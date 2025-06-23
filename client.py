import logging
from datetime import datetime, timedelta
import requests
from requests_ntlm import HttpNtlmAuth
import json
from pathlib import Path
import backoff
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from typing import Dict, Any, List, Optional, Union
import asyncio
import aiohttp
import pandas as pd
from io import StringIO, BytesIO

from .configuration import Config
from .exceptions import ManicTimeClientError, AuthenticationError, NotFoundError
from .models import Activity, Timeline, TagCombination

logger = logging.getLogger("manictime.client")

class ManicTimeClient:
    def __init__(self, config: Config):
        """Initialize client with configuration"""
        self.config = config
        self.config.validate()
        self.session = self._create_session()
        self._setup_authentication()
        logger.debug("ManicTimeClient initialized with config: %s", self.config.server_url)
        
    def _create_session(self) -> requests.Session:
        """Create and configure requests session with retries"""
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session
        
    def _setup_authentication(self):
        """Configure authentication based on config"""
        if self.config.auth_type == 'ntlm':
            domain_user = f'{self.config.domain}\\{self.config.username}' if self.config.domain else self.config.username
            self.session.auth = HttpNtlmAuth(domain_user, self.config.password)
        elif self.config.auth_type == 'bearer':
            if self.config.token:
                self.session.headers['Authorization'] = f'Bearer {self.config.token}'
            elif self.config.username and self.config.password:
                self._get_token()
            else:
                raise AuthenticationError("Bearer auth requires token or username/password")
        
    def _get_token(self):
        """Get authentication token using username/password following OAuth 2.0 Resource Owner Password Flow"""
        try:
            if self.config.auth_type == 'bearer':
                # Bypass token endpoint discovery and use direct URL
                # Clear session cookies to ensure a clean request
                self.session.cookies.clear()
                logger.debug(f"Session cookies cleared before token request")
                
                # Use the direct token endpoint URL
                token_url = f"{self.config.server_url}/api/token"
                logger.debug(f"Using direct token endpoint: {token_url}")
                
                # Step 2: Get access token from token endpoint
                headers = {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/vnd.manictime.v3+json"
                }
                
                # Use form-urlencoded format with proper URL encoding
                data = {
                    "grant_type": "password",
                    "username": self.config.username,
                    "password": self.config.password
                }
                
                token_response = self.session.request(
                    "post",
                    token_url,
                    headers=headers,
                    data=data,  # requests will handle URL encoding automatically
                    timeout=self.config.timeout
                )
                
                logger.debug(f"Token request response status: {token_response.status_code}")
                
                # Even if we get a 200 OK, we need to verify the response contains a token
                # First check if the response is valid JSON
                try:
                    token_data = token_response.json()
                except Exception as e:
                    logger.error(f"Failed to parse token response as JSON: {str(e)}")
                    raise AuthenticationError(f"Invalid response format from server: {str(e)}")
                
                # Check if token_data is a dictionary
                if not isinstance(token_data, dict):
                    logger.error(f"Unexpected token response format: {type(token_data)}")
                    raise AuthenticationError(f"Unexpected token response format: {type(token_data)}")
                
                # Check if the token is in the response
                if "token" not in token_data:
                    # Some servers might return 200 OK even for auth failures
                    # with different response formats
                    if "error" in token_data:
                        error_msg = token_data.get("error_description", token_data["error"])
                        raise AuthenticationError(f"Authentication error: {error_msg}")
                    else:
                        raise AuthenticationError("Invalid token response from server (token not found)")
                    
                # Set authorization header for future API calls
                self.session.headers['Authorization'] = f'Bearer {token_data["token"]}'
                
                # Return the token for storing in Odoo
                self.token = token_data["token"]
                
                logger.debug("Successfully obtained authentication token")
                
            elif self.config.auth_type == 'ntlm':
                # For NTLM, we already set up the session with HttpNtlmAuth,
                # so nothing else to do here except verify it works
                api_url = f"{self.config.server_url}/api"
                logger.debug(f"Testing NTLM authentication to {api_url}")
                
                headers = {
                    "Accept": "application/vnd.manictime.v3+json"
                }
                
                response = self.session.request(
                    "get",
                    api_url,
                    headers=headers,
                    timeout=self.config.timeout
                )
                
                response.raise_for_status()
                logger.debug("NTLM authentication successful")
                
            else:
                raise AuthenticationError(f"Unsupported authentication type: {self.config.auth_type}")
                
        except requests.exceptions.RequestException as e:
            raise AuthenticationError(f"Failed to obtain authentication token: {str(e)}")
        
    @backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_tries=3)
    def _make_request(self, url: str, method: str = 'get', 
                     data: Any = None, params: Dict[str, Any] = None,
                     headers: Dict[str, str] = None) -> Any:
        """Make HTTP request with retries and error handling"""
        # Prepare headers - start with session headers
        request_headers = dict(self.session.headers)
        
        # Add any custom headers
        if headers:
            request_headers.update(headers)
            
        try:
            response = self.session.request(
                method,
                url,
                json=data,
                params=params,
                headers=request_headers,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            
            # Check if we got JSON response
            content_type = response.headers.get('content-type', '')
            if 'application/json' in content_type or 'application/vnd.manictime' in content_type:
                return response.json() if response.text else None
            else:
                # If we got HTML, it's likely a login page
                if 'text/html' in content_type:
                    logger.error(f"Got HTML response instead of JSON from {url}. This usually means authentication failed.")
                    raise AuthenticationError("Authentication required - received HTML instead of JSON")
                else:
                    logger.warning(f"Unexpected content type: {content_type}")
                    # Try to parse as JSON anyway
                    try:
                        return response.json() if response.text else None
                    except:
                        raise ManicTimeClientError(f"Invalid response format from {url}. Expected JSON, got {content_type}")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Authentication failed")
            if e.response.status_code == 404:
                raise NotFoundError(f"Resource not found: {url}")
            raise ManicTimeClientError(f"Request failed: {str(e)}")
        except requests.exceptions.ConnectionError as e:
            # Explicitly handle connection errors
            raise ManicTimeClientError(f"Connection error: {str(e)}")
        except requests.exceptions.Timeout as e:
            # Explicitly handle timeout errors
            raise ManicTimeClientError(f"Request timed out: {str(e)}")
        except requests.exceptions.RequestException as e:
            # Handle any other request exceptions
            raise ManicTimeClientError(f"Request error: {str(e)}")
        
    def get_activities(self, timeline_id: str, 
                      from_time: datetime, to_time: datetime, 
                      cache: bool = True, activities_url: str = None) -> Dict[str, Any]:
        """Get activities for timeline in time range
        
        Args:
            timeline_id: The timeline ID
            from_time: Start time for the activity range
            to_time: End time for the activity range
            cache: Whether to use caching
            activities_url: Optional direct URL to the activities endpoint
            
        Returns:
            Response data from activities API with 'activities' key containing processed activity data
        """
        # Use the provided activities URL if available, otherwise construct it
        if activities_url:
            url = activities_url
            logger.info(f"Using provided activities URL: {url}")
        else:
            url = f"{self.config.server_url}/api/timelines/{timeline_id}/activities"
            logger.info(f"Using default constructed activities URL: {url}")
            
        # Format parameters for the request
        params = {
            'fromTime': from_time.isoformat(),
            'toTime': to_time.isoformat()
        }
        
        # Add v3 API header to ensure proper response format
        headers = {"Accept": "application/vnd.manictime.v3+json"}
        logger.info(f"Requesting activities for timeline {timeline_id} from {from_time} to {to_time}")
        
        try:
            result = self._make_request(url, params=params, headers=headers)
            
            # Handle ManicTime API response with 'entities' array 
            if isinstance(result, dict):
                # Extract activities from 'entities' array
                if 'entities' in result and isinstance(result['entities'], list):
                    # Filter entities for activities
                    activities = [
                        entity for entity in result['entities'] 
                        if isinstance(entity, dict) and entity.get('entityType') == 'activity'
                    ]
                    
                    # Transform entities to standard activity format
                    transformed_activities = []
                    for activity in activities:
                        values = activity.get('values', {})
                        if isinstance(values, dict) and 'timeInterval' in values:
                            time_interval = values.get('timeInterval', {})
                            start_time = time_interval.get('start', '')
                            duration_seconds = time_interval.get('duration', 0)
                            
                            # Calculate end time from start and duration
                            end_time = ''
                            if start_time:
                                try:
                                    from dateutil import parser
                                    from datetime import timedelta
                                    start_dt = parser.parse(start_time)
                                    end_dt = start_dt + timedelta(seconds=duration_seconds)
                                    end_time = end_dt.isoformat()
                                except Exception as e:
                                    logger.warning(f"Error calculating end time: {str(e)}")
                            
                            # Get activity name/title
                            name = values.get('name', '')
                            
                            # Extract tags from group entities
                            tags = []
                            group_list_id = values.get('groupListId')
                            if group_list_id:
                                # Find the groupList entity
                                group_list = next((
                                    entity for entity in result['entities']
                                    if entity.get('entityType') == 'groupList' and entity.get('entityId') == group_list_id
                                ), None)
                                
                                if group_list and 'values' in group_list and 'groupIds' in group_list['values']:
                                    group_ids = group_list['values']['groupIds']
                                    # Find all group entities with these IDs
                                    groups = [
                                        entity for entity in result['entities']
                                        if entity.get('entityType') == 'group' and entity.get('entityId') in group_ids
                                    ]
                                    # Extract names from groups
                                    for group in groups:
                                        if 'values' in group and 'name' in group['values']:
                                            tag_name = group['values']['name']
                                            if tag_name:
                                                tags.append(tag_name)
                            
                            # Create standardized activity data - ensure ID is present and properly formatted
                            entity_id = activity.get('entityId')
                            # Convert entityId to string if it exists, otherwise use empty string
                            entity_id_str = str(entity_id) if entity_id is not None else ''
                            
                            # Log the entityId for debugging
                            logger.info(f"Processing activity with entityId: {entity_id} (type: {type(entity_id)})")
                            
                            activity_data = {
                                'id': entity_id_str,  # Use string representation as ID
                                'entityId': entity_id,  # Keep original entityId for reference
                                'title': name,
                                'start': start_time,
                                'end': end_time,
                                'duration': duration_seconds,
                                'tags': tags,
                                'groupId': values.get('groupId'),  # Add this line
                            }
                            
                            # Add application field if available
                            if 'application' in values:
                                activity_data['application'] = values['application']
                            
                            transformed_activities.append(activity_data)
                    
                    # Add standardized activities to result
                    result['activities'] = transformed_activities
                    logger.info(f"Extracted {len(transformed_activities)} activities from entities")
                else:
                    # No entities found, create empty activities list
                    logger.warning(f"Response doesn't contain 'entities' array. Keys: {list(result.keys())}")
                    result['activities'] = []
            else:
                # Unexpected response type, create empty result
                logger.warning(f"Unexpected response type: {type(result)}")
                result = {'activities': []}
                
            return result
        except Exception as e:
            logger.error(f"Error fetching activities for timeline {timeline_id}: {str(e)}")
            raise

    def get_timelines(self) -> List[Dict[str, Any]]:
        """
        Get list of timelines
        """
        url = f"{self.config.server_url}/api/timelines"
        response = self._make_request(url, "GET")
        
        # Extract timelines array from response
        if isinstance(response, dict) and 'timelines' in response:
            timelines = response['timelines']
            logger.debug(f"Retrieved {len(timelines)} timelines")
            return timelines
        elif isinstance(response, list):
            # Response is already a list
            logger.debug(f"Retrieved {len(response)} timelines")
            return response
        else:
            logger.warning(f"Unexpected timelines response format: {type(response)}")
            return []
    
    def discover_users_from_timelines(self) -> Dict[str, Dict[str, Any]]:
        """
        Discover unique users from timeline data
        
        Returns:
            Dictionary mapping username to user info including display name and timeline count
        """
        timelines = self.get_timelines()
        users = {}
        
        for timeline in timelines:
            # Extract owner information from timeline
            owner = timeline.get('owner', {})
            # ManicTime API uses 'username' field, not 'name'
            username = owner.get('username') or owner.get('name')
            
            if username:
                if username not in users:
                    users[username] = {
                        'username': username,
                        'display_name': owner.get('displayName', username),
                        'email': owner.get('email', ''),  # May not be present
                        'timeline_count': 0,
                        'timelines': []
                    }
                
                users[username]['timeline_count'] += 1
                users[username]['timelines'].append({
                    'key': timeline.get('timelineKey'),
                    'device': timeline.get('deviceDisplayName', 'Unknown Device')
                })
        
        logger.debug(f"Discovered {len(users)} unique users from {len(timelines)} timelines")
        return users

    def get_tag_combinations(self, include_all_users: bool = False) -> List[Dict[str, Any]]:
        """
        Get list of tag combinations
        
        Args:
            include_all_users: If True, fetch tags for all users (admin only)
            
        Returns:
            List of tag combinations
        """
        if include_all_users:
            # Admin endpoint to get tags for all users
            url = f"{self.config.server_url}/api/tagcombinationlist?getAll=true"
            logger.info("Fetching tag combinations for all users (admin endpoint)")
        else:
            # Standard endpoint for current user's tags
            url = f"{self.config.server_url}/api/tagcombinationlist"
            logger.info("Fetching tag combinations for current user")
            
        # Add appropriate accept header for v3 API
        headers = {"Accept": "application/vnd.manictime.v3+json"}
        
        try:
            response = self._make_request(url, "GET", headers=headers)
            logger.info(f"Retrieved {len(response)} tag combinations")
            return response
        except ManicTimeClientError as e:
            # If the admin endpoint fails, fall back to the standard endpoint
            if include_all_users:
                logger.warning(f"Admin tag endpoint failed: {str(e)}. Falling back to user endpoint.")
                return self.get_tag_combinations(include_all_users=False)
            # Re-raise the error for the standard endpoint
            raise

    def get_activities_for_date_range(self, 
                                    timeline_id: str,
                                    start_date: datetime,
                                    end_date: datetime,
                                    batch_size: timedelta = timedelta(days=7),
                                    activities_url: str = None) -> List[Activity]:
        """
        Get all activities between two dates, handling pagination
        
        Args:
            timeline_id: The timeline to query
            start_date: Start date (inclusive)
            end_date: End date (inclusive) 
            batch_size: How much data to request at once (default 7 days)
            activities_url: Optional direct URL to the activities endpoint
        
        Returns:
            List of Activity objects
        """
        all_activities = []
        current_start = start_date
        
        while current_start <= end_date:
            current_end = min(current_start + batch_size, end_date)
            
            logger.info(f"Fetching activities from {current_start} to {current_end}")
            
            batch = self.get_activities(
                timeline_id,
                current_start,
                current_end,
                activities_url=activities_url
            )
            
            # Handle the case where batch might not be a dictionary
            if not isinstance(batch, dict):
                logger.warning(f"Unexpected format in activities response: {type(batch)}")
                activities = []
            else:
                # Safely extract activities from the response
                activity_data = batch.get("activities", [])
                if not isinstance(activity_data, list):
                    logger.warning(f"Activities field is not a list: {type(activity_data)}")
                    activities = []
                else:
                    activities = []
                    for a in activity_data:
                        try:
                            activities.append(Activity.from_dict(a))
                        except Exception as e:
                            logger.error(f"Failed to parse activity: {str(e)}")
                            # Continue with other activities
            all_activities.extend(activities)
            
            logger.debug(f"Retrieved {len(activities)} activities")
            
            current_start = current_end + timedelta(seconds=1)
            
        return all_activities

    def get_all_timeline_activities(self,
                                  start_date: datetime,
                                  end_date: datetime) -> Dict[str, List[Activity]]:
        """
        Get activities for all timelines in a date range
        
        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            
        Returns:
            Dict mapping timeline IDs to lists of activities
        """
        results = {}
        timelines = self.get_timelines()
        
        for timeline in timelines:
            timeline_id = timeline["timelineId"]
            logger.info(f"Fetching activities for timeline {timeline_id}")
            
            try:
                activities = self.get_activities_for_date_range(
                    timeline_id,
                    start_date,
                    end_date
                )
                results[timeline_id] = activities
                
            except NotFoundError:
                logger.warning(f"Timeline {timeline_id} not found or no access")
                continue
                
        return results
        
    def get_daily_activities(self, 
                           start_date: datetime,
                           end_date: datetime) -> List[Dict[str, Any]]:
        """
        Get activities for all timelines grouped by day
        
        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            
        Returns:
            List of dictionaries with day and timeline activities
        """
        all_activities = self.get_all_timeline_activities(start_date, end_date)
        daily_data = []
        
        # Create a dictionary for each day in the range
        current_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        while current_date <= end_date:
            next_date = current_date + timedelta(days=1)
            
            day_data = {
                "date": current_date.date().isoformat(),
                "timelines": {}
            }
            
            # Filter activities for this day for each timeline
            for timeline_id, activities in all_activities.items():
                day_activities = [
                    activity for activity in activities
                    if current_date <= activity.start < next_date
                ]
                
                if day_activities:
                    timeline_data = {
                        "activities": [
                            {
                                "start": activity.start.isoformat(),
                                "end": activity.end.isoformat(),
                                "title": activity.title,
                                "application": activity.application,
                                "duration_seconds": activity.duration.total_seconds(),
                                "tags": activity.tags,
                                "notes": activity.notes
                            }
                            for activity in day_activities
                        ],
                        "total_seconds": sum(a.duration.total_seconds() for a in day_activities)
                    }
                    day_data["timelines"][timeline_id] = timeline_data
            
            if day_data["timelines"]:
                daily_data.append(day_data)
            
            current_date = next_date
        
        return daily_data

    def create_tag_combination(self, name: str, tags: List[str], description: str = None, 
                             color: str = None) -> Dict[str, Any]:
        """
        Create a new tag combination
        
        Args:
            name: Name of the tag combination
            tags: List of tag names to include
            description: Optional description
            color: Optional color (hex code)
            
        Returns:
            Created tag combination data
        """
        url = f"{self.config.server_url}/api/tags"
        data = {
            "name": name,
            "tags": tags
        }
        
        if description:
            data["description"] = description
            
        if color:
            data["color"] = color
            
        logger.info(f"Creating tag combination: {name}")
        return self._make_request(url, method="POST", data=data)
    
    def update_tag_combination(self, combination_id: str, name: str = None, 
                             tags: List[str] = None, description: str = None,
                             color: str = None) -> Dict[str, Any]:
        """
        Update an existing tag combination
        
        Args:
            combination_id: ID of the tag combination to update
            name: New name (optional)
            tags: New list of tags (optional)
            description: New description (optional)
            color: New color (optional)
            
        Returns:
            Updated tag combination data
        """
        url = f"{self.config.server_url}/api/tags/{combination_id}"
        data = {}
        
        if name:
            data["name"] = name
            
        if tags:
            data["tags"] = tags
            
        if description:
            data["description"] = description
            
        if color:
            data["color"] = color
        
        logger.info(f"Updating tag combination: {combination_id}")
        return self._make_request(url, method="PUT", data=data)
        
    def delete_tag_combination(self, combination_id: str) -> None:
        """
        Delete a tag combination
        
        Args:
            combination_id: ID of the tag combination to delete
        """
        url = f"{self.config.server_url}/api/tags/{combination_id}"
        logger.info(f"Deleting tag combination: {combination_id}")
        return self._make_request(url, method="DELETE")
    
    # Query builder for more flexible activity queries
    def activity_query(self):
        """
        Create a fluent query interface for activities
        
        Returns:
            ActivityQueryBuilder instance
        """
        return ActivityQueryBuilder(self)
    
    # Export methods
    def export_activities_to_csv(self, activities: List[Activity], 
                                filename: Optional[str] = None) -> Union[str, None]:
        """
        Export activities to CSV format
        
        Args:
            activities: List of Activity objects
            filename: Optional filename to write to
            
        Returns:
            CSV string if filename is None, otherwise None
        """
        records = []
        for activity in activities:
            record = {
                "start": activity.start,
                "end": activity.end,
                "duration_seconds": activity.duration.total_seconds(),
                "title": activity.title,
                "application": activity.application,
                "notes": activity.notes or "",
                "tags": ",".join(activity.tags)
            }
            records.append(record)
            
        df = pd.DataFrame(records)
        
        if filename:
            df.to_csv(filename, index=False)
            logger.info(f"Exported {len(activities)} activities to {filename}")
            return None
        else:
            csv_string = StringIO()
            df.to_csv(csv_string, index=False)
            return csv_string.getvalue()
            
    def export_activities_to_excel(self, activities: List[Activity], 
                                  filename: str) -> None:
        """
        Export activities to Excel format
        
        Args:
            activities: List of Activity objects
            filename: Filename to write to
        """
        records = []
        for activity in activities:
            record = {
                "start": activity.start,
                "end": activity.end,
                "duration_seconds": activity.duration.total_seconds(),
                "title": activity.title,
                "application": activity.application,
                "notes": activity.notes or "",
                "tags": ",".join(activity.tags)
            }
            records.append(record)
            
        df = pd.DataFrame(records)
        df.to_excel(filename, index=False)
        logger.info(f"Exported {len(activities)} activities to {filename}")
        
    def export_activities_to_json(self, activities: List[Activity], 
                                 filename: Optional[str] = None) -> Union[str, None]:
        """
        Export activities to JSON format
        
        Args:
            activities: List of Activity objects
            filename: Optional filename to write to
            
        Returns:
            JSON string if filename is None, otherwise None
        """
        records = []
        for activity in activities:
            record = {
                "start": activity.start.isoformat(),
                "end": activity.end.isoformat(),
                "duration_seconds": activity.duration.total_seconds(),
                "title": activity.title,
                "application": activity.application,
                "notes": activity.notes or "",
                "tags": activity.tags
            }
            records.append(record)
            
        if filename:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(records, f, ensure_ascii=False, indent=2)
            logger.info(f"Exported {len(activities)} activities to {filename}")
            return None
        else:
            return json.dumps(records, ensure_ascii=False, indent=2)
    
    def export_activities_to_html(self, activities: List[Activity],
                                 filename: str,
                                 title: str = "ManicTime Activities") -> None:
        """
        Export activities to HTML format
        
        Args:
            activities: List of Activity objects
            filename: Filename to write to
            title: Title for the HTML page
        """
        records = []
        for activity in activities:
            records.append({
                "start": activity.start.strftime("%Y-%m-%d %H:%M:%S"),
                "end": activity.end.strftime("%Y-%m-%d %H:%M:%S"),
                "duration": str(activity.duration).split('.')[0],  # Remove microseconds
                "title": activity.title,
                "application": activity.application,
                "notes": activity.notes or "",
                "tags": ", ".join(activity.tags)
            })
            
        df = pd.DataFrame(records)
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 20px;
                    line-height: 1.6;
                }}
                h1 {{
                    color: #333;
                }}
                table {{
                    border-collapse: collapse;
                    width: 100%;
                    margin-top: 20px;
                }}
                th, td {{
                    padding: 12px 15px;
                    border-bottom: 1px solid #ddd;
                    text-align: left;
                }}
                th {{
                    background-color: #f2f2f2;
                    color: #333;
                }}
                tr:hover {{
                    background-color: #f5f5f5;
                }}
                .summary {{
                    margin-top: 20px;
                    padding: 15px;
                    background-color: #f2f2f2;
                    border-radius: 5px;
                }}
            </style>
        </head>
        <body>
            <h1>{title}</h1>
            <div class="summary">
                <p>Total activities: {len(activities)}</p>
                <p>Total duration: {str(timedelta(seconds=sum(a.duration.total_seconds() for a in activities))).split('.')[0]}</p>
                <p>Date range: {min(a.start for a in activities).strftime('%Y-%m-%d')} to {max(a.end for a in activities).strftime('%Y-%m-%d')}</p>
            </div>
            {df.to_html(index=False)}
        </body>
        </html>
        """
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        logger.info(f"Exported {len(activities)} activities to HTML file {filename}")
        
    # Statistical Analysis Features
    def get_activity_statistics(self, activities: List[Activity]) -> Dict[str, Any]:
        """
        Generate statistical metrics for a list of activities
        
        Args:
            activities: List of Activity objects
            
        Returns:
            Dictionary with statistical metrics
        """
        if not activities:
            return {
                "total_count": 0,
                "total_duration_seconds": 0,
                "average_duration_seconds": 0,
                "min_duration_seconds": 0,
                "max_duration_seconds": 0,
                "total_days": 0
            }
            
        # Calculate total duration
        total_duration_seconds = sum(a.duration.total_seconds() for a in activities)
        
        # Calculate min and max duration
        min_duration = min(activities, key=lambda a: a.duration).duration
        max_duration = max(activities, key=lambda a: a.duration).duration
        
        # Calculate average duration
        avg_duration = timedelta(seconds=total_duration_seconds / len(activities))
        
        # Find unique dates
        unique_dates = set(a.start.date() for a in activities)
        
        # Group activities by application
        apps = {}
        for activity in activities:
            app = activity.application
            if app not in apps:
                apps[app] = []
            apps[app].append(activity)
            
        # Calculate duration per application
        app_durations = {}
        for app, app_activities in apps.items():
            app_durations[app] = sum(a.duration.total_seconds() for a in app_activities)
            
        # Sort applications by duration (descending)
        sorted_apps = sorted(app_durations.items(), key=lambda x: x[1], reverse=True)
        
        # Group activities by tags
        tags = {}
        for activity in activities:
            for tag in activity.tags:
                if tag not in tags:
                    tags[tag] = []
                tags[tag].append(activity)
                
        # Calculate duration per tag
        tag_durations = {}
        for tag, tag_activities in tags.items():
            tag_durations[tag] = sum(a.duration.total_seconds() for a in tag_activities)
            
        # Sort tags by duration (descending)
        sorted_tags = sorted(tag_durations.items(), key=lambda x: x[1], reverse=True)
            
        return {
            "total_count": len(activities),
            "total_duration_seconds": total_duration_seconds,
            "average_duration_seconds": avg_duration.total_seconds(),
            "min_duration_seconds": min_duration.total_seconds(),
            "max_duration_seconds": max_duration.total_seconds(),
            "total_days": len(unique_dates),
            "applications": {
                "count": len(apps),
                "durations": {app: duration for app, duration in sorted_apps[:10]}
            },
            "tags": {
                "count": len(tags),
                "durations": {tag: duration for tag, duration in sorted_tags[:10]}
            }
        }
        
    def get_daily_summary(self, activities: List[Activity]) -> Dict[str, Dict[str, float]]:
        """
        Generate daily summary of activity durations
        
        Args:
            activities: List of Activity objects
            
        Returns:
            Dictionary mapping dates to duration summaries
        """
        daily_summary = {}
        
        for activity in activities:
            date_str = activity.start.date().isoformat()
            
            if date_str not in daily_summary:
                daily_summary[date_str] = {
                    "total_seconds": 0,
                    "applications": {},
                    "tags": {}
                }
                
            summary = daily_summary[date_str]
            duration_seconds = activity.duration.total_seconds()
            
            # Update total duration
            summary["total_seconds"] += duration_seconds
            
            # Update application duration
            app = activity.application
            if app not in summary["applications"]:
                summary["applications"][app] = 0
            summary["applications"][app] += duration_seconds
            
            # Update tag durations
            for tag in activity.tags:
                if tag not in summary["tags"]:
                    summary["tags"][tag] = 0
                summary["tags"][tag] += duration_seconds
                
        # Sort each day's applications and tags
        for date_str, summary in daily_summary.items():
            summary["applications"] = dict(
                sorted(
                    summary["applications"].items(),
                    key=lambda x: x[1],
                    reverse=True
                )
            )
            
            summary["tags"] = dict(
                sorted(
                    summary["tags"].items(),
                    key=lambda x: x[1],
                    reverse=True
                )
            )
            
        return daily_summary
        
    def calculate_productivity_score(self, activities: List[Activity], 
                                   productive_apps: List[str] = None,
                                   productive_tags: List[str] = None) -> Dict[str, Any]:
        """
        Calculate productivity score based on activities
        
        Args:
            activities: List of Activity objects
            productive_apps: List of applications considered productive
            productive_tags: List of tags considered productive
            
        Returns:
            Dictionary with productivity metrics
        """
        productive_apps = productive_apps or []
        productive_tags = productive_tags or []
        
        if not activities:
            return {
                "productive_seconds": 0,
                "unproductive_seconds": 0,
                "productive_percentage": 0,
                "productivity_score": 0
            }
            
        total_seconds = sum(a.duration.total_seconds() for a in activities)
        productive_seconds = 0
        
        for activity in activities:
            # Check if activity has productive app or tag
            is_productive = (
                activity.application in productive_apps or
                any(tag in productive_tags for tag in activity.tags)
            )
            
            if is_productive:
                productive_seconds += activity.duration.total_seconds()
                
        unproductive_seconds = total_seconds - productive_seconds
        
        # Calculate percentage and score (0-100)
        productive_percentage = (productive_seconds / total_seconds) * 100 if total_seconds > 0 else 0
        
        return {
            "productive_seconds": productive_seconds,
            "unproductive_seconds": unproductive_seconds,
            "total_seconds": total_seconds,
            "productive_percentage": productive_percentage,
            "productivity_score": round(productive_percentage)
        }


class ActivityQueryBuilder:
    """Fluent interface for constructing activity queries"""
    
    def __init__(self, client: ManicTimeClient):
        self.client = client
        self._timeline_id = None
        self._from_time = None
        self._to_time = None
        self._tags = []
        self._applications = []
        self._title_search = None
        self._min_duration = None
        self._max_duration = None
        
    def timeline(self, timeline_id: str) -> 'ActivityQueryBuilder':
        """Set the timeline ID"""
        self._timeline_id = timeline_id
        return self
        
    def from_time(self, time: datetime) -> 'ActivityQueryBuilder':
        """Set the start time"""
        self._from_time = time
        return self
        
    def to_time(self, time: datetime) -> 'ActivityQueryBuilder':
        """Set the end time"""
        self._to_time = time
        return self
        
    def with_tags(self, tags: List[str]) -> 'ActivityQueryBuilder':
        """Filter by tags"""
        self._tags.extend(tags)
        return self
        
    def with_applications(self, applications: List[str]) -> 'ActivityQueryBuilder':
        """Filter by application names"""
        self._applications.extend(applications)
        return self
        
    def title_contains(self, search_text: str) -> 'ActivityQueryBuilder':
        """Filter by title text"""
        self._title_search = search_text
        return self
        
    def min_duration(self, duration: timedelta) -> 'ActivityQueryBuilder':
        """Set minimum activity duration"""
        self._min_duration = duration
        return self
        
    def max_duration(self, duration: timedelta) -> 'ActivityQueryBuilder':
        """Set maximum activity duration"""
        self._max_duration = duration
        return self
        
    def execute(self) -> List[Activity]:
        """Execute the query and return results"""
        if not self._timeline_id:
            raise ValueError("Timeline ID must be set")
            
        if not self._from_time:
            raise ValueError("From time must be set")
            
        if not self._to_time:
            raise ValueError("To time must be set")
            
        # Get raw activities from server
        raw_activities = self.client.get_activities(
            self._timeline_id,
            self._from_time,
            self._to_time
        )
        
        activities = [Activity.from_dict(a) for a in raw_activities.get("activities", [])]
        filtered_activities = []
        
        # Apply filters
        for activity in activities:
            # Check tags
            if self._tags and not any(tag in activity.tags for tag in self._tags):
                continue
                
            # Check application
            if self._applications and activity.application not in self._applications:
                continue
                
            # Check title
            if self._title_search and self._title_search.lower() not in activity.title.lower():
                continue
                
            # Check duration
            if self._min_duration and activity.duration < self._min_duration:
                continue
                
            if self._max_duration and activity.duration > self._max_duration:
                continue
                
            filtered_activities.append(activity)
            
        return filtered_activities


class AsyncManicTimeClient:
    """Asynchronous version of the ManicTime client using aiohttp"""
    
    def __init__(self, config: Config):
        """Initialize client with configuration"""
        self.config = config
        self.config.validate()
        self.session = None
        logger.debug("AsyncManicTimeClient initialized with config: %s", self.config.server_url)
        
    async def __aenter__(self):
        """Create session when entering async context"""
        self.session = aiohttp.ClientSession()
        await self._setup_authentication()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close session when exiting async context"""
        if self.session:
            await self.session.close()
        
    async def _setup_authentication(self):
        """Configure authentication based on config"""
        if self.config.auth_type == 'bearer':
            if self.config.token:
                self.session.headers['Authorization'] = f'Bearer {self.config.token}'
            elif self.config.username and self.config.password:
                await self._get_token()
            else:
                raise AuthenticationError("Bearer auth requires token or username/password")
        elif self.config.auth_type == 'ntlm':
            # aiohttp doesn't support NTLM auth natively
            logger.warning("NTLM auth is not fully supported in AsyncManicTimeClient")
        
    async def _get_token(self):
        """Get authentication token using username/password following OAuth 2.0 Resource Owner Password Flow"""
        try:
            # Bypass token endpoint discovery and use direct URL
            # Clear existing cookies for a fresh request
            self.session.cookie_jar.clear()
            logger.debug(f"Session cookies cleared before token request")
            
            # Use the direct token endpoint URL
            token_url = f"{self.config.server_url}/api/token"
            logger.debug(f"Using direct token endpoint: {token_url}")
            
            # Step 2: Get access token from token endpoint
            token_headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/vnd.manictime.v3+json"
            }
            
            # Use form-urlencoded format with proper URL encoding
            data = {
                "grant_type": "password",
                "username": self.config.username,
                "password": self.config.password
            }
            
            async with self.session.post(
                token_url,
                headers=token_headers,
                data=data,  # aiohttp will handle URL encoding automatically
                timeout=self.config.timeout
            ) as token_response:
                logger.debug(f"Token request response status: {token_response.status}")
                
                token_response.raise_for_status()
                token_data = await token_response.json()
                
                if "token" not in token_data:
                    raise AuthenticationError("Invalid token response from server")
                    
                # Set authorization header for future API calls
                self.session.headers['Authorization'] = f'Bearer {token_data["token"]}'
                logger.debug("Successfully obtained authentication token")
                    
        except aiohttp.ClientError as e:
            raise AuthenticationError(f"Failed to obtain authentication token: {str(e)}")
            
    async def _make_request(self, url: str, method: str = 'get', 
                          data: Any = None, params: Dict[str, Any] = None) -> Any:
        """Make HTTP request with retries and error handling"""
        retries = 3
        backoff_factor = 0.5
        
        for attempt in range(retries):
            try:
                if method.lower() == 'get':
                    async with self.session.get(url, params=params, timeout=self.config.timeout) as response:
                        response.raise_for_status()
                        return await response.json() if response.content_type == 'application/json' else None
                elif method.lower() == 'post':
                    async with self.session.post(url, json=data, params=params, timeout=self.config.timeout) as response:
                        response.raise_for_status()
                        return await response.json() if response.content_type == 'application/json' else None
                elif method.lower() == 'put':
                    async with self.session.put(url, json=data, params=params, timeout=self.config.timeout) as response:
                        response.raise_for_status()
                        return await response.json() if response.content_type == 'application/json' else None
                elif method.lower() == 'delete':
                    async with self.session.delete(url, timeout=self.config.timeout) as response:
                        response.raise_for_status()
                        return None
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
            except aiohttp.ClientResponseError as e:
                if e.status == 401:
                    raise AuthenticationError("Authentication failed")
                if e.status == 404:
                    raise NotFoundError(f"Resource not found: {url}")
                if attempt == retries - 1:
                    raise ManicTimeClientError(f"Request failed after {retries} attempts: {str(e)}")
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt == retries - 1:
                    raise ManicTimeClientError(f"Request error: {str(e)}")
                
            await asyncio.sleep(backoff_factor * (2 ** attempt))
        
        raise ManicTimeClientError("All request attempts failed")
            
    async def get_timelines(self) -> List[Dict[str, Any]]:
        """Get list of timelines"""
        url = f"{self.config.server_url}/api/timelines"
        response = await self._make_request(url, "GET")
        logger.info(f"Retrieved {len(response)} timelines")
        return response
    
    async def get_tag_combinations(self) -> List[Dict[str, Any]]:
        """Get list of tag combinations"""
        url = f"{self.config.server_url}/api/tags"
        response = await self._make_request(url, "GET")
        logger.info(f"Retrieved {len(response)} tag combinations")
        return response
        
    async def get_activities(self, timeline_id: str, 
                           from_time: datetime, to_time: datetime) -> Dict[str, Any]:
        """Get activities for timeline in time range"""
        url = f"{self.config.server_url}/api/timelines/{timeline_id}/activities"
        params = {
            'fromTime': from_time.isoformat(),
            'toTime': to_time.isoformat()
        }
        return await self._make_request(url, params=params)
        
    async def get_activities_for_date_range(self, 
                                          timeline_id: str,
                                          start_date: datetime,
                                          end_date: datetime,
                                          batch_size: timedelta = timedelta(days=7)) -> List[Activity]:
        """
        Get all activities between two dates, handling pagination
        
        Args:
            timeline_id: The timeline to query
            start_date: Start date (inclusive)
            end_date: End date (inclusive) 
            batch_size: How much data to request at once (default 7 days)
        
        Returns:
            List of Activity objects
        """
        all_activities = []
        current_start = start_date
        
        while current_start <= end_date:
            current_end = min(current_start + batch_size, end_date)
            
            logger.info(f"Fetching activities from {current_start} to {current_end}")
            
            batch = await self.get_activities(
                timeline_id,
                current_start,
                current_end
            )
            
            activities = [Activity.from_dict(a) for a in batch.get("activities", [])]
            all_activities.extend(activities)
            
            logger.debug(f"Retrieved {len(activities)} activities")
            
            current_start = current_end + timedelta(seconds=1)
            
        return all_activities
        
    async def get_all_timeline_activities(self,
                                        start_date: datetime,
                                        end_date: datetime) -> Dict[str, List[Activity]]:
        """
        Get activities for all timelines in a date range
        
        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            
        Returns:
            Dict mapping timeline IDs to lists of activities
        """
        results = {}
        timelines = await self.get_timelines()
        
        for timeline in timelines:
            timeline_id = timeline["timelineId"]
            logger.info(f"Fetching activities for timeline {timeline_id}")
            
            try:
                activities = await self.get_activities_for_date_range(
                    timeline_id,
                    start_date,
                    end_date
                )
                results[timeline_id] = activities
                
            except NotFoundError:
                logger.warning(f"Timeline {timeline_id} not found or no access")
                continue
                
        return results
        
    async def create_tag_combination(self, name: str, tags: List[str], 
                                   description: str = None, 
                                   color: str = None) -> Dict[str, Any]:
        """
        Create a new tag combination
        
        Args:
            name: Name of the tag combination
            tags: List of tag names to include
            description: Optional description
            color: Optional color (hex code)
            
        Returns:
            Created tag combination data
        """
        url = f"{self.config.server_url}/api/tags"
        data = {
            "name": name,
            "tags": tags
        }
        
        if description:
            data["description"] = description
            
        if color:
            data["color"] = color
            
        logger.info(f"Creating tag combination: {name}")
        return await self._make_request(url, method="POST", data=data)
    
    async def update_tag_combination(self, combination_id: str, name: str = None, 
                                   tags: List[str] = None, description: str = None,
                                   color: str = None) -> Dict[str, Any]:
        """
        Update an existing tag combination
        
        Args:
            combination_id: ID of the tag combination to update
            name: New name (optional)
            tags: New list of tags (optional)
            description: New description (optional)
            color: New color (optional)
            
        Returns:
            Updated tag combination data
        """
        url = f"{self.config.server_url}/api/tags/{combination_id}"
        data = {}
        
        if name:
            data["name"] = name
            
        if tags:
            data["tags"] = tags
            
        if description:
            data["description"] = description
            
        if color:
            data["color"] = color
        
        logger.info(f"Updating tag combination: {combination_id}")
        return await self._make_request(url, method="PUT", data=data)
        
    async def delete_tag_combination(self, combination_id: str) -> None:
        """
        Delete a tag combination
        
        Args:
            combination_id: ID of the tag combination to delete
        """
        url = f"{self.config.server_url}/api/tags/{combination_id}"
        logger.info(f"Deleting tag combination: {combination_id}")
        return await self._make_request(url, method="DELETE")
    
    # Query builder for async activity queries
    def activity_query(self):
        """
        Create a fluent query interface for activities
        
        Returns:
            AsyncActivityQueryBuilder instance
        """
        return AsyncActivityQueryBuilder(self)


