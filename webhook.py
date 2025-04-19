"""Webhook handlers for ManicTime API events."""
import json
import hmac
import hashlib
import logging
import threading
from typing import Dict, Any, Callable, Optional, List
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs

logger = logging.getLogger("manictime.webhook")

# Type definitions
WebhookHandler = Callable[[Dict[str, Any]], None]
WebhookVerifier = Callable[[bytes, str, str], bool]


class WebhookConfig:
    """Configuration for webhook handler"""
    
    def __init__(self, 
                secret: Optional[str] = None,
                path: str = "/",
                host: str = "0.0.0.0",
                port: int = 5000,
                signature_header: str = "X-ManicTime-Signature"):
        """
        Initialize webhook configuration
        
        Args:
            secret: Secret key for validating webhook signatures
            path: URL path to listen on (default: "/")
            host: Host to bind to (default: "0.0.0.0")
            port: Port to listen on (default: 5000)
            signature_header: HTTP header containing the signature
        """
        self.secret = secret
        self.path = path
        self.host = host
        self.port = port
        self.signature_header = signature_header


def default_signature_verifier(payload: bytes, 
                             signature: str, 
                             secret: str) -> bool:
    """
    Default webhook signature verification function
    
    Args:
        payload: Raw request payload
        signature: Signature from HTTP header
        secret: Secret key for verification
        
    Returns:
        True if signature is valid, False otherwise
    """
    if not signature or not secret:
        return False
        
    # Calculate expected signature
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    # Compare signatures in constant time to prevent timing attacks
    return hmac.compare_digest(expected, signature)


class WebhookRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for webhooks"""
    
    # Set by WebhookServer
    handlers: Dict[str, List[WebhookHandler]] = {}
    config: WebhookConfig = None
    verifier: WebhookVerifier = None
    
    def do_POST(self):
        """Handle POST requests"""
        # Check if path matches
        if self.path != self.config.path:
            self.send_error(404)
            return
            
        # Get content length
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length <= 0:
            self.send_error(400, "Missing payload")
            return
            
        # Read payload
        payload = self.rfile.read(content_length)
        
        # Verify signature if configured
        if self.config.secret and self.verifier:
            signature = self.headers.get(self.config.signature_header)
            if not signature:
                logger.warning("Missing signature header")
                self.send_error(401, "Missing signature")
                return
                
            if not self.verifier(payload, signature, self.config.secret):
                logger.warning("Invalid signature")
                self.send_error(401, "Invalid signature")
                return
        
        # Parse JSON payload
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            logger.error("Invalid JSON payload")
            self.send_error(400, "Invalid JSON")
            return
            
        # Get event type
        event_type = data.get("event") or "default"
        
        # Call handlers
        handlers_to_call = self.handlers.get(event_type, []) + self.handlers.get("*", [])
        
        if not handlers_to_call:
            logger.warning(f"No handlers for event: {event_type}")
            
        for handler in handlers_to_call:
            try:
                handler(data)
            except Exception as e:
                logger.error(f"Error in webhook handler: {str(e)}")
        
        # Send response
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"success"}')
        
    def log_message(self, format, *args):
        """Custom logging"""
        logger.info(f"Webhook request: {format % args}")


class WebhookServer:
    """Server for handling ManicTime webhooks"""
    
    def __init__(self, config: WebhookConfig = None):
        """
        Initialize webhook server
        
        Args:
            config: Webhook configuration or None for defaults
        """
        self.config = config or WebhookConfig()
        self.server = None
        self.server_thread = None
        self.handlers: Dict[str, List[WebhookHandler]] = {}
        self.verifier = default_signature_verifier
        
    def add_handler(self, event_type: str, handler: WebhookHandler) -> None:
        """
        Add handler for event type
        
        Args:
            event_type: Event type to handle or "*" for all events
            handler: Function to call when event is received
        """
        if event_type not in self.handlers:
            self.handlers[event_type] = []
            
        self.handlers[event_type].append(handler)
        logger.debug(f"Added handler for event: {event_type}")
        
    def remove_handler(self, event_type: str, handler: WebhookHandler) -> bool:
        """
        Remove handler for event type
        
        Args:
            event_type: Event type
            handler: Handler function to remove
            
        Returns:
            True if handler was removed, False otherwise
        """
        if event_type not in self.handlers:
            return False
            
        try:
            self.handlers[event_type].remove(handler)
            logger.debug(f"Removed handler for event: {event_type}")
            return True
        except ValueError:
            return False
            
    def set_signature_verifier(self, verifier: WebhookVerifier) -> None:
        """
        Set custom signature verification function
        
        Args:
            verifier: Function to verify webhook signatures
        """
        self.verifier = verifier
        
    def start(self, daemon: bool = True) -> None:
        """
        Start webhook server in background thread
        
        Args:
            daemon: Whether server thread should be a daemon
        """
        if self.server:
            logger.warning("Webhook server already running")
            return
            
        # Set handler class attributes
        WebhookRequestHandler.handlers = self.handlers
        WebhookRequestHandler.config = self.config
        WebhookRequestHandler.verifier = self.verifier
        
        # Create server
        self.server = HTTPServer((self.config.host, self.config.port), WebhookRequestHandler)
        
        # Start server thread
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = daemon
        self.server_thread.start()
        
        logger.info(f"Webhook server started on {self.config.host}:{self.config.port}")
        
    def stop(self) -> None:
        """Stop webhook server"""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
            self.server_thread = None
            logger.info("Webhook server stopped")
            
    def __enter__(self):
        """Start server when entering context"""
        self.start()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop server when exiting context"""
        self.stop()


