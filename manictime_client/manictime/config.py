import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Configuration management class"""
    def __init__(self, server_url=None, auth_type=None, username=None, 
                password=None, domain=None, token=None, timeout=30):
        self.server_url = server_url or os.getenv('MANICTIME_SERVER_URL', 'http://localhost:8080')
        self.auth_type = auth_type or os.getenv('MANICTIME_AUTH_TYPE')
        self.username = username or os.getenv('MANICTIME_USERNAME')
        self.password = password or os.getenv('MANICTIME_PASSWORD')
        self.domain = domain or os.getenv('MANICTIME_DOMAIN')
        self.token = token or os.getenv('MANICTIME_TOKEN')
        
        # Handle timeout conversion
        if isinstance(timeout, str):
            self.timeout = int(timeout)
        else:
            self.timeout = timeout
            
    @classmethod
    def from_env(cls):
        """Create a new Config instance from environment variables"""
        # Re-load environment variables to ensure we have the latest values
        load_dotenv()
        
        # Convert timeout to int if present
        timeout_str = os.getenv('MANICTIME_TIMEOUT')
        timeout = int(timeout_str) if timeout_str else 30
        
        return cls(
            server_url=os.getenv('MANICTIME_SERVER_URL'),
            auth_type=os.getenv('MANICTIME_AUTH_TYPE'),
            username=os.getenv('MANICTIME_USERNAME'),
            password=os.getenv('MANICTIME_PASSWORD'),
            domain=os.getenv('MANICTIME_DOMAIN'),
            token=os.getenv('MANICTIME_TOKEN'),
            timeout=timeout
        )

    def validate(self):
        """Validate configuration"""
        if not self.server_url:
            raise ValueError("MANICTIME_SERVER_URL must be set")
        
        if self.auth_type not in [None, 'ntlm', 'bearer']:
            raise ValueError("MANICTIME_AUTH_TYPE must be one of: ntlm, bearer")
            
        if self.auth_type == 'bearer' and not (self.token or (self.username and self.password)):
            raise ValueError("Bearer auth requires either token or username/password")
            
        if self.auth_type == 'ntlm' and not (self.username and self.password):
            raise ValueError("NTLM auth requires username and password")