class AsyncActivityQueryBuilder:
    """Fluent interface for constructing asynchronous activity queries"""
    
    def __init__(self, client: AsyncManicTimeClient):
        self.client = client
        self._timeline_id = None
        self._from_time = None
        self._to_time = None
        self._tags = []
        self._applications = []
        self._title_search = None
        self._min_duration = None
        self._max_duration = None
        
    def timeline(self, timeline_id: str) -> 'AsyncActivityQueryBuilder':
        """Set the timeline ID"""
        self._timeline_id = timeline_id
        return self
        
    def from_time(self, time: datetime) -> 'AsyncActivityQueryBuilder':
        """Set the start time"""
        self._from_time = time
        return self
        
    def to_time(self, time: datetime) -> 'AsyncActivityQueryBuilder':
        """Set the end time"""
        self._to_time = time
        return self
        
    def with_tags(self, tags: List[str]) -> 'AsyncActivityQueryBuilder':
        """Filter by tags"""
        self._tags.extend(tags)
        return self
        
    def with_applications(self, applications: List[str]) -> 'AsyncActivityQueryBuilder':
        """Filter by application names"""
        self._applications.extend(applications)
        return self
        
    def title_contains(self, search_text: str) -> 'AsyncActivityQueryBuilder':
        """Filter by title text"""
        self._title_search = search_text
        return self
        
    def min_duration(self, duration: timedelta) -> 'AsyncActivityQueryBuilder':
        """Set minimum activity duration"""
        self._min_duration = duration
        return self
        
    def max_duration(self, duration: timedelta) -> 'AsyncActivityQueryBuilder':
        """Set maximum activity duration"""
        self._max_duration = duration
        return self
        
    async def execute(self) -> List[Activity]:
        """Execute the query and return results"""
        if not self._timeline_id:
            raise ValueError("Timeline ID must be set")
            
        if not self._from_time:
            raise ValueError("From time must be set")
            
        if not self._to_time:
            raise ValueError("To time must be set")
            
        # Get raw activities from server
        raw_activities = await self.client.get_activities(
            self._timeline_id,
            self._from_time,
            self._to_time
        )
        
        activities = [Activity.from_dict(a) for a in raw_activities.get("activities", [])]
        filtered_activities = []
        
        # Apply filters
        for activity in activities:
            # Check tags
            if self._tags and not any(tag in activity.tags for tag in self._tags):
                continue
                
            # Check application
            if self._applications and activity.application not in self._applications:
                continue
                
            # Check title
            if self._title_search and self._title_search.lower() not in activity.title.lower():
                continue
                
            # Check duration
            if self._min_duration and activity.duration < self._min_duration:
                continue
                
            if self._max_duration and activity.duration > self._max_duration:
                continue
                
            filtered_activities.append(activity)
            
        return filtered_activities