class WebhookManager:
    """Manager for registering webhooks with ManicTime server"""
    
    def __init__(self, client):
        """
        Initialize webhook manager
        
        Args:
            client: ManicTimeClient instance
        """
        self.client = client
        
    def register_webhook(self, url: str, events: List[str], 
                        secret: Optional[str] = None,
                        description: Optional[str] = None) -> Dict[str, Any]:
        """
        Register a new webhook with ManicTime server
        
        Args:
            url: Callback URL for webhook
            events: List of event types to subscribe to
            secret: Optional shared secret for signature verification
            description: Optional webhook description
            
        Returns:
            Created webhook data
        """
        endpoint = f"{self.client.config.server_url}/api/webhooks"
        
        data = {
            "url": url,
            "events": events
        }
        
        if secret:
            data["secret"] = secret
            
        if description:
            data["description"] = description
            
        logger.info(f"Registering webhook for events: {', '.join(events)}")
        return self.client._make_request(endpoint, method="POST", data=data)
        
    def get_webhooks(self) -> List[Dict[str, Any]]:
        """
        Get list of registered webhooks
        
        Returns:
            List of webhook data
        """
        endpoint = f"{self.client.config.server_url}/api/webhooks"
        return self.client._make_request(endpoint)
        
    def get_webhook(self, webhook_id: str) -> Dict[str, Any]:
        """
        Get webhook details
        
        Args:
            webhook_id: Webhook ID
            
        Returns:
            Webhook data
        """
        endpoint = f"{self.client.config.server_url}/api/webhooks/{webhook_id}"
        return self.client._make_request(endpoint)
        
    def update_webhook(self, webhook_id: str, url: Optional[str] = None,
                      events: Optional[List[str]] = None, 
                      secret: Optional[str] = None,
                      description: Optional[str] = None) -> Dict[str, Any]:
        """
        Update webhook configuration
        
        Args:
            webhook_id: Webhook ID
            url: New callback URL (optional)
            events: New list of event types (optional)
            secret: New shared secret (optional)
            description: New description (optional)
            
        Returns:
            Updated webhook data
        """
        endpoint = f"{self.client.config.server_url}/api/webhooks/{webhook_id}"
        
        data = {}
        
        if url:
            data["url"] = url
            
        if events:
            data["events"] = events
            
        if secret:
            data["secret"] = secret
            
        if description:
            data["description"] = description
            
        logger.info(f"Updating webhook {webhook_id}")
        return self.client._make_request(endpoint, method="PUT", data=data)
        
    def delete_webhook(self, webhook_id: str) -> None:
        """
        Delete webhook
        
        Args:
            webhook_id: Webhook ID
        """
        endpoint = f"{self.client.config.server_url}/api/webhooks/{webhook_id}"
        logger.info(f"Deleting webhook {webhook_id}")
        self.client._make_request(endpoint, method="DELETE")
        
    def test_webhook(self, webhook_id: str) -> Dict[str, Any]:
        """
        Send test event to webhook
        
        Args:
            webhook_id: Webhook ID
            
        Returns:
            Test result
        """
        endpoint = f"{self.client.config.server_url}/api/webhooks/{webhook_id}/test"
        logger.info(f"Testing webhook {webhook_id}")
        return self.client._make_request(endpoint, method="POST")


