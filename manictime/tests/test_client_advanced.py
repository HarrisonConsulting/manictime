"""
Additional tests for the ManicTimeClient to improve coverage.
"""

import pytest
import requests
from datetime import datetime, timedelta
import os
import sys
from unittest.mock import patch, MagicMock

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from client import ManicTimeClient
from config import Config
from models import Activity, Timeline, TagCombination
from exceptions import ManicTimeClientError, AuthenticationError, NotFoundError

class TestClientAdvanced:
    """Additional tests for ManicTimeClient to improve coverage."""
    
    def test_setup_ntlm_authentication(self, mocker):
        """Test NTLM authentication setup."""
        config = Config(
            server_url="http://example.com",
            auth_type="ntlm",
            username="user",
            password="pass",
            domain="domain"
        )
        
        # Create a mock session
        mock_session = mocker.MagicMock()
        
        # Patch the _create_session method to return our mock session
        mocker.patch.object(ManicTimeClient, '_create_session', return_value=mock_session)
        
        # Create the client which will call _setup_authentication
        client = ManicTimeClient(config)
        
        # Check that the HttpNtlmAuth was set up correctly
        assert client.session.auth is not None
        
    def test_setup_bearer_auth_with_token(self, mocker):
        """Test bearer authentication setup with token."""
        config = Config(
            server_url="http://example.com",
            auth_type="bearer",
            token="test-token"
        )
        
        # Create a mock session with a real headers dict
        mock_session = mocker.MagicMock()
        mock_session.headers = {}
        
        # Patch the _create_session method to return our mock session
        mocker.patch.object(ManicTimeClient, '_create_session', return_value=mock_session)
        
        # Create the client which will call _setup_authentication
        client = ManicTimeClient(config)
        
        # Check that the Authorization header was set correctly
        assert client.session.headers['Authorization'] == 'Bearer test-token'
        
    def test_auth_error_with_no_credentials(self, mocker):
        """Test authentication error with no credentials."""
        config = Config(
            server_url="http://example.com",
            auth_type="bearer"
            # No username/password or token
        )
        
        # Create a mock session
        mock_session = mocker.MagicMock()
        
        # Patch the _create_session method to return our mock session
        mocker.patch.object(ManicTimeClient, '_create_session', return_value=mock_session)
        
        # Test that calling _setup_authentication directly raises AuthenticationError
        client = ManicTimeClient.__new__(ManicTimeClient)  # Create without __init__
        client.config = config
        client.session = mock_session
        
        with pytest.raises(AuthenticationError):
            client._setup_authentication()
        
    def test_activities_processing(self, mock_client, mocker):
        """Test processing of activities."""
        # Mock a response from the activities endpoint
        activities_response = {
            "activities": [
                {
                    "start": "2023-01-01T09:00:00",
                    "end": "2023-01-01T10:00:00",
                    "title": "Test Activity",
                    "application": "Test App"
                }
            ]
        }
        
        # Mock the get_activities method to return our test data
        mocker.patch.object(mock_client, 'get_activities', return_value=activities_response)
        
        # Call the method
        result = mock_client.get_activities_for_date_range(
            "test-timeline",
            datetime(2023, 1, 1),
            datetime(2023, 1, 2)
        )
        
        # Verify the activity was processed correctly
        assert len(result) == 1
        assert result[0].title == "Test Activity"
        assert result[0].application == "Test App"
        assert result[0].start == datetime(2023, 1, 1, 9, 0)
        assert result[0].end == datetime(2023, 1, 1, 10, 0)
        assert result[0].duration.total_seconds() == 3600  # 1 hour
        
    def test_get_all_timeline_activities(self, mock_client, mocker):
        """Test getting activities for all timelines."""
        # Mock the get_timelines method
        mocker.patch.object(mock_client, 'get_timelines', return_value=[
            {"timelineId": "timeline1", "name": "Timeline 1"},
            {"timelineId": "timeline2", "name": "Timeline 2"}
        ])
        
        # Create fake activities for each timeline
        activities1 = [
            {
                "start": "2023-01-01T09:00:00",
                "end": "2023-01-01T10:00:00",
                "title": "Activity 1",
                "application": "App 1"
            }
        ]
        
        activities2 = [
            {
                "start": "2023-01-01T11:00:00",
                "end": "2023-01-01T12:00:00",
                "title": "Activity 2",
                "application": "App 2"
            }
        ]
        
        # Mock get_activities_for_date_range to return different activities for each timeline
        def mock_get_activities(timeline_id, start_date, end_date):
            if timeline_id == "timeline1":
                return [Activity(
                    start=datetime(2023, 1, 1, 9, 0),
                    end=datetime(2023, 1, 1, 10, 0),
                    title="Activity 1",
                    application="App 1"
                )]
            elif timeline_id == "timeline2":
                return [Activity(
                    start=datetime(2023, 1, 1, 11, 0),
                    end=datetime(2023, 1, 1, 12, 0),
                    title="Activity 2",
                    application="App 2"
                )]
            return []
            
        mocker.patch.object(mock_client, 'get_activities_for_date_range', side_effect=mock_get_activities)
        
        # Call the method
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 2)
        result = mock_client.get_all_timeline_activities(start_date, end_date)
        
        # Verify the result
        assert len(result) == 2
        assert "timeline1" in result
        assert "timeline2" in result
        assert len(result["timeline1"]) == 1
        assert len(result["timeline2"]) == 1
        assert result["timeline1"][0].title == "Activity 1"
        assert result["timeline2"][0].title == "Activity 2"
        
    def test_get_daily_activities(self, mock_client, mocker):
        """Test getting daily activities."""
        # Mock get_all_timeline_activities
        timeline_activities = {
            "timeline1": [
                Activity(
                    start=datetime(2023, 1, 1, 9, 0),
                    end=datetime(2023, 1, 1, 10, 0),
                    title="Activity 1 Day 1",
                    application="App 1"
                ),
                Activity(
                    start=datetime(2023, 1, 2, 9, 0),
                    end=datetime(2023, 1, 2, 10, 0),
                    title="Activity 1 Day 2",
                    application="App 1"
                )
            ],
            "timeline2": [
                Activity(
                    start=datetime(2023, 1, 1, 11, 0),
                    end=datetime(2023, 1, 1, 12, 0),
                    title="Activity 2 Day 1",
                    application="App 2"
                )
            ]
        }
        
        mocker.patch.object(mock_client, 'get_all_timeline_activities', return_value=timeline_activities)
        
        # Call the method
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 3)
        result = mock_client.get_daily_activities(start_date, end_date)
        
        # Verify the result
        assert len(result) == 2  # Two days with activities
        
        # Check day 1
        assert result[0]["date"] == "2023-01-01"
        assert len(result[0]["timelines"]) == 2  # Two timelines on day 1
        assert len(result[0]["timelines"]["timeline1"]["activities"]) == 1
        assert result[0]["timelines"]["timeline1"]["activities"][0]["title"] == "Activity 1 Day 1"
        assert result[0]["timelines"]["timeline1"]["total_seconds"] == 3600  # 1 hour
        
        # Check day 2
        assert result[1]["date"] == "2023-01-02"
        assert len(result[1]["timelines"]) == 1  # One timeline on day 2
        assert len(result[1]["timelines"]["timeline1"]["activities"]) == 1
        assert result[1]["timelines"]["timeline1"]["activities"][0]["title"] == "Activity 1 Day 2"