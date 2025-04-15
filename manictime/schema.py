"""JSON schema validation for ManicTime API responses."""
import json
import logging
from typing import Dict, Any, Optional, List, Union
import jsonschema
from jsonschema import Draft7Validator, validators
from pathlib import Path

logger = logging.getLogger("manictime.schema")

# Default schema directory
SCHEMA_DIR = Path(__file__).parent / "schemas"

# Ensure schema directory exists
SCHEMA_DIR.mkdir(exist_ok=True)


def extend_with_default(validator_class):
    """
    Extend validator class with default values
    
    Based on jsonschema documentation example for handling default values
    """
    validate_properties = validator_class.VALIDATORS["properties"]
    
    def set_defaults(validator, properties, instance, schema):
        for property_name, subschema in properties.items():
            if "default" in subschema and property_name not in instance:
                instance[property_name] = subschema["default"]
                
        for error in validate_properties(validator, properties, instance, schema):
            yield error
            
    return validators.extend(validator_class, {"properties": set_defaults})


# Create validator with default value support
DefaultValidatingDraft7Validator = extend_with_default(Draft7Validator)


class SchemaValidator:
    """JSON schema validator for API responses"""
    
    def __init__(self, schema_dir: Optional[Path] = None):
        """
        Initialize schema validator
        
        Args:
            schema_dir: Directory containing schema files
        """
        self.schema_dir = schema_dir or SCHEMA_DIR
        self.schemas: Dict[str, Dict[str, Any]] = {}
        self._load_schemas()
        
    def _load_schemas(self) -> None:
        """Load all schema files from schema directory"""
        if not self.schema_dir.exists():
            logger.warning(f"Schema directory does not exist: {self.schema_dir}")
            return
            
        for schema_file in self.schema_dir.glob("*.json"):
            try:
                schema_name = schema_file.stem
                with open(schema_file, "r") as f:
                    schema = json.load(f)
                self.schemas[schema_name] = schema
                logger.debug(f"Loaded schema: {schema_name}")
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error loading schema {schema_file}: {str(e)}")
                
    def get_schema(self, schema_name: str) -> Optional[Dict[str, Any]]:
        """
        Get schema by name
        
        Args:
            schema_name: Schema name without extension
            
        Returns:
            Schema definition or None if not found
        """
        return self.schemas.get(schema_name)
        
    def validate(self, data: Dict[str, Any], schema_name: str) -> List[str]:
        """
        Validate data against schema
        
        Args:
            data: Data to validate
            schema_name: Schema name
            
        Returns:
            List of validation error messages (empty if valid)
        """
        schema = self.get_schema(schema_name)
        if not schema:
            logger.warning(f"Schema not found: {schema_name}")
            return [f"Schema not found: {schema_name}"]
            
        validator = DefaultValidatingDraft7Validator(schema)
        errors = list(validator.iter_errors(data))
        
        if not errors:
            return []
            
        # Format error messages
        error_messages = []
        for error in errors:
            path = ".".join(str(p) for p in error.path) if error.path else "root"
            message = f"{path}: {error.message}"
            error_messages.append(message)
            
        return error_messages
        
    def validate_and_transform(self, 
                             data: Dict[str, Any], 
                             schema_name: str) -> Dict[str, Any]:
        """
        Validate data and apply schema transformations (like defaults)
        
        Args:
            data: Data to validate
            schema_name: Schema name
            
        Returns:
            Validated and transformed data
            
        Raises:
            jsonschema.exceptions.ValidationError: If validation fails
        """
        schema = self.get_schema(schema_name)
        if not schema:
            raise ValueError(f"Schema not found: {schema_name}")
            
        # Make a copy to avoid modifying original
        data_copy = json.loads(json.dumps(data))
        
        # Use validator with default support
        validator = DefaultValidatingDraft7Validator(schema)
        validator.validate(data_copy)
        
        return data_copy
        
    def add_schema(self, schema_name: str, schema: Dict[str, Any], 
                  save: bool = False) -> None:
        """
        Add a new schema
        
        Args:
            schema_name: Schema name
            schema: Schema definition
            save: Whether to save to file
        """
        self.schemas[schema_name] = schema
        
        if save:
            schema_file = self.schema_dir / f"{schema_name}.json"
            try:
                with open(schema_file, "w") as f:
                    json.dump(schema, f, indent=2)
                logger.debug(f"Saved schema: {schema_name}")
            except IOError as e:
                logger.error(f"Error saving schema {schema_file}: {str(e)}")
                
    def remove_schema(self, schema_name: str, 
                     delete_file: bool = False) -> bool:
        """
        Remove a schema
        
        Args:
            schema_name: Schema name
            delete_file: Whether to delete schema file
            
        Returns:
            True if schema was removed, False otherwise
        """
        if schema_name not in self.schemas:
            return False
            
        del self.schemas[schema_name]
        
        if delete_file:
            schema_file = self.schema_dir / f"{schema_name}.json"
            try:
                if schema_file.exists():
                    schema_file.unlink()
                    logger.debug(f"Deleted schema file: {schema_name}")
            except IOError as e:
                logger.error(f"Error deleting schema file {schema_file}: {str(e)}")
                
        return True


