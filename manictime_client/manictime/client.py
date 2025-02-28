import logging
from datetime import datetime, timedelta
import requests
from requests_ntlm import HttpNtlmAuth
import json
from pathlib import Path
import backoff
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from typing import Dict, Any, List, Optional

from .config import Config
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
        
    @backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_tries=3)
    def _make_request(self, url: str, method: str = 'get', 
                     data: Any = None, params: Dict[str, Any] = None) -> Any:
        """Make HTTP request with retries and error handling"""
        try:
            response = self.session.request(
                method,
                url,
                json=data,
                params=params,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            return response.json() if response.text else None
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Authentication failed")
            if e.response.status_code == 404:
                raise NotFoundError(f"Resource not found: {url}")
            raise ManicTimeClientError(f"Request failed: {str(e)}")
        
    def get_activities(self, timeline_id: str, 
                      from_time: datetime, to_time: datetime, 
                      cache: bool = True) -> Dict[str, Any]:
        """Get activities for timeline in time range"""
        url = f"{self.config.server_url}/api/timelines/{timeline_id}/activities"
        params = {
            'fromTime': from_time.isoformat(),
            'toTime': to_time.isoformat()
        }
        return self._make_request(url, params=params)

    def get_timelines(self) -> List[Dict[str, Any]]:
        """
        Get list of timelines
        """
        url = f"{self.config.server_url}/api/timelines"
        response = self._make_request(url, "GET")
        logger.info(f"Retrieved {len(response)} timelines")
        return response

    def get_tag_combinations(self) -> List[Dict[str, Any]]:
        """
        Get list of tag combinations
        """
        url = f"{self.config.server_url}/api/tags"
        response = self._make_request(url, "GET")
        logger.info(f"Retrieved {len(response)} tag combinations")
        return response

    def get_activities_for_date_range(self, 
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
            
            batch = self.get_activities(
                timeline_id,
                current_start,
                current_end
            )
            
            activities = [Activity.from_dict(a) for a in batch.get("activities", [])]
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