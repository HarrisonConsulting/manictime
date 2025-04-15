"""OAuth authentication flow for ManicTime API."""
import os
import json
import time
import random
import string
import webbrowser
import http.server
import socketserver
import urllib.parse
from typing import Dict, Any, Optional, Callable
import threading
import logging
from pathlib import Path
from datetime import datetime, timedelta
import requests

logger = logging.getLogger("manictime.oauth")

class OAuthTokenStorage:
    """Storage for OAuth tokens"""
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize token storage
        
        Args:
            storage_path: Path to token storage file (default: ~/.manictime/tokens.json)
        """
        if storage_path is None:
            home_dir = Path.home()
            storage_dir = home_dir / ".manictime"
            storage_dir.mkdir(exist_ok=True)
            self.storage_path = storage_dir / "tokens.json"
        else:
            self.storage_path = Path(storage_path)
            
    def save_tokens(self, client_id: str, tokens: Dict[str, Any]) -> None:
        """
        Save tokens for a client ID
        
        Args:
            client_id: OAuth client ID
            tokens: Dictionary with tokens and metadata
        """
        # Add timestamp for tracking token age
        tokens["stored_at"] = datetime.now().isoformat()
        
        # Read existing tokens
        all_tokens = {}
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r") as f:
                    all_tokens = json.load(f)
            except json.JSONDecodeError:
                logger.warning(f"Couldn't parse tokens file at {self.storage_path}, creating new file")
        
        # Update with new tokens
        all_tokens[client_id] = tokens
        
        # Save back to file
        with open(self.storage_path, "w") as f:
            json.dump(all_tokens, f, indent=2)
        
        logger.info(f"Saved tokens for client {client_id}")
        
    def get_tokens(self, client_id: str) -> Optional[Dict[str, Any]]:
        """
        Get tokens for a client ID
        
        Args:
            client_id: OAuth client ID
            
        Returns:
            Dictionary with tokens or None if not found
        """
        if not self.storage_path.exists():
            return None
            
        try:
            with open(self.storage_path, "r") as f:
                all_tokens = json.load(f)
                
            if client_id in all_tokens:
                return all_tokens[client_id]
        except (json.JSONDecodeError, IOError):
            logger.warning(f"Error reading tokens from {self.storage_path}")
            
        return None
        
    def delete_tokens(self, client_id: str) -> bool:
        """
        Delete tokens for a client ID
        
        Args:
            client_id: OAuth client ID
            
        Returns:
            True if tokens were deleted, False otherwise
        """
        if not self.storage_path.exists():
            return False
            
        try:
            with open(self.storage_path, "r") as f:
                all_tokens = json.load(f)
                
            if client_id in all_tokens:
                del all_tokens[client_id]
                
                with open(self.storage_path, "w") as f:
                    json.dump(all_tokens, f, indent=2)
                    
                logger.info(f"Deleted tokens for client {client_id}")
                return True
                
        except (json.JSONDecodeError, IOError):
            logger.warning(f"Error manipulating tokens in {self.storage_path}")
            
        return False


class AuthorizationCodeHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for OAuth authorization code callback"""
    
    # Will be set by the server
    auth_code = None
    state_param = None
    received_state = None
    error = None
    
    def do_GET(self):
        """Handle GET request with authorization code or error"""
        parsed_url = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed_url.query)
        
        # Set response headers
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        
        if "error" in params:
            AuthorizationCodeHandler.error = params["error"][0]
            self.wfile.write(b"Authentication failed. You can close this window.")
            return
            
        if "code" in params and "state" in params:
            received_state = params["state"][0]
            
            if received_state != AuthorizationCodeHandler.state_param:
                AuthorizationCodeHandler.error = "Invalid state parameter"
                self.wfile.write(b"Authentication failed: Invalid state parameter. You can close this window.")
                return
                
            AuthorizationCodeHandler.auth_code = params["code"][0]
            AuthorizationCodeHandler.received_state = received_state
            
            self.wfile.write(b"Authentication successful! You can close this window.")
        else:
            AuthorizationCodeHandler.error = "Missing code or state parameter"
            self.wfile.write(b"Authentication failed: Missing parameters. You can close this window.")
    
    def log_message(self, format, *args):
        """Suppress default logging"""
        return