class CachedManicTimeClient(ManicTimeClient):
    """
    ManicTime client with built-in caching for frequently accessed data
    """
    
    def __init__(self, config: Config, cache_ttl: int = 300):
        """
        Initialize client with configuration and cache settings
        
        Args:
            config: Configuration object
            cache_ttl: Cache time-to-live in seconds (default: 5 minutes)
        """
        super().__init__(config)
        self.cache_ttl = cache_ttl
        self._cache = {}
        self._cache_timestamps = {}
        logger.debug("CachedManicTimeClient initialized with TTL: %s seconds", cache_ttl)
        
    def _get_cache_key(self, *args, **kwargs) -> str:
        """
        Generate a cache key from args and kwargs
        
        Returns:
            String cache key
        """
        # Convert args and kwargs to strings and combine
        args_str = ",".join(str(arg) for arg in args)
        kwargs_str = ",".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
        return f"{args_str}|{kwargs_str}"
    
    def _get_from_cache(self, key: str) -> Optional[Any]:
        """
        Get value from cache if it exists and is not expired
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        if key not in self._cache:
            return None
            
        timestamp = self._cache_timestamps.get(key)
        if timestamp and (datetime.now() - timestamp).total_seconds() > self.cache_ttl:
            # Cache expired, remove it
            del self._cache[key]
            del self._cache_timestamps[key]
            return None
            
        logger.debug("Cache hit for key: %s", key)
        return self._cache[key]
        
    def _store_in_cache(self, key: str, value: Any) -> None:
        """
        Store value in cache with current timestamp
        
        Args:
            key: Cache key
            value: Value to cache
        """
        self._cache[key] = value
        self._cache_timestamps[key] = datetime.now()
        logger.debug("Stored in cache: %s", key)
        
    def clear_cache(self) -> None:
        """Clear all cached data"""
        self._cache.clear()
        self._cache_timestamps.clear()
        logger.info("Cache cleared")
        
    def get_timelines(self) -> List[Dict[str, Any]]:
        """Get list of timelines with caching"""
        cache_key = self._get_cache_key("get_timelines")
        cached = self._get_from_cache(cache_key)
        
        if cached is not None:
            return cached
            
        result = super().get_timelines()
        self._store_in_cache(cache_key, result)
        return result
        
    def get_tag_combinations(self) -> List[Dict[str, Any]]:
        """Get list of tag combinations with caching"""
        cache_key = self._get_cache_key("get_tag_combinations")
        cached = self._get_from_cache(cache_key)
        
        if cached is not None:
            return cached
            
        result = super().get_tag_combinations()
        self._store_in_cache(cache_key, result)
        return result
        
    def get_activities(self, timeline_id: str, 
                      from_time: datetime, to_time: datetime, 
                      cache: bool = True, 
                      activities_url: str = None) -> Dict[str, Any]:
        """Get activities for timeline in time range with optional caching"""
        if not cache:
            # If activities_url is provided, pass it to the parent method
            if activities_url:
                return super().get_activities(timeline_id, from_time, to_time, cache=False, activities_url=activities_url)
            else:
                return super().get_activities(timeline_id, from_time, to_time, cache=False)
            
        cache_key = self._get_cache_key("get_activities", timeline_id, from_time, to_time)
        if activities_url:
            # If a custom URL is provided, include it in the cache key
            cache_key += f"_{hash(activities_url)}"
            
        cached = self._get_from_cache(cache_key)
        
        if cached is not None:
            return cached
        
        # Call parent method with or without activities_url    
        if activities_url:
            result = super().get_activities(timeline_id, from_time, to_time, cache=False, activities_url=activities_url)
        else:
            result = super().get_activities(timeline_id, from_time, to_time, cache=False)
            
        self._store_in_cache(cache_key, result)
        return result
        
    def get_activities_for_date_range(self, 
                                    timeline_id: str,
                                    start_date: datetime,
                                    end_date: datetime,
                                    batch_size: timedelta = timedelta(days=7),
                                    activities_url: str = None) -> List[Activity]:
        """
        Get all activities between two dates, handling pagination
        
        Args:
            timeline_id: The timeline to query
            start_date: Start date (inclusive)
            end_date: End date (inclusive) 
            batch_size: How much data to request at once (default 7 days)
            activities_url: Optional direct URL to the activities endpoint
        
        Returns:
            List of Activity objects
        """
        all_activities = []
        current_start = start_date
        
        while current_start <= end_date:
            current_end = min(current_start + batch_size, end_date)
            
            logger.info(f"Fetching activities from {current_start} to {current_end}")
            
            # Use the activities_url parameter when calling get_activities
            batch = self.get_activities(
                timeline_id,
                current_start,
                current_end,
                activities_url=activities_url
            )
            
            # Log the batch structure for debugging
            logger.info(f"Activity batch type: {type(batch)}")
            if isinstance(batch, dict):
                logger.info(f"Activity batch keys: {list(batch.keys())}")
            
            # Handle the case where batch might not be a dictionary
            if not isinstance(batch, dict):
                logger.warning(f"Unexpected format in activities response: {type(batch)}")
                activities = []
            else:
                # Safely extract activities from the response
                activity_data = batch.get("activities", [])
                logger.info(f"Found {len(activity_data)} activities in batch")
                
                if not isinstance(activity_data, list):
                    logger.warning(f"Activities field is not a list: {type(activity_data)}")
                    activities = []
                else:
                    activities = []
                    for i, a in enumerate(activity_data):
                        try:
                            # Log every 100th activity for debugging, to avoid too much logging
                            if i % 100 == 0:
                                logger.info(f"Processing activity {i} with data: {a}")
                            
                            activity = Activity.from_dict(a)
                            
                            # Verify ID is present
                            if hasattr(activity, 'id') and activity.id:
                                activities.append(activity)
                                # Log every 100th created activity
                                if i % 100 == 0:
                                    logger.info(f"Created activity {i} with ID: {activity.id}")
                            else:
                                logger.warning(f"Skipping activity {i} because ID is missing")
                                
                        except Exception as e:
                            logger.error(f"Failed to parse activity: {str(e)}")
                            # Continue with other activities
                            
            all_activities.extend(activities)
            
            logger.info(f"Retrieved {len(activities)} activities in this batch")
            
            current_start = current_end + timedelta(seconds=1)
            
        logger.info(f"Total activities retrieved: {len(all_activities)}")
        return all_activities


class ServerAdminClient:
    """Client for ManicTime server administration operations"""
    
    def __init__(self, client: ManicTimeClient):
        """
        Initialize with a ManicTimeClient instance
        
        Args:
            client: Authenticated ManicTimeClient with admin privileges
        """
        self.client = client
        
    def get_server_info(self) -> Dict[str, Any]:
        """
        Get general server information
        
        Returns:
            Dictionary with server information
        """
        url = f"{self.client.config.server_url}/api/server/info"
        return self.client._make_request(url)
        
    def get_server_status(self) -> Dict[str, Any]:
        """
        Get server status information
        
        Returns:
            Dictionary with server status metrics
        """
        url = f"{self.client.config.server_url}/api/server/status"
        return self.client._make_request(url)
        
    def get_users(self) -> List[Dict[str, Any]]:
        """
        Get list of all users on the server
        
        Returns:
            List of user objects
        """
        url = f"{self.client.config.server_url}/api/users"
        return self.client._make_request(url)
        
    def get_user(self, user_id: str) -> Dict[str, Any]:
        """
        Get user details
        
        Args:
            user_id: User ID
            
        Returns:
            User details
        """
        url = f"{self.client.config.server_url}/api/users/{user_id}"
        return self.client._make_request(url)
        
    def create_user(self, username: str, password: str, 
                   email: str = None, is_admin: bool = False) -> Dict[str, Any]:
        """
        Create a new user
        
        Args:
            username: Username 
            password: Password
            email: Optional email address
            is_admin: Whether user should have admin privileges
            
        Returns:
            Created user object
        """
        url = f"{self.client.config.server_url}/api/users"
        data = {
            "username": username,
            "password": password,
            "isAdmin": is_admin
        }
        
        if email:
            data["email"] = email
            
        return self.client._make_request(url, method="POST", data=data)
        
    def update_user(self, user_id: str, password: str = None, 
                   email: str = None, is_admin: bool = None,
                   is_active: bool = None) -> Dict[str, Any]:
        """
        Update a user
        
        Args:
            user_id: User ID
            password: New password (optional)
            email: New email address (optional)
            is_admin: Update admin status (optional)
            is_active: Update active status (optional)
            
        Returns:
            Updated user object
        """
        url = f"{self.client.config.server_url}/api/users/{user_id}"
        data = {}
        
        if password is not None:
            data["password"] = password
            
        if email is not None:
            data["email"] = email
            
        if is_admin is not None:
            data["isAdmin"] = is_admin
            
        if is_active is not None:
            data["isActive"] = is_active
            
        return self.client._make_request(url, method="PUT", data=data)
        
    def delete_user(self, user_id: str) -> None:
        """
        Delete a user
        
        Args:
            user_id: User ID
        """
        url = f"{self.client.config.server_url}/api/users/{user_id}"
        self.client._make_request(url, method="DELETE")
        
    def get_server_settings(self) -> Dict[str, Any]:
        """
        Get server settings
        
        Returns:
            Dictionary with server settings
        """
        url = f"{self.client.config.server_url}/api/server/settings"
        return self.client._make_request(url)
        
    def update_server_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update server settings
        
        Args:
            settings: Dictionary with settings to update
            
        Returns:
            Updated settings
        """
        url = f"{self.client.config.server_url}/api/server/settings"
        return self.client._make_request(url, method="PUT", data=settings)
        
    def get_license_info(self) -> Dict[str, Any]:
        """
        Get license information
        
        Returns:
            Dictionary with license details
        """
        url = f"{self.client.config.server_url}/api/server/license"
        return self.client._make_request(url)
        
    def update_license(self, license_key: str) -> Dict[str, Any]:
        """
        Update server license
        
        Args:
            license_key: New license key
            
        Returns:
            Updated license information
        """
        url = f"{self.client.config.server_url}/api/server/license"
        data = {"licenseKey": license_key}
        return self.client._make_request(url, method="PUT", data=data)