class AsyncWebhookManager:
    """Async manager for registering webhooks with ManicTime server"""
    
    def __init__(self, client):
        """
        Initialize webhook manager
        
        Args:
            client: AsyncManicTimeClient instance
        """
        self.client = client
        
    async def register_webhook(self, url: str, events: List[str], 
                             secret: Optional[str] = None,
                             description: Optional[str] = None) -> Dict[str, Any]:
        """
        Register a new webhook with ManicTime server
        
        Args:
            url: Callback URL for webhook
            events: List of event types to subscribe to
            secret: Optional shared secret for signature verification
            description: Optional webhook description
            
        Returns:
            Created webhook data
        """
        endpoint = f"{self.client.config.server_url}/api/webhooks"
        
        data = {
            "url": url,
            "events": events
        }
        
        if secret:
            data["secret"] = secret
            
        if description:
            data["description"] = description
            
        logger.info(f"Registering webhook for events: {', '.join(events)}")
        return await self.client._make_request(endpoint, method="POST", data=data)
        
    async def get_webhooks(self) -> List[Dict[str, Any]]:
        """
        Get list of registered webhooks
        
        Returns:
            List of webhook data
        """
        endpoint = f"{self.client.config.server_url}/api/webhooks"
        return await self.client._make_request(endpoint)
        
    async def get_webhook(self, webhook_id: str) -> Dict[str, Any]:
        """
        Get webhook details
        
        Args:
            webhook_id: Webhook ID
            
        Returns:
            Webhook data
        """
        endpoint = f"{self.client.config.server_url}/api/webhooks/{webhook_id}"
        return await self.client._make_request(endpoint)
        
    async def update_webhook(self, webhook_id: str, url: Optional[str] = None,
                           events: Optional[List[str]] = None, 
                           secret: Optional[str] = None,
                           description: Optional[str] = None) -> Dict[str, Any]:
        """
        Update webhook configuration
        
        Args:
            webhook_id: Webhook ID
            url: New callback URL (optional)
            events: New list of event types (optional)
            secret: New shared secret (optional)
            description: New description (optional)
            
        Returns:
            Updated webhook data
        """
        endpoint = f"{self.client.config.server_url}/api/webhooks/{webhook_id}"
        
        data = {}
        
        if url:
            data["url"] = url
            
        if events:
            data["events"] = events
            
        if secret:
            data["secret"] = secret
            
        if description:
            data["description"] = description
            
        logger.info(f"Updating webhook {webhook_id}")
        return await self.client._make_request(endpoint, method="PUT", data=data)
        
    async def delete_webhook(self, webhook_id: str) -> None:
        """
        Delete webhook
        
        Args:
            webhook_id: Webhook ID
        """
        endpoint = f"{self.client.config.server_url}/api/webhooks/{webhook_id}"
        logger.info(f"Deleting webhook {webhook_id}")
        await self.client._make_request(endpoint, method="DELETE")
        
    async def test_webhook(self, webhook_id: str) -> Dict[str, Any]:
        """
        Send test event to webhook
        
        Args:
            webhook_id: Webhook ID
            
        Returns:
            Test result
        """
        endpoint = f"{self.client.config.server_url}/api/webhooks/{webhook_id}/test"
        logger.info(f"Testing webhook {webhook_id}")
        return await self.client._make_request(endpoint, method="POST")