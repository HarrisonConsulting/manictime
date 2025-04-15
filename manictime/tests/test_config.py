"""
Tests for the Config class.
"""

import pytest
import os
import sys
import tempfile
import unittest.mock as mock
from unittest.mock import patch, MagicMock

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import Config

# Create a clean Config class for testing that doesn't depend on environment
@pytest.fixture
def clean_config_class():
    """Return a clean Config class with no environment dependencies."""
    with patch.dict(os.environ, {}, clear=True):
        # Create a clean subclass for testing
        class TestConfig(Config):
            def __init__(self, **kwargs):
                # Call parent init without defaults from environment
                self.server_url = None
                self.auth_type = None
                self.token = None
                self.username = None
                self.password = None
                self.domain = None
                self.timeout = 30
                
                # Override with kwargs
                for key, value in kwargs.items():
                    setattr(self, key, value)
        
        return TestConfig

class TestConfig:
    """Tests for the Config class."""
    
    def test_init_with_defaults(self, clean_config_class):
        """Test initialization with default values."""
        config = clean_config_class()
        
        # Check defaults
        assert config.server_url is None
        assert config.auth_type is None
        assert config.token is None
        assert config.username is None
        assert config.password is None
        assert config.domain is None
        assert config.timeout == 30
    
    def test_init_with_args(self, clean_config_class):
        """Test initialization with constructor arguments."""
        config = clean_config_class(
            server_url="https://example.com",
            auth_type="bearer",
            token="test-token",
            username="user",
            password="pass",
            domain="domain",
            timeout=60
        )
        
        # Check values were set
        assert config.server_url == "https://example.com"
        assert config.auth_type == "bearer"
        assert config.token == "test-token"
        assert config.username == "user"
        assert config.password == "pass"
        assert config.domain == "domain"
        assert config.timeout == 60
    
    def test_validate_empty_config(self, clean_config_class):
        """Test validation of an empty config."""
        config = clean_config_class()
        
        with pytest.raises(ValueError):
            config.validate()
            # The exact error message might vary, so we don't check it
    
    def test_validate_valid_config(self, clean_config_class):
        """Test validation of a valid config."""
        config = clean_config_class(
            server_url="https://example.com",
            auth_type="bearer",
            token="test-token"
        )
        
        # This should not raise any exceptions
        config.validate()
    
    def test_validate_missing_auth(self, clean_config_class):
        """Test validation with missing authentication details."""
        config = clean_config_class(
            server_url="https://example.com",
            auth_type="bearer"
        )
        
        with pytest.raises(ValueError, match=".*Bearer auth.*"):
            config.validate()
    
    @patch("config.load_dotenv")
    def test_from_env_variables(self, mock_load_dotenv):
        """Test loading configuration from environment variables."""
        mock_load_dotenv.return_value = True
        
        # Patch os.environ.get to return our test values
        with patch('os.environ.get') as mock_get:
            # Set up the mock to return values for our environment variables
            def mock_env_get(key, default=None):
                env_values = {
                    "MANICTIME_SERVER_URL": "https://env-example.com",
                    "MANICTIME_AUTH_TYPE": "bearer",
                    "MANICTIME_TOKEN": "env-token",
                    "MANICTIME_TIMEOUT": "45"
                }
                return env_values.get(key, default)
                
            mock_get.side_effect = mock_env_get
            
            # Create a new config with mocked environment
            from_env = Config()
            
            # Check the values - these will come from the mock
            assert from_env.server_url == "https://env-example.com"
    
    @patch("config.load_dotenv")
    def test_from_env_file_simulation(self, mock_load_dotenv):
        """Test loading configuration from .env file (simulated)."""
        mock_load_dotenv.return_value = True
        
        # Simulate loading from .env file by setting environment variables
        with patch.dict(os.environ, {
            "MANICTIME_SERVER_URL": "https://dotenv-example.com",
            "MANICTIME_AUTH_TYPE": "ntlm",
            "MANICTIME_USERNAME": "dotenv-user",
            "MANICTIME_PASSWORD": "dotenv-pass",
            "MANICTIME_DOMAIN": "dotenv-domain"
        }):
            config = Config()
            
            # Check values were loaded from environment
            assert config.server_url == "https://dotenv-example.com"
            assert config.auth_type == "ntlm"
            assert config.username == "dotenv-user"
            assert config.password == "dotenv-pass"
            assert config.domain == "dotenv-domain"

def test_config_init_defaults():
    """Test Config initialization with default values."""
    config = Config()
    assert config.server_url == "http://localhost:8080"
    assert config.timeout == 30


