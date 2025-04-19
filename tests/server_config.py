"""
Configuration for connecting to external ManicTime servers for integration testing.
These values are loaded from the .env file in the manictime directory.
"""

# Set to True to use external server instead of Docker
USE_EXTERNAL_SERVER = True

# Server connection details loaded from .env file
SERVER_URL = "https://time.harrison.consulting"
ADMIN_USERNAME = "matt@harrison.consulting"
ADMIN_PASSWORD = "v077vWCP"