# Create default schemas

activity_schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Activity",
    "description": "Activity data from ManicTime API",
    "type": "object",
    "properties": {
        "start": {
            "type": "string",
            "format": "date-time",
            "description": "Activity start time"
        },
        "end": {
            "type": "string",
            "format": "date-time", 
            "description": "Activity end time"
        },
        "application": {
            "type": "string",
            "description": "Application name"
        },
        "title": {
            "type": "string",
            "description": "Activity title"
        },
        "tags": {
            "type": "array",
            "items": {
                "type": "string"
            },
            "default": [],
            "description": "Tags assigned to the activity"
        },
        "notes": {
            "type": ["string", "null"],
            "default": null,
            "description": "Activity notes"
        }
    },
    "required": ["start", "end", "application", "title"]
}

timeline_schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Timeline",
    "description": "Timeline data from ManicTime API",
    "type": "object",
    "properties": {
        "timelineId": {
            "type": "string",
            "description": "Timeline ID"
        },
        "name": {
            "type": "string",
            "description": "Timeline name"
        },
        "description": {
            "type": ["string", "null"],
            "default": null,
            "description": "Timeline description"
        }
    },
    "required": ["timelineId", "name"]
}

tag_combination_schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "TagCombination",
    "description": "Tag combination data from ManicTime API",
    "type": "object",
    "properties": {
        "combinationId": {
            "type": "string",
            "description": "Tag combination ID"
        },
        "name": {
            "type": "string",
            "description": "Tag combination name"
        },
        "tags": {
            "type": "array",
            "items": {
                "type": "string"
            },
            "description": "List of tags in the combination"
        },
        "description": {
            "type": ["string", "null"],
            "default": null,
            "description": "Tag combination description"
        },
        "color": {
            "type": ["string", "null"],
            "default": null,
            "description": "Tag combination color (hex code)"
        }
    },
    "required": ["combinationId", "name", "tags"]
}

webhook_schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Webhook",
    "description": "Webhook data from ManicTime API",
    "type": "object",
    "properties": {
        "webhookId": {
            "type": "string",
            "description": "Webhook ID"
        },
        "url": {
            "type": "string",
            "description": "Webhook URL"
        },
        "events": {
            "type": "array",
            "items": {
                "type": "string"
            },
            "description": "List of event types"
        },
        "description": {
            "type": ["string", "null"],
            "default": null,
            "description": "Webhook description"
        },
        "secret": {
            "type": ["string", "null"],
            "default": null,
            "description": "Webhook secret (for signature verification)"
        }
    },
    "required": ["webhookId", "url", "events"]
}

# Default schema validator instance
default_validator = SchemaValidator()

# Initialize default schemas
if not (SCHEMA_DIR / "activity.json").exists():
    default_validator.add_schema("activity", activity_schema, save=True)
    
if not (SCHEMA_DIR / "timeline.json").exists():
    default_validator.add_schema("timeline", timeline_schema, save=True)
    
if not (SCHEMA_DIR / "tag_combination.json").exists():
    default_validator.add_schema("tag_combination", tag_combination_schema, save=True)
    
if not (SCHEMA_DIR / "webhook.json").exists():
    default_validator.add_schema("webhook", webhook_schema, save=True)


def validate_response(data: Dict[str, Any], schema_name: str) -> List[str]:
    """
    Validate API response against schema
    
    Args:
        data: Response data
        schema_name: Schema name
        
    Returns:
        List of validation error messages (empty if valid)
    """
    return default_validator.validate(data, schema_name)


def validate_and_transform(data: Dict[str, Any], schema_name: str) -> Dict[str, Any]:
    """
    Validate and transform data according to schema
    
    Args:
        data: Data to validate
        schema_name: Schema name
        
    Returns:
        Validated and transformed data
        
    Raises:
        jsonschema.exceptions.ValidationError: If validation fails
    """
    return default_validator.validate_and_transform(data, schema_name)