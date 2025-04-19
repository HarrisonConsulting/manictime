#!/usr/bin/env python3
"""
Basic usage example for the ManicTime client.
Shows how to connect to the API and retrieve timeline data.
"""

import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import logging

# Import the ManicTime client library
from manictime import ManicTimeClient, Config
from manictime.exceptions import AuthenticationError, ManicTimeClientError, NotFoundError

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Load environment variables from .env file
load_dotenv()

def main():
    """Main function demonstrating basic ManicTime client usage"""
    print("ManicTime API Client - Basic Usage Example")
    print("-----------------------------------------")
    
    # Create configuration from environment variables
    config = Config.from_env()
    
    # Check if we have necessary authentication configuration
    if not config.server_url:
        print("ERROR: MANICTIME_SERVER_URL environment variable is not set.")
        print("Please set up your .env file with the required configuration.")
        print("See examples/README.md for details on environment setup.")
        return
        
    # Check authentication method
    if config.auth_type == 'bearer' and not config.token:
        print(f"Warning: Using bearer authentication but token is not set.")
        if config.username and config.password:
            print(f"Using username/password instead: {config.username}")
        else:
            print("ERROR: Authentication credentials not found in environment variables.")
            print("Please set MANICTIME_TOKEN or MANICTIME_USERNAME/MANICTIME_PASSWORD in your .env file.")
            return
    
    print(f"Connecting to: {config.server_url}")
    print(f"Authentication type: {config.auth_type or 'default'}")
    
    try:
        # Initialize client
        client = ManicTimeClient(config)
        
        # Get all timelines
        print("\nFetching timelines...")
        timelines = client.get_timelines()
        print(f"Found {len(timelines)} timelines:")
    except AuthenticationError as e:
        print(f"\nERROR: Authentication failed - {str(e)}")
        print("Please check your authentication credentials in the .env file.")
        print("Make sure your token is valid or username/password are correct.")
        return
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        return
    
    for i, timeline in enumerate(timelines, 1):
        print(f"  {i}. {timeline.get('name', 'Unknown')} (ID: {timeline.get('timelineId', 'Unknown')})")
    
    # Choose a timeline (using the first one for this example)
    if not timelines:
        print("No timelines found. Exiting.")
        return
        
    timeline_id = timelines[0]["timelineId"]
    timeline_name = timelines[0]["name"]
    print(f"\nUsing timeline: {timeline_name}")
    
    # Get activities for the last 24 hours
    now = datetime.now()
    yesterday = now - timedelta(days=1)
    
    print(f"\nFetching activities from {yesterday.isoformat()} to {now.isoformat()}...")
    activities = client.get_activities(
        timeline_id=timeline_id,
        from_time=yesterday,
        to_time=now
    )
    
    # Display the results
    activity_count = len(activities.get("activities", []))
    print(f"Found {activity_count} activities in the last 24 hours.")
    
    if activity_count > 0:
        print("\nSample of activities:")
        for i, activity in enumerate(activities.get("activities", [])[:5], 1):
            start = activity.get("start", "Unknown")
            end = activity.get("end", "Unknown")
            title = activity.get("title", "Unknown")
            application = activity.get("application", "Unknown")
            
            print(f"  {i}. [{start} - {end}] {application}: {title}")
    
    print("\nExample completed.")

if __name__ == "__main__":
    main()