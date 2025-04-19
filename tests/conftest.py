import pytest
import requests
import time
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import Config
from client import ManicTimeClient

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import custom server configuration
try:
    from .server_config import USE_EXTERNAL_SERVER, SERVER_URL, ADMIN_USERNAME, ADMIN_PASSWORD
    logger.info(f"Using custom server configuration: {SERVER_URL}")
except ImportError:
    # Default values if server_config.py doesn't exist
    # Check for environment variables first, then use defaults
    USE_EXTERNAL_SERVER = os.getenv('MANICTIME_USE_EXTERNAL_SERVER', 'False').lower() == 'true'
    SERVER_URL = os.getenv('MANICTIME_SERVER_URL', 'http://localhost:8080')
    ADMIN_USERNAME = os.getenv('MANICTIME_ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.getenv('MANICTIME_ADMIN_PASSWORD', 'admin123')
    logger.info(f"Using {'environment variables' if any([os.getenv('MANICTIME_SERVER_URL'), os.getenv('MANICTIME_ADMIN_USERNAME')]) else 'default'} server configuration")

# Docker-based server configuration
DOCKER_URL = os.getenv('MANICTIME_DOCKER_URL', 'http://localhost:8080')
MAX_RETRIES = int(os.getenv('MANICTIME_MAX_RETRIES', '5'))
RETRY_DELAY = int(os.getenv('MANICTIME_RETRY_DELAY', '2'))  # seconds

def is_server_running(url):
    """Check if the ManicTime server is running."""
    try:
        response = requests.get(f"{url}/api/server/info", timeout=5)
        logger.info(f"Server info response: {response.status_code}")
        return response.status_code == 200
    except requests.RequestException as e:
        logger.error(f"Error checking server: {str(e)}")
        return False
        
def test_server_credentials(url, username, password):
    """Test if we can authenticate with the server."""
    try:
        # Create a test client
        config = Config()
        config.server_url = url
        config.username = username
        config.password = password
        config.auth_type = "bearer"
        
        # Create a client and attempt to authenticate
        client = ManicTimeClient(config)
        
        # Try to access a protected endpoint
        timelines = client.get_timelines()
        
        # If we got here without error, authentication works
        logger.info(f"Successfully authenticated with ManicTime server at {url}")
        return True
    except Exception as e:
        logger.warning(f"Failed to authenticate with ManicTime server at {url}: {str(e)}")
        return False

@pytest.fixture(scope="session")
def server_config():
    """Provide a server configuration for tests."""
    if USE_EXTERNAL_SERVER:
        logger.info(f"Using external ManicTime server at {SERVER_URL}")
        
        # Test external server connection
        if is_server_running(SERVER_URL):
            logger.info("External ManicTime server is running")
            
            # Test authentication
            if test_server_credentials(SERVER_URL, ADMIN_USERNAME, ADMIN_PASSWORD):
                logger.info("External ManicTime server authentication successful")
                
                # Create server configuration
                config = Config()
                config.server_url = SERVER_URL
                config.username = ADMIN_USERNAME
                config.password = ADMIN_PASSWORD
                config.auth_type = "bearer"
                
                return config
            else:
                logger.warning("External ManicTime server authentication failed")
        else:
            logger.warning(f"External ManicTime server at {SERVER_URL} is not reachable")
    else:
        logger.info("Using Docker ManicTime server for testing")
        
        # Check if the server is running in Docker
        for attempt in range(MAX_RETRIES):
            if is_server_running(DOCKER_URL):
                logger.info("Docker ManicTime server is running")
                
                # Test authentication
                if test_server_credentials(DOCKER_URL, ADMIN_USERNAME, ADMIN_PASSWORD):
                    logger.info("Docker ManicTime server authentication successful")
                    
                    # Create server configuration
                    config = Config()
                    config.server_url = DOCKER_URL
                    config.username = ADMIN_USERNAME
                    config.password = ADMIN_PASSWORD
                    config.auth_type = "bearer"
                    
                    return config
                else:
                    logger.warning("Docker ManicTime server authentication failed")
                    
                break
            else:
                if attempt < MAX_RETRIES - 1:
                    logger.info(f"Waiting for Docker ManicTime server to start (attempt {attempt+1}/{MAX_RETRIES})...")
                    time.sleep(RETRY_DELAY)
                else:
                    logger.warning("Docker ManicTime server is not running.")
    
    # Create fallback server configuration
    config = Config()
    config.server_url = SERVER_URL if USE_EXTERNAL_SERVER else DOCKER_URL
    config.username = ADMIN_USERNAME
    config.password = ADMIN_PASSWORD
    config.auth_type = "bearer"
    
    pytest.skip("ManicTime server is not available or authentication failed")
    return config

@pytest.fixture
def mock_client():
    """Provide a mock client for tests."""
    config = Config()
    config.server_url = "http://mock-server"
    config.auth_type = "bearer"
    config.token = "mock-token"
    
    client = ManicTimeClient(config)
    return client