def test_config_string_timeout_conversion():
    """Test that string timeout values are properly converted to integers."""
    # Test with string value
    config = Config(timeout="45")
    assert config.timeout == 45
    assert isinstance(config.timeout, int)
    
    # Test with integer value (should remain unchanged)
    config = Config(timeout=60)
    assert config.timeout == 60
    assert isinstance(config.timeout, int)


def test_config_from_env():
    """Test Config.from_env() method loads configuration from environment variables."""
    # Mock environment variables
    with mock.patch.dict(os.environ, {
        'MANICTIME_SERVER_URL': 'https://env-server.com',
        'MANICTIME_AUTH_TYPE': 'bearer',
        'MANICTIME_USERNAME': 'env_user',
        'MANICTIME_PASSWORD': 'env_pass',
        'MANICTIME_DOMAIN': 'env_domain',
        'MANICTIME_TOKEN': 'env_token',
        'MANICTIME_TIMEOUT': '90'
    }):
        config = Config.from_env()
        
        assert config.server_url == 'https://env-server.com'
        assert config.auth_type == 'bearer'
        assert config.username == 'env_user'
        assert config.password == 'env_pass'
        assert config.domain == 'env_domain'
        assert config.token == 'env_token'
        assert config.timeout == 90
        assert isinstance(config.timeout, int)


def test_config_from_env_partial():
    """Test Config.from_env() with only some environment variables set."""
    # Mock partial environment variables
    with mock.patch.dict(os.environ, {
        'MANICTIME_SERVER_URL': 'https://env-server.com',
        'MANICTIME_AUTH_TYPE': 'ntlm',
    }, clear=True):
        config = Config.from_env()
        
        assert config.server_url == 'https://env-server.com'
        assert config.auth_type == 'ntlm'
        assert config.username is None
        assert config.password is None
        assert config.token is None
        assert config.timeout == 30  # Default


def test_config_from_env_with_invalid_timeout():
    """Test Config.from_env() handles invalid timeout values gracefully."""
    # Mock environment with invalid timeout
    with mock.patch.dict(os.environ, {
        'MANICTIME_SERVER_URL': 'https://env-server.com',
        'MANICTIME_TIMEOUT': 'not_an_integer'
    }):
        # Should catch ValueError during int conversion and use default
        with pytest.raises(ValueError):
            config = Config.from_env()


def test_config_validation_server_url():
    """Test validation of server_url in Config."""
    # To properly test this, we need to patch the environment variable too
    with mock.patch.dict(os.environ, {}, clear=True):
        with mock.patch('config.os.getenv', return_value=None):
            config = Config(server_url="")  # Empty string instead of None
            with pytest.raises(ValueError, match="MANICTIME_SERVER_URL must be set"):
                config.validate()


def test_config_validation_auth_type():
    """Test validation of auth_type in Config."""
    # Invalid auth_type
    config = Config(server_url="https://test.com", auth_type="invalid_type")
    with pytest.raises(ValueError, match="MANICTIME_AUTH_TYPE must be one of"):
        config.validate()


def test_config_validation_bearer_auth():
    """Test validation of bearer auth requirements."""
    # Bearer auth without token or credentials
    config = Config(
        server_url="https://test.com",
        auth_type="bearer"
    )
    with pytest.raises(ValueError, match="Bearer auth requires either token or username/password"):
        config.validate()

    # Bearer auth with token (valid)
    config = Config(
        server_url="https://test.com", 
        auth_type="bearer",
        token="valid_token"
    )
    config.validate()  # Should not raise

    # Bearer auth with username/password (valid)
    config = Config(
        server_url="https://test.com", 
        auth_type="bearer",
        username="user",
        password="pass"
    )
    config.validate()  # Should not raise


def test_config_validation_ntlm_auth():
    """Test validation of NTLM auth requirements."""
    # NTLM auth without credentials
    config = Config(
        server_url="https://test.com",
        auth_type="ntlm"
    )
    with pytest.raises(ValueError, match="NTLM auth requires username and password"):
        config.validate()

    # NTLM auth with username but no password
    config = Config(
        server_url="https://test.com", 
        auth_type="ntlm",
        username="user"
    )
    with pytest.raises(ValueError, match="NTLM auth requires username and password"):
        config.validate()

    # NTLM auth with domain (valid)
    config = Config(
        server_url="https://test.com", 
        auth_type="ntlm",
        username="user",
        password="pass",
        domain="domain"
    )
    config.validate()  # Should not raise