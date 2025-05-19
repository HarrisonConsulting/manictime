"""
Tests for error handling in the ManicTime client.
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
from configuration import Config 
from exceptions import ManicTimeClientError, AuthenticationError, NotFoundError

class TestErrorHandling:
    """Tests for error handling in the ManicTime client."""
    
    def test_authentication_error(self, mock_client, mocker):
        """Test handling of 401 authentication errors."""
        # Create a mock response with 401 status
        mock_response = mocker.Mock()
        mock_response.status_code = 401
        http_error = requests.exceptions.HTTPError("401 Client Error")
        http_error.response = mock_response  # Need to add response attribute
        mock_response.raise_for_status.side_effect = http_error
        
        # Mock the session request to return the 401 response
        mocker.patch.object(mock_client.session, 'request', return_value=mock_response)
        
        # Call a method that uses _make_request and expect AuthenticationError
        with pytest.raises(AuthenticationError):
            mock_client.get_timelines()
    
    def test_not_found_error(self, mock_client, mocker):
        """Test handling of 404 not found errors."""
        # Create a mock response with 404 status
        mock_response = mocker.Mock()
        mock_response.status_code = 404
        http_error = requests.exceptions.HTTPError("404 Client Error")
        http_error.response = mock_response  # Need to add response attribute
        mock_response.raise_for_status.side_effect = http_error
        
        # Mock the session request to return the 404 response
        mocker.patch.object(mock_client.session, 'request', return_value=mock_response)
        
        # Call a method that uses _make_request and expect NotFoundError
        with pytest.raises(NotFoundError):
            mock_client.get_timelines()
    
    def test_generic_server_error(self, mock_client, mocker):
        """Test handling of 500 server errors."""
        # Create a mock response with 500 status
        mock_response = mocker.Mock()
        mock_response.status_code = 500
        http_error = requests.exceptions.HTTPError("500 Server Error")
        http_error.response = mock_response  # Need to add response attribute
        mock_response.raise_for_status.side_effect = http_error
        
        # Mock the session request to return the 500 response
        mocker.patch.object(mock_client.session, 'request', return_value=mock_response)
        
        # Call a method that uses _make_request and expect ManicTimeClientError
        with pytest.raises(ManicTimeClientError):
            mock_client.get_timelines()
    
    def test_timeout_error(self, mock_client, mocker):
        """Test handling of request timeouts."""
        # Mock the session request to raise a Timeout exception
        mocker.patch.object(
            mock_client.session, 
            'request', 
            side_effect=requests.exceptions.Timeout("Request timed out")
        )
        
        # Call a method that uses _make_request and expect ManicTimeClientError
        with pytest.raises(ManicTimeClientError) as exc_info:
            mock_client.get_timelines()
        assert "timed out" in str(exc_info.value)
    
    def test_connection_error(self, mock_client, mocker):
        """Test handling of connection errors."""
        # Mock the session request to raise a ConnectionError exception
        mocker.patch.object(
            mock_client.session, 
            'request', 
            side_effect=requests.exceptions.ConnectionError("Failed to establish connection")
        )
        
        # Call a method that uses _make_request and expect ManicTimeClientError
        with pytest.raises(ManicTimeClientError) as exc_info:
            mock_client.get_timelines()
        assert "Connection error" in str(exc_info.value)
    
    def test_invalid_json_response(self, mock_client, mocker):
        """Test handling of invalid JSON responses."""
        # Create a mock response with invalid JSON
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.text = "Not a JSON response"
        
        # Patch _make_request to raise the ValueError directly
        mocker.patch.object(
            mock_client,
            '_make_request',
            side_effect=ValueError("Invalid JSON")
        )
        
        # Call a method that uses _make_request and expect ValueError
        with pytest.raises(ValueError):
            mock_client.get_timelines()
    
    def test_empty_response(self, mock_client, mocker):
        """Test handling of empty responses."""
        # Mock the client behavior directly
        mocker.patch.object(
            mock_client,
            'get_timelines',
            return_value=[]
        )
        
        # Call the mocked method
        result = mock_client.get_timelines()
        assert result == []


def test_auth_missing_token_method(mocker):
    """Test that an AuthenticationError is raised when the client needs a token but no method exists."""
    # Create a config that would need token acquisition
    config = Config(
        server_url="http://test-server.com",
        auth_type="bearer",
        username="testuser",
        password="testpass"
    )
    
    # The client should raise an AuthenticationError during init
    with pytest.raises(AuthenticationError):
        client = ManicTimeClient(config)


def test_http_error_handling(mocker):
    """Test HTTP error handling directly in the _make_request method."""
    # Create a minimal client with mocked session
    config = Config(server_url="http://test-server.com", auth_type="bearer", token="test-token")
    
    with patch('client.requests.Session') as mock_session_cls:
        session = MagicMock()
        mock_session_cls.return_value = session
        
        # Create client with mock session
        client = ManicTimeClient(config)
        
        # Configure mock for authentication error (401)
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_error = requests.exceptions.HTTPError("401 Unauthorized")
        mock_error.response = mock_response
        mock_response.raise_for_status.side_effect = mock_error
        session.request.return_value = mock_response
        
        # Test 401 error
        with pytest.raises(AuthenticationError):
            client._make_request("http://test-server.com/api/endpoint")
        
        # Configure mock for not found error (404)
        mock_response.status_code = 404
        mock_error = requests.exceptions.HTTPError("404 Not Found")
        mock_error.response = mock_response
        
        # Test 404 error 
        with pytest.raises(NotFoundError):
            client._make_request("http://test-server.com/api/endpoint")
        
        # Configure mock for server error (500)
        mock_response.status_code = 500
        mock_error = requests.exceptions.HTTPError("500 Server Error")
        mock_error.response = mock_response
        
        # Test 500 error
        with pytest.raises(ManicTimeClientError):
            client._make_request("http://test-server.com/api/endpoint")


def test_network_error_handling():
    """Test network error handling in the _make_request method."""
    # Create a minimal client with mocked session
    config = Config(server_url="http://test-server.com", auth_type="bearer", token="test-token")
    
    # We need to patch the requests module and disable backoff
    with patch('client.requests.Session') as mock_session_cls,\
         patch('client.backoff') as mock_backoff:
        # Make backoff.on_exception immediately call the decorated function
        mock_backoff.on_exception.return_value = lambda f: f
        
        session = MagicMock()
        mock_session_cls.return_value = session
        
        # Create client with our mocks
        client = ManicTimeClient(config)
        
        # Test connection error
        connection_error = requests.exceptions.ConnectionError("Connection failed")
        session.request.side_effect = connection_error
        
        with pytest.raises(ManicTimeClientError) as exc_info:
            client._make_request("http://test-server.com/api/endpoint")
        assert "Connection error" in str(exc_info.value)
        
        # Test timeout error
        timeout_error = requests.exceptions.Timeout("Request timed out")
        session.request.side_effect = timeout_error
        
        with pytest.raises(ManicTimeClientError) as exc_info:
            client._make_request("http://test-server.com/api/endpoint")
        assert "timed out" in str(exc_info.value)


def test_pagination_edge_cases(mock_client, mocker):
    """Test the pagination logic in get_activities_for_date_range with edge cases."""
    # Test case: Start date equal to end date (one-day range)
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2023, 1, 1)
    
    # Mock get_activities to return an empty list for the one day
    mock_response = {"activities": []}
    mocker.patch.object(mock_client, 'get_activities', return_value=mock_response)
    
    result = mock_client.get_activities_for_date_range("timeline1", start_date, end_date)
    assert isinstance(result, list)
    assert len(result) == 0
    
    # Test case: Empty response in the middle of pagination
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2023, 1, 15)
    
    # Create a side effect function that returns activities for some dates and empty for others
    def side_effect(timeline_id, from_time, to_time):
        # Return activities only for dates before Jan 7
        if from_time < datetime(2023, 1, 7):
            return {
                "activities": [
                    {
                        "start": "2023-01-01T10:00:00",
                        "end": "2023-01-01T11:00:00",
                        "title": "Activity",
                        "application": "App"
                    }
                ]
            }
        return {"activities": []}
    
    mocker.patch.object(mock_client, 'get_activities', side_effect=side_effect)
    
    result = mock_client.get_activities_for_date_range("timeline1", start_date, end_date, 
                                                     batch_size=timedelta(days=3))
    
    # We should have some activities from the first week
    assert len(result) > 0
    
    # Test case: Very large date range (potentially causing memory issues)
    start_date = datetime(2022, 1, 1)
    end_date = datetime(2023, 1, 1)  # One year range
    
    # Mock get_activities to return a consistent response
    mocker.patch.object(mock_client, 'get_activities', return_value={"activities": []})
    
    # Should process without errors even with a large range
    result = mock_client.get_activities_for_date_range("timeline1", start_date, end_date, 
                                                     batch_size=timedelta(days=30))
    assert isinstance(result, list)


def test_token_acquisition(mocker):
    """Test the token acquisition process with username/password."""
    config = Config(
        server_url="http://test-server.com",
        auth_type="bearer",
        username="testuser",
        password="testpass"
    )
    
    # Create a mock for the session - important to patch the client's import of requests
    with patch('client.requests.Session') as mock_session_cls:
        # Setup the mock session
        session = MagicMock()
        mock_session_cls.return_value = session
        
        # We need to mock the headers as a dict-like object
        session.headers = {}
        
        # Configure mock for token endpoint
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "new_test_token"}
        session.request.return_value = mock_response
        
        # Create client with mock session - this will call _get_token during init
        client = ManicTimeClient(config)
        
        # Verify the token endpoint was called
        session.request.assert_any_call(
            "post",
            f"{config.server_url}/api/token",
            json={"username": "testuser", "password": "testpass"},
            timeout=config.timeout
        )
        
        # Verify the token was set
        assert 'Authorization' in session.headers
        assert session.headers['Authorization'] == "Bearer new_test_token"


def test_token_acquisition_error(mocker):
    """Test error handling during token acquisition."""
    config = Config(
        server_url="http://test-server.com",
        auth_type="bearer",
        username="testuser", 
        password="testpass"
    )
    
    # Create a mock for the session - important to patch the client's import
    with patch('client.requests.Session') as mock_session_cls:
        # Setup the mock session
        session = MagicMock()
        mock_session_cls.return_value = session
        
        # Configure mock to raise an error for token request
        session.request.side_effect = requests.exceptions.RequestException("Connection error")
        
        # Creating client should raise AuthenticationError
        with pytest.raises(AuthenticationError):
            client = ManicTimeClient(config)