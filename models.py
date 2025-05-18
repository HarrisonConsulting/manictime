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
    duration: Optional[timedelta] = None
    notes: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Calculate duration after initialization"""
        if not self.duration and self.start and self.end:
            self.duration = self.end - self.start
            
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Activity":
        """Create Activity from API response dict"""
        return cls(
            start=datetime.fromisoformat(data["start"]),
            end=datetime.fromisoformat(data["end"]),
            title=data.get("title", ""),
            application=data.get("application", ""),
            notes=data.get("notes"),
            tags=data.get("tags", [])
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