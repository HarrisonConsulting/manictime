import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Configuration management class"""
    def __init__(self):
        self.server_url = os.getenv('MANICTIME_SERVER_URL', 'http://localhost:8080')
        self.auth_type = os.getenv('MANICTIME_AUTH_TYPE')
        self.username = os.getenv('MANICTIME_USERNAME')
        self.password = os.getenv('MANICTIME_PASSWORD')
        self.domain = os.getenv('MANICTIME_DOMAIN')
        self.token = os.getenv('MANICTIME_TOKEN')
        self.timeout = int(os.getenv('MANICTIME_TIMEOUT', 30))

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