class AsyncServerAdminClient:
    """Async client for ManicTime server administration operations"""
    
    def __init__(self, client: AsyncManicTimeClient):
        """
        Initialize with an AsyncManicTimeClient instance
        
        Args:
            client: Authenticated AsyncManicTimeClient with admin privileges
        """
        self.client = client
        
    async def get_server_info(self) -> Dict[str, Any]:
        """
        Get general server information
        
        Returns:
            Dictionary with server information
        """
        url = f"{self.client.config.server_url}/api/server/info"
        return await self.client._make_request(url)
        
    async def get_server_status(self) -> Dict[str, Any]:
        """
        Get server status information
        
        Returns:
            Dictionary with server status metrics
        """
        url = f"{self.client.config.server_url}/api/server/status"
        return await self.client._make_request(url)
        
    async def get_users(self) -> List[Dict[str, Any]]:
        """
        Get list of all users on the server
        
        Returns:
            List of user objects
        """
        url = f"{self.client.config.server_url}/api/users"
        return await self.client._make_request(url)
        
    async def get_user(self, user_id: str) -> Dict[str, Any]:
        """
        Get user details
        
        Args:
            user_id: User ID
            
        Returns:
            User details
        """
        url = f"{self.client.config.server_url}/api/users/{user_id}"
        return await self.client._make_request(url)
        
    async def create_user(self, username: str, password: str, 
                        email: str = None, is_admin: bool = False) -> Dict[str, Any]:
        """
        Create a new user
        
        Args:
            username: Username 
            password: Password
            email: Optional email address
            is_admin: Whether user should have admin privileges
            
        Returns:
            Created user object
        """
        url = f"{self.client.config.server_url}/api/users"
        data = {
            "username": username,
            "password": password,
            "isAdmin": is_admin
        }
        
        if email:
            data["email"] = email
            
        return await self.client._make_request(url, method="POST", data=data)
        
    async def update_user(self, user_id: str, password: str = None, 
                        email: str = None, is_admin: bool = None,
                        is_active: bool = None) -> Dict[str, Any]:
        """
        Update a user
        
        Args:
            user_id: User ID
            password: New password (optional)
            email: New email address (optional)
            is_admin: Update admin status (optional)
            is_active: Update active status (optional)
            
        Returns:
            Updated user object
        """
        url = f"{self.client.config.server_url}/api/users/{user_id}"
        data = {}
        
        if password is not None:
            data["password"] = password
            
        if email is not None:
            data["email"] = email
            
        if is_admin is not None:
            data["isAdmin"] = is_admin
            
        if is_active is not None:
            data["isActive"] = is_active
            
        return await self.client._make_request(url, method="PUT", data=data)
        
    async def delete_user(self, user_id: str) -> None:
        """
        Delete a user
        
        Args:
            user_id: User ID
        """
        url = f"{self.client.config.server_url}/api/users/{user_id}"
        await self.client._make_request(url, method="DELETE")
        
    async def get_server_settings(self) -> Dict[str, Any]:
        """
        Get server settings
        
        Returns:
            Dictionary with server settings
        """
        url = f"{self.client.config.server_url}/api/server/settings"
        return await self.client._make_request(url)
        
    async def update_server_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update server settings
        
        Args:
            settings: Dictionary with settings to update
            
        Returns:
            Updated settings
        """
        url = f"{self.client.config.server_url}/api/server/settings"
        return await self.client._make_request(url, method="PUT", data=settings)
        
    async def get_license_info(self) -> Dict[str, Any]:
        """
        Get license information
        
        Returns:
            Dictionary with license details
        """
        url = f"{self.client.config.server_url}/api/server/license"
        return await self.client._make_request(url)
        
    async def update_license(self, license_key: str) -> Dict[str, Any]:
        """
        Update server license
        
        Args:
            license_key: New license key
            
        Returns:
            Updated license information
        """
        url = f"{self.client.config.server_url}/api/server/license"
        data = {"licenseKey": license_key}
        return await self.client._make_request(url, method="PUT", data=data)