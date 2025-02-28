#!/usr/bin/env python3
"""
Daily activities example for the ManicTime client.
Shows how to retrieve and analyze daily timeline data.
"""

from datetime import datetime, timedelta
import json
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
    """Main function demonstrating daily activities usage"""
    print("ManicTime API Client - Daily Activities Example")
    print("----------------------------------------------")
    
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
        
        # Get activities for the last 7 days
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        print(f"\nFetching daily activities from {start_date.date()} to {end_date.date()}...")
        daily_data = client.get_daily_activities(start_date, end_date)
        
        print(f"Retrieved data for {len(daily_data)} days.")
    except AuthenticationError as e:
        print(f"\nERROR: Authentication failed - {str(e)}")
        print("Please check your authentication credentials in the .env file.")
        print("Make sure your token is valid or username/password are correct.")
        return
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        return
    
    # Analyze the data
    if not daily_data:
        print("No data found for the specified date range.")
        return
    
    print("\nDaily summary:")
    print("-------------")
    
    total_seconds_by_timeline = {}
    
    for day in daily_data:
        date = day['date']
        print(f"\nDate: {date}")
        
        if not day['timelines']:
            print("  No timeline data for this day.")
            continue
            
        day_total_seconds = 0
        
        for timeline_id, timeline_data in day['timelines'].items():
            seconds = timeline_data['total_seconds']
            hours = seconds / 3600
            day_total_seconds += seconds
            
            # Update timeline totals
            if timeline_id not in total_seconds_by_timeline:
                total_seconds_by_timeline[timeline_id] = 0
            total_seconds_by_timeline[timeline_id] += seconds
            
            print(f"  Timeline: {timeline_id}")
            print(f"    Hours: {hours:.2f}")
            print(f"    Activities: {len(timeline_data['activities'])}")
            
            # Print top 3 activities by duration
            if timeline_data['activities']:
                sorted_activities = sorted(
                    timeline_data['activities'], 
                    key=lambda x: x['duration_seconds'], 
                    reverse=True
                )
                
                print("    Top activities:")
                for i, activity in enumerate(sorted_activities[:3], 1):
                    minutes = activity['duration_seconds'] / 60
                    print(f"      {i}. {activity['application']}: {activity['title']} ({minutes:.1f} min)")
        
        print(f"  Total hours for day: {day_total_seconds / 3600:.2f}")
    
    # Print overall summary
    print("\nOverall summary for the last 7 days:")
    print("----------------------------------")
    
    total_hours = sum(total_seconds_by_timeline.values()) / 3600
    print(f"Total tracked hours: {total_hours:.2f}")
    
    print("\nHours by timeline:")
    for timeline_id, seconds in sorted(
        total_seconds_by_timeline.items(),
        key=lambda x: x[1],
        reverse=True
    ):
        hours = seconds / 3600
        percentage = hours / total_hours * 100 if total_hours > 0 else 0
        print(f"  {timeline_id}: {hours:.2f} hours ({percentage:.1f}%)")
    
    # Optional: save to file
    save = input("\nDo you want to save the data to a JSON file? (y/n): ")
    if save.lower() == 'y':
        filename = f"manictime_data_{start_date.date()}_{end_date.date()}.json"
        with open(filename, 'w') as f:
            json.dump(daily_data, f, indent=2)
        print(f"Data saved to {filename}")
    
    print("\nExample completed.")

if __name__ == "__main__":
    main()