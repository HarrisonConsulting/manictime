from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging

# Set up logging
logger = logging.getLogger(__name__)

@dataclass
class Timeline:
    """Represents a ManicTime timeline"""
    id: str
    name: str
    description: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Timeline":
        """Create Timeline from API response dict"""
        return cls(
            id=data.get("timelineId", ""),
            name=data.get("name", ""),
            description=data.get("description"),
            tags=data.get("tags", [])
        )

@dataclass 
class Activity:
    """Represents a ManicTime activity"""
    start: datetime
    end: datetime
    title: str
    application: str
    # Add id field with default empty string
    id: str = ""
    duration: Optional[timedelta] = None
    notes: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    groupId: Optional[int] = None
    
    def __post_init__(self):
        """Calculate duration after initialization"""
        if not self.duration and self.start and self.end:
            self.duration = self.end - self.start
            
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Activity":
        """Create Activity from the standardized activity data format
        
        Expected fields in data:
        - id: Activity unique identifier
        - start: ISO formatted start time string
        - end: ISO formatted end time string
        - title: Activity title/name
        - application: Application name (optional)
        - duration: Duration in seconds (optional)
        - tags: List of tag strings
        - notes: Activity notes (optional)
        - groupId: Group ID (optional)
        """
        # Add detailed logging to diagnose what data is being passed
        logger.info(f"Activity.from_dict data: {data}")
        # Log the data keys specifically to see what fields are available
        if isinstance(data, dict):
            logger.info(f"Activity data keys: {list(data.keys())}")
            logger.info(f"Activity ID: {data.get('id', 'MISSING')}")
            logger.info(f"Activity entityId: {data.get('entityId', 'MISSING')}")
            
        if not isinstance(data, dict):
            logger.warning(f"Activity.from_dict received non-dict data: {type(data)}")
            # Return an empty activity with placeholder values to avoid errors
            return cls(
                start=datetime.now(),
                end=datetime.now(),
                title="Invalid Data",
                application="",
                notes="",
                tags=[]
            )
        
        # Parse start time from ISO format
        start_str = data.get("start", "")
        try:
            from dateutil import parser
            start_time = parser.parse(start_str)
        except Exception as e:
            logger.warning(f"Failed to parse start time '{start_str}': {str(e)}")
            start_time = datetime.now()
        
        # Parse end time from ISO format
        end_str = data.get("end", "")
        try:
            from dateutil import parser
            end_time = parser.parse(end_str)
        except Exception as e:
            logger.warning(f"Failed to parse end time '{end_str}': {str(e)}")
            # Calculate from duration or use default
            duration_seconds = data.get("duration", 0)
            if duration_seconds:
                end_time = start_time + timedelta(seconds=duration_seconds)
            else:
                end_time = start_time + timedelta(minutes=1)  # Default duration
        
        # Get basic fields
        title = data.get("title", "")
        application = data.get("application", "")
        notes = data.get("notes", "")
        
        # Get tags (always as a list)
        tags = data.get("tags", [])
        if not isinstance(tags, list):
            tags = [tags] if tags else []
        
        # Get ID field - critical for activity identification
        activity_id = data.get("id", "")
        entity_id = data.get("entityId")
        
        # If ID is not present or empty, try to use entityId
        if not activity_id and entity_id is not None:
            activity_id = str(entity_id)
            
        # Log the ID for debugging
        logger.info(f"Creating Activity with id: '{activity_id}', entityId: {entity_id}")
        
        # Ensure ID is not None or empty
        if not activity_id:
            logger.warning(f"Activity has no ID or entityId, creating a random ID")
            import uuid
            activity_id = f"generated_{uuid.uuid4()}"
        
        # Get groupId
        group_id = data.get("groupId")
        if group_id is not None:
            try:
                group_id = int(group_id)
            except (ValueError, TypeError):
                logger.warning(f"Invalid groupId value: {group_id}")
                group_id = None
            
        return cls(
            id=activity_id,  # Include ID field
            start=start_time,
            end=end_time,
            title=title,
            application=application,
            notes=notes,
            tags=tags,
            groupId=group_id
        )

@dataclass
class TagCombination:
    """Represents a ManicTime tag combination"""
    name: str
    tags: List[str] = field(default_factory=list)
    description: Optional[str] = None
    color: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TagCombination":
        """Create TagCombination from API response dict"""
        # Handle if data is not a dictionary
        if not isinstance(data, dict):
            logger.warning(f"TagCombination.from_dict received non-dict data: {type(data)}")
            if isinstance(data, str):
                # If it's a string, use it as the name with empty tags
                return cls(name=data, tags=[])
            return cls(name="Unknown", tags=[])
        
        # Extract tags and ensure it's a list
        tags = data.get("tags", [])
        if not isinstance(tags, list):
            if tags:
                # If tags is a string or other non-list, convert to single-item list
                tags = [str(tags)]
            else:
                tags = []
                
        return cls(
            name=data.get("name", ""),
            tags=tags,
            description=data.get("description"),
            color=data.get("color")
        )