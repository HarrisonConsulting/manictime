import pytest
from datetime import datetime, timedelta
from manictime.client import ManicTimeClient
from manictime.config import Config 
from manictime.exceptions import ManicTimeClientError
from manictime.models import Activity

def test_config_validation():
    config = Config()
    config.server_url = None
    with pytest.raises(ValueError):
        config.validate()

def test_client_initialization():
    config = Config()
    config.server_url = "http://localhost:8080"
    config.auth_type = "bearer"
    config.token = "test_token"
    
    client = ManicTimeClient(config)
    assert client.session.headers["Authorization"] == "Bearer test_token"

def test_get_activities():
    config = Config()
    config.server_url = "http://localhost:8080"
    client = ManicTimeClient(config)
    
    from_time = datetime.now() - timedelta(days=1)
    to_time = datetime.now()
    
    activities = client.get_activities(
        "test_timeline",
        from_time,
        to_time
    )
    assert isinstance(activities, dict)

def test_get_timelines(mocker):
    config = Config()
    client = ManicTimeClient(config)
    mocker.patch.object(client, '_make_request', return_value=[{"timelineId": "1", "name": "Test Timeline"}])
    timelines = client.get_timelines()
    assert len(timelines) == 1
    assert timelines[0]["timelineId"] == "1"

def test_get_tag_combinations(mocker):
    config = Config()
    client = ManicTimeClient(config)
    mocker.patch.object(client, '_make_request', return_value=[{"id": "1", "tags": ["tag1", "tag2"]}])
    tags = client.get_tag_combinations()
    assert len(tags) == 1
    assert tags[0]["id"] == "1"
    
def test_get_daily_activities(mocker):
    """Test getting daily activities with timeline data organized by day"""
    config = Config()
    config.server_url = "http://localhost:8080"
    client = ManicTimeClient(config)
    
    # Mock the get_all_timeline_activities method
    activities = {
        "timeline1": [
            Activity(
                start=datetime(2023, 1, 1, 10, 0),
                end=datetime(2023, 1, 1, 11, 0),
                title="Activity 1",
                application="App 1"
            ),
            Activity(
                start=datetime(2023, 1, 2, 9, 0),
                end=datetime(2023, 1, 2, 10, 0),
                title="Activity 3",
                application="App 1"
            )
        ],
        "timeline2": [
            Activity(
                start=datetime(2023, 1, 1, 14, 0),
                end=datetime(2023, 1, 1, 15, 0),
                title="Activity 2",
                application="App 2"
            )
        ]
    }
    
    mocker.patch.object(client, 'get_all_timeline_activities', return_value=activities)
    
    # Call the method
    result = client.get_daily_activities(
        datetime(2023, 1, 1),
        datetime(2023, 1, 2)
    )
    
    # Verify results
    assert len(result) == 2  # Two days with data
    
    # Check first day
    assert result[0]["date"] == "2023-01-01"
    assert len(result[0]["timelines"]) == 2  # Two timelines
    assert len(result[0]["timelines"]["timeline1"]["activities"]) == 1
    assert len(result[0]["timelines"]["timeline2"]["activities"]) == 1
    
    # Check second day
    assert result[1]["date"] == "2023-01-02"
    assert len(result[1]["timelines"]) == 1  # One timeline
    assert len(result[1]["timelines"]["timeline1"]["activities"]) == 1
    
    # Check totals
    assert result[0]["timelines"]["timeline1"]["total_seconds"] == 3600
    assert result[0]["timelines"]["timeline2"]["total_seconds"] == 3600