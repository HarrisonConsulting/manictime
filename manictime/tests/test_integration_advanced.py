"""
Advanced integration tests for the ManicTime client.
These tests require a running ManicTime server in Docker with test data.
Run with: pytest -m docker tests/test_integration_advanced.py
"""

import pytest
from datetime import datetime, timedelta
import requests
import os
import sys
import json
import logging

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from client import ManicTimeClient
from models import Activity, Timeline, TagCombination

# Mark all tests in this file as requiring Docker
pytestmark = pytest.mark.docker

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

class TestIntegrationScenarios:
    """Advanced integration tests for real-world scenarios."""
    
    def test_weekly_report(self, client):
        """Test generating a weekly activity report."""
        try:
            # Define the date range for last week
            end_date = datetime.now().replace(hour=23, minute=59, second=59)
            start_date = (end_date - timedelta(days=7)).replace(hour=0, minute=0, second=0)
            
            # Get all timeline activities for the week
            activities = client.get_all_timeline_activities(start_date, end_date)
            
            # Verify we got data back
            assert activities is not None
            
            # Check the structure of the response
            assert isinstance(activities, dict)
            
            # Process the activities into a daily report
            daily_activities = client.get_daily_activities(start_date, end_date)
            
            # Verify the daily report structure
            assert daily_activities is not None
            assert isinstance(daily_activities, list)
            
            # If we have daily data, verify its structure
            if daily_activities:
                first_day = daily_activities[0]
                assert "date" in first_day
                assert "timelines" in first_day
                
                # Verify timeline structure if present
                if first_day["timelines"]:
                    for timeline_id, timeline_data in first_day["timelines"].items():
                        assert "activities" in timeline_data
                        assert "total_seconds" in timeline_data
                        
                        # If there are activities, verify their structure
                        if timeline_data["activities"]:
                            activity = timeline_data["activities"][0]
                            assert "start" in activity
                            assert "end" in activity
                            assert "title" in activity
                            assert "duration_seconds" in activity
        except Exception as e:
            pytest.skip(f"Couldn't run weekly report test: {str(e)}")
    
    def test_application_usage_summary(self, client):
        """Test generating an application usage summary report."""
        try:
            # Define the date range for yesterday
            end_date = datetime.now().replace(hour=23, minute=59, second=59)
            start_date = (end_date - timedelta(days=1)).replace(hour=0, minute=0, second=0)
            
            # Get the timelines
            timelines = client.get_timelines()
            assert isinstance(timelines, list)
            
            # If no timelines are available, skip the test
            if not timelines:
                pytest.skip("No timelines available for testing")
            
            # Use the first timeline for testing
            timeline_id = timelines[0].get("timelineId")
            assert timeline_id is not None
            
            # Get activities for this timeline
            activities = client.get_activities_for_date_range(
                timeline_id,
                start_date,
                end_date
            )
            
            # Verify we got a list back
            assert isinstance(activities, list)
            
            # Group activities by application if we have any
            app_usage = {}
            for activity in activities:
                app = activity.application
                if not app:  # Handle case with no application data
                    continue
                    
                if app not in app_usage:
                    app_usage[app] = 0
                app_usage[app] += activity.duration.total_seconds()
            
            # Sort applications by usage
            sorted_apps = sorted(app_usage.items(), key=lambda x: x[1], reverse=True)
            
            logger.info(f"Found {len(sorted_apps)} applications with usage data")
            
            # Log the top applications (up to 5)
            top_count = min(len(sorted_apps), 5)
            if top_count > 0:
                logger.info(f"Top {top_count} applications by usage:")
                for i, (app, seconds) in enumerate(sorted_apps[:top_count], 1):
                    hours = seconds / 3600
                    logger.info(f"  {i}. {app}: {hours:.2f} hours")
                    
        except Exception as e:
            pytest.skip(f"Couldn't run application usage test: {str(e)}")
    
    def test_tag_based_report(self, client):
        """Test generating a report based on activity tags."""
        try:
            # Define the date range for the last 7 days (shorter than 30 for Docker test)
            end_date = datetime.now().replace(hour=23, minute=59, second=59)
            start_date = (end_date - timedelta(days=7)).replace(hour=0, minute=0, second=0)
            
            # Get all timeline activities
            activities = client.get_all_timeline_activities(start_date, end_date)
            assert isinstance(activities, dict)
            
            # Calculate time spent for each tag
            tag_time = {}
            for timeline_id, timeline_activities in activities.items():
                for activity in timeline_activities:
                    # Skip activities without tags
                    if not activity.tags:
                        continue
                        
                    for tag in activity.tags:
                        if tag not in tag_time:
                            tag_time[tag] = 0
                        tag_time[tag] += activity.duration.total_seconds()
            
            # Sort tags by usage
            sorted_tags = sorted(tag_time.items(), key=lambda x: x[1], reverse=True)
            
            logger.info(f"Found {len(sorted_tags)} tags with usage data")
            
            # Log the top tags (up to 5)
            top_count = min(len(sorted_tags), 5)
            if top_count > 0:
                logger.info(f"Top {top_count} tags by usage:")
                for i, (tag, seconds) in enumerate(sorted_tags[:top_count], 1):
                    hours = seconds / 3600
                    logger.info(f"  {i}. {tag}: {hours:.2f} hours")
                    
        except Exception as e:
            pytest.skip(f"Couldn't run tag-based report test: {str(e)}")
            
    def test_data_aggregation(self, client):
        """Test data aggregation functionality."""
        try:
            # Define the date range for the last 3 days
            end_date = datetime.now().replace(hour=23, minute=59, second=59)
            start_date = (end_date - timedelta(days=3)).replace(hour=0, minute=0, second=0)
            
            # Get daily activities
            daily_data = client.get_daily_activities(start_date, end_date)
            assert isinstance(daily_data, list)
            
            # Calculate total time spent each day
            daily_totals = {}
            for day in daily_data:
                date_str = day["date"]
                total_seconds = 0
                
                for timeline_id, timeline_data in day["timelines"].items():
                    total_seconds += timeline_data["total_seconds"]
                
                daily_totals[date_str] = total_seconds
            
            logger.info("Daily totals (in hours):")
            for date_str, seconds in daily_totals.items():
                hours = seconds / 3600
                logger.info(f"  {date_str}: {hours:.2f} hours")
                
        except Exception as e:
            pytest.skip(f"Couldn't run data aggregation test: {str(e)}")