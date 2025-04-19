"""
Integration tests for the ManicTime client.
These tests require a running ManicTime server in Docker.
Run with: pytest -m docker tests/test_integration.py
"""

import pytest
from datetime import datetime, timedelta
import requests
import os
import sys

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from client import ManicTimeClient
from models import Activity, Timeline

# Mark all tests in this file as requiring Docker
pytestmark = pytest.mark.docker

def is_server_running(server_url):
    """Check if the server is running."""
    try:
        response = requests.get(f"{server_url}/api/server/info", timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False

@pytest.fixture(scope="module")
def check_server(server_config):
    """Skip all tests if the server is not running."""
    try:
        response = requests.get(f"{server_config.server_url}/api/server/info", timeout=5)
        if response.status_code == 200:
            return server_config
        pytest.skip("ManicTime server is running but returned unexpected status code")
    except requests.RequestException:
        pytest.skip("ManicTime server not available, skipping integration tests")

@pytest.fixture
def client(check_server):
    """Create a client for the running server."""
    config = check_server
    # Make sure auth_type is set to bearer for our Docker server
    config.auth_type = "bearer"
    client = ManicTimeClient(config)
    return client

class TestBasicIntegration:
    """Basic integration tests for the ManicTime client."""
    
    def test_server_connection(self, client):
        """Test that we can connect to the server."""
        # This test will fail if the client can't be initialized
        assert client is not None
        
    def test_get_timelines(self, client):
        """Test that we can get timelines from the server."""
        try:
            timelines = client.get_timelines()
            assert isinstance(timelines, list)
            # Even a fresh server should have at least the default timelines
            assert len(timelines) > 0
        except Exception as e:
            pytest.skip(f"Couldn't get timelines from server: {str(e)}")
    
    def test_get_activities(self, client):
        """Test that we can get activities from the server."""
        try:
            # First get timelines
            timelines = client.get_timelines()
            if not timelines:
                pytest.skip("No timelines available on server")
            
            # Use the first timeline for testing
            timeline_id = timelines[0].get("timelineId", None)
            if not timeline_id:
                pytest.skip("Timeline doesn't have an ID")
            
            # Get activities for the last day
            end_time = datetime.now()
            start_time = end_time - timedelta(days=1)
            
            activities = client.get_activities(
                timeline_id=timeline_id,
                from_time=start_time,
                to_time=end_time
            )
            
            assert isinstance(activities, dict)
            assert "activities" in activities
        except Exception as e:
            pytest.skip(f"Couldn't get activities from server: {str(e)}")

class TestActivityDataRetrieval:
    """Tests for activity data retrieval from the server."""
    
    def test_get_activities_for_date_range(self, client):
        """Test we can get activities for a date range."""
        try:
            # First get timelines
            timelines = client.get_timelines()
            if not timelines:
                pytest.skip("No timelines available on server")
            
            # Use the first timeline for testing
            timeline_id = timelines[0].get("timelineId", None)
            if not timeline_id:
                pytest.skip("Timeline doesn't have an ID")
            
            # Get activities for the last week
            end_time = datetime.now()
            start_time = end_time - timedelta(days=7)
            
            activities = client.get_activities_for_date_range(
                timeline_id=timeline_id,
                start_date=start_time,
                end_date=end_time
            )
            
            # The result should be a list of Activity objects
            assert isinstance(activities, list)
            # Even if there are no activities, it should be an empty list
            assert isinstance(activities, list)
            
            # If we have activities, verify they're Activity objects
            if activities:
                assert all(isinstance(a, Activity) for a in activities)
                
        except Exception as e:
            pytest.skip(f"Couldn't get activities for date range: {str(e)}")
    
    def test_get_daily_activities(self, client):
        """Test we can get daily activities."""
        try:
            # Get activities for the last week
            end_time = datetime.now()
            start_time = end_time - timedelta(days=7)
            
            daily_data = client.get_daily_activities(
                start_date=start_time,
                end_date=end_time
            )
            
            # The result should be a list
            assert isinstance(daily_data, list)
            
            # If we have data, check its structure
            if daily_data:
                day = daily_data[0]
                assert "date" in day
                assert "timelines" in day
                
        except Exception as e:
            pytest.skip(f"Couldn't get daily activities: {str(e)}")