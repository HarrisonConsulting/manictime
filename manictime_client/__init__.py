import logging
import sys
from manictime.client import ManicTimeClient
from manictime.config import Config
from manictime.exceptions import ManicTimeClientError, AuthenticationError, NotFoundError
from manictime.models import Timeline, Activity, TagCombination

# Configure logging
logger = logging.getLogger("manictime")
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

__all__ = [
    'ManicTimeClient',
    'Config',
    'ManicTimeClientError',
    'AuthenticationError',
    'NotFoundError',
    'Timeline',
    'Activity',
    'TagCombination'
]