"""
Tests for the data models.
"""

import pytest
from datetime import datetime, timedelta
import os
import sys
import json

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models import Activity, Timeline, TagCombination

class TestActivity:
    """Tests for the Activity class."""
    
    def test_create_activity(self):
        """Test creating an Activity object directly."""
        start = datetime(2023, 1, 1, 10, 0)
        end = datetime(2023, 1, 1, 11, 0)
        
        activity = Activity(
            start=start,
            end=end,
            title="Test Activity",
            application="Test App",
            notes="Some notes",
            tags=["tag1", "tag2"]
        )
        
        # Verify properties
        assert activity.start == start
        assert activity.end == end
        assert activity.title == "Test Activity"
        assert activity.application == "Test App"
        assert activity.notes == "Some notes"
        assert activity.tags == ["tag1", "tag2"]
        
        # Verify duration was calculated
        assert activity.duration == timedelta(hours=1)
        assert activity.duration.total_seconds() == 3600
    
    def test_from_dict(self):
        """Test creating an Activity from a dictionary."""
        data = {
            "start": "2023-01-01T10:00:00",
            "end": "2023-01-01T11:30:00",
            "title": "Dict Activity",
            "application": "Dict App",
            "notes": "Dict notes",
            "tags": ["tag3", "tag4"]
        }
        
        activity = Activity.from_dict(data)
        
        # Verify properties
        assert activity.start == datetime(2023, 1, 1, 10, 0)
        assert activity.end == datetime(2023, 1, 1, 11, 30)
        assert activity.title == "Dict Activity"
        assert activity.application == "Dict App"
        assert activity.notes == "Dict notes"
        assert activity.tags == ["tag3", "tag4"]
        
        # Verify duration was calculated
        assert activity.duration.total_seconds() == 5400  # 1.5 hours
    
    def test_from_dict_minimal(self):
        """Test creating an Activity with minimal data."""
        data = {
            "start": "2023-01-01T10:00:00",
            "end": "2023-01-01T10:30:00"
        }
        
        activity = Activity.from_dict(data)
        
        # Verify required properties
        assert activity.start == datetime(2023, 1, 1, 10, 0)
        assert activity.end == datetime(2023, 1, 1, 10, 30)
        
        # Verify optional properties have defaults
        assert activity.title == ""
        assert activity.application == ""
        assert activity.notes is None
        assert activity.tags == []
        
        # Verify duration was calculated
        assert activity.duration.total_seconds() == 1800  # 30 minutes

class TestTimeline:
    """Tests for the Timeline class."""
    
    def test_create_timeline(self):
        """Test creating a Timeline object directly."""
        timeline = Timeline(
            id="timeline-123",
            name="Test Timeline",
            description="A test timeline",
            tags=["timeline-tag1", "timeline-tag2"]
        )
        
        # Verify properties
        assert timeline.id == "timeline-123"
        assert timeline.name == "Test Timeline"
        assert timeline.description == "A test timeline"
        assert timeline.tags == ["timeline-tag1", "timeline-tag2"]
    
    def test_from_dict(self):
        """Test creating a Timeline from a dictionary."""
        data = {
            "timelineId": "dict-timeline-456",
            "name": "Dict Timeline",
            "description": "A timeline from dict",
            "tags": ["dict-tag1", "dict-tag2"]
        }
        
        timeline = Timeline.from_dict(data)
        
        # Verify properties
        assert timeline.id == "dict-timeline-456"
        assert timeline.name == "Dict Timeline"
        assert timeline.description == "A timeline from dict"
        assert timeline.tags == ["dict-tag1", "dict-tag2"]
    
    def test_from_dict_minimal(self):
        """Test creating a Timeline with minimal data."""
        data = {
            "timelineId": "minimal-timeline",
            "name": "Minimal Timeline"
        }
        
        timeline = Timeline.from_dict(data)
        
        # Verify required properties
        assert timeline.id == "minimal-timeline"
        assert timeline.name == "Minimal Timeline"
        
        # Verify optional properties have defaults
        assert timeline.description is None
        assert timeline.tags == []

class TestTagCombination:
    """Tests for the TagCombination class."""
    
    def test_create_tag_combination(self):
        """Test creating a TagCombination object directly."""
        tag_combo = TagCombination(
            name="Test Combo",
            tags=["combo-tag1", "combo-tag2"],
            description="A test tag combination",
            color="#FF5733"
        )
        
        # Verify properties
        assert tag_combo.name == "Test Combo"
        assert tag_combo.tags == ["combo-tag1", "combo-tag2"]
        assert tag_combo.description == "A test tag combination"
        assert tag_combo.color == "#FF5733"
    
    def test_from_dict(self):
        """Test creating a TagCombination from a dictionary."""
        data = {
            "name": "Dict Combo",
            "tags": ["dict-tag1", "dict-tag2"],
            "description": "A combo from dict",
            "color": "#33FF57"
        }
        
        tag_combo = TagCombination.from_dict(data)
        
        # Verify properties
        assert tag_combo.name == "Dict Combo"
        assert tag_combo.tags == ["dict-tag1", "dict-tag2"]
        assert tag_combo.description == "A combo from dict"
        assert tag_combo.color == "#33FF57"
    
    def test_from_dict_minimal(self):
        """Test creating a TagCombination with minimal data."""
        data = {
            "name": "Minimal Combo",
        }
        
        tag_combo = TagCombination.from_dict(data)
        
        # Verify required properties
        assert tag_combo.name == "Minimal Combo"
        
        # Verify optional properties have defaults
        assert tag_combo.tags == []
        assert tag_combo.description is None
        assert tag_combo.color is None