class OAuthClient:
    """OAuth client for ManicTime API"""
    
    def __init__(self, 
                client_id: str,
                client_secret: str,
                auth_url: str = "https://login.manictime.com",
                token_url: Optional[str] = None,
                callback_url: str = "http://127.0.0.1:4040",
                scope: str = "openid profile email api",
                token_storage: Optional[OAuthTokenStorage] = None):
        """
        Initialize OAuth client
        
        Args:
            client_id: OAuth client ID
            client_secret: OAuth client secret
            auth_url: Authorization server URL
            token_url: Token endpoint URL (if different from auth_url)
            callback_url: Callback URL for authorization code
            scope: OAuth scopes to request
            token_storage: Custom token storage or None to use default
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.auth_url = auth_url
        self.token_url = token_url or f"{auth_url}/connect/token"
        self.callback_url = callback_url
        self.scope = scope
        self.token_storage = token_storage or OAuthTokenStorage()
        
        # Check for existing tokens
        self.tokens = self.token_storage.get_tokens(client_id)
        
    def is_authenticated(self) -> bool:
        """
        Check if we have valid tokens
        
        Returns:
            True if we have valid tokens, False otherwise
        """
        if not self.tokens or "access_token" not in self.tokens:
            return False
            
        # Check if token is expired
        if "expires_at" in self.tokens:
            expires_at = datetime.fromisoformat(self.tokens["expires_at"])
            if datetime.now() >= expires_at:
                return False
                
        return True
        
    def generate_auth_url(self, state: Optional[str] = None) -> tuple[str, str]:
        """
        Generate authorization URL for user to visit
        
        Args:
            state: Optional state parameter or None to generate random state
            
        Returns:
            Tuple of (auth_url, state)
        """
        if state is None:
            # Generate random state parameter
            state = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(32))
            
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.callback_url,
            "response_type": "code",
            "scope": self.scope,
            "state": state
        }
        
        query_string = urllib.parse.urlencode(params)
        auth_url = f"{self.auth_url}/connect/authorize?{query_string}"
        
        return auth_url, state
        
    def start_authorization_code_flow(self) -> str:
        """
        Start OAuth flow by opening browser and waiting for callback
        
        Returns:
            Access token on success
            
        Raises:
            ValueError on authentication failure
        """
        logger.info("Starting OAuth authorization code flow")
        
        # Generate authorization URL
        auth_url, state = self.generate_auth_url()
        
        # Start local server to receive callback
        server_url = urllib.parse.urlparse(self.callback_url)
        if not server_url.port:
            port = 80 if server_url.scheme == "http" else 443
        else:
            port = server_url.port
            
        server = None
        try:
            # Set static class variables for the handler
            AuthorizationCodeHandler.auth_code = None
            AuthorizationCodeHandler.state_param = state
            AuthorizationCodeHandler.error = None
            
            # Start server in a thread
            server = socketserver.TCPServer(("", port), AuthorizationCodeHandler)
            server_thread = threading.Thread(target=server.serve_forever)
            server_thread.daemon = True
            server_thread.start()
            
            logger.info(f"Listening for authorization code on port {port}")
            
            # Open browser with authorization URL
            logger.info(f"Opening browser for authentication")
            webbrowser.open(auth_url)
            
            # Wait for callback to set the authorization code
            max_wait = 60  # seconds
            start_time = time.time()
            
            while not AuthorizationCodeHandler.auth_code and not AuthorizationCodeHandler.error:
                time.sleep(0.5)
                if time.time() - start_time > max_wait:
                    raise ValueError("Timeout waiting for authorization code")
                    
            # Check for errors
            if AuthorizationCodeHandler.error:
                raise ValueError(f"Authentication error: {AuthorizationCodeHandler.error}")
                
            # Exchange code for tokens
            if AuthorizationCodeHandler.auth_code:
                return self.exchange_code_for_tokens(AuthorizationCodeHandler.auth_code)
                
            raise ValueError("No authorization code received")
            
        finally:
            if server:
                server.shutdown()
                server.server_close()
                
    def exchange_code_for_tokens(self, code: str) -> str:
        """
        Exchange authorization code for tokens
        
        Args:
            code: Authorization code from callback
            
        Returns:
            Access token
            
        Raises:
            ValueError on token exchange failure
        """
        logger.info("Exchanging authorization code for tokens")
        
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.callback_url
        }
        
        try:
            response = requests.post(self.token_url, data=data)
            response.raise_for_status()
            token_data = response.json()
            
            if "access_token" not in token_data:
                raise ValueError("No access token in response")
                
            # Calculate expiration time
            if "expires_in" in token_data:
                expires_at = datetime.now() + timedelta(seconds=token_data["expires_in"])
                token_data["expires_at"] = expires_at.isoformat()
                
            # Store tokens
            self.tokens = token_data
            self.token_storage.save_tokens(self.client_id, token_data)
            
            logger.info("Successfully obtained tokens")
            return token_data["access_token"]
            
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Failed to exchange code for tokens: {str(e)}")
            
    def refresh_token(self) -> Optional[str]:
        """
        Refresh access token using refresh token
        
        Returns:
            New access token or None if refresh failed
            
        Raises:
            ValueError if refresh token is missing or invalid
        """
        if not self.tokens or "refresh_token" not in self.tokens:
            raise ValueError("No refresh token available")
            
        logger.info("Refreshing access token")
        
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": self.tokens["refresh_token"]
        }
        
        try:
            response = requests.post(self.token_url, data=data)
            response.raise_for_status()
            token_data = response.json()
            
            if "access_token" not in token_data:
                raise ValueError("No access token in response")
                
            # Calculate expiration time
            if "expires_in" in token_data:
                expires_at = datetime.now() + timedelta(seconds=token_data["expires_in"])
                token_data["expires_at"] = expires_at.isoformat()
                
            # Preserve refresh token if not returned
            if "refresh_token" not in token_data and "refresh_token" in self.tokens:
                token_data["refresh_token"] = self.tokens["refresh_token"]
                
            # Store tokens
            self.tokens = token_data
            self.token_storage.save_tokens(self.client_id, token_data)
            
            logger.info("Successfully refreshed tokens")
            return token_data["access_token"]
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to refresh token: {str(e)}")
            return None
            
    def get_access_token(self, force_refresh: bool = False) -> str:
        """
        Get access token, refreshing if necessary
        
        Args:
            force_refresh: Force token refresh even if not expired
            
        Returns:
            Access token
            
        Raises:
            ValueError if no valid token available
        """
        if not self.is_authenticated() or force_refresh:
            if self.tokens and "refresh_token" in self.tokens:
                refreshed_token = self.refresh_token()
                if refreshed_token:
                    return refreshed_token
            
            # If no refresh token or refresh failed, start authorization flow
            return self.start_authorization_code_flow()
        
        return self.tokens["access_token"]
        
    def logout(self) -> bool:
        """
        Clear stored tokens
        
        Returns:
            True if tokens were cleared, False otherwise
        """
        self.tokens = None
        return self.token_storage.delete_tokens(self.client_id)