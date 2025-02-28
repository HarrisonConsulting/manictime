#!/usr/bin/env python3
"""
Export example for the ManicTime client.
Shows how to export ManicTime data to CSV for use in other tools.
"""

from datetime import datetime, timedelta
import csv
import json
import argparse
from dotenv import load_dotenv
import logging
import os

# Import the ManicTime client library
from manictime import ManicTimeClient, Config
from manictime.exceptions import AuthenticationError, ManicTimeClientError, NotFoundError

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Load environment variables from .env file
load_dotenv()

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Export ManicTime data to CSV files")
    parser.add_argument(
        "--days", 
        type=int, 
        default=30, 
        help="Number of days to export (default: 30)"
    )
    parser.add_argument(
        "--output", 
        type=str, 
        default="manictime_export", 
        help="Output directory (default: manictime_export)"
    )
    parser.add_argument(
        "--format", 
        choices=["csv", "json", "both"], 
        default="csv",
        help="Export format (default: csv)"
    )
    
    return parser.parse_args()

def main():
    """Main function for exporting ManicTime data"""
    args = parse_args()
    
    print("ManicTime API Client - Export to CSV Example")
    print("------------------------------------------")
    
    # Create output directory
    os.makedirs(args.output, exist_ok=True)
    
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
        
        # Get activities for the last N days
        end_date = datetime.now()
        start_date = end_date - timedelta(days=args.days)
        
        print(f"\nFetching daily activities from {start_date.date()} to {end_date.date()}...")
        print(f"This will export {args.days} days of data.")
        
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
    
    if not daily_data:
        print("No data found for the specified date range.")
        return
    
    # Format date range for filenames
    date_range = f"{start_date.date()}_{end_date.date()}"
    
    # Export as JSON if requested
    if args.format in ["json", "both"]:
        json_filename = os.path.join(args.output, f"manictime_data_{date_range}.json")
        with open(json_filename, 'w') as f:
            json.dump(daily_data, f, indent=2)
        print(f"Saved JSON data to: {json_filename}")
    
    # Export as CSV if requested
    if args.format in ["csv", "both"]:
        # Export activities to CSV
        activities_filename = os.path.join(args.output, f"manictime_activities_{date_range}.csv")
        with open(activities_filename, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Write header
            writer.writerow([
                'Date', 
                'Timeline', 
                'Application', 
                'Title', 
                'Start', 
                'End', 
                'Duration (min)',
                'Tags'
            ])
            
            # Write data
            for day in daily_data:
                date = day['date']
                for timeline_id, timeline_data in day['timelines'].items():
                    for activity in timeline_data['activities']:
                        tags = ';'.join(activity.get('tags', []))
                        writer.writerow([
                            date,
                            timeline_id,
                            activity['application'],
                            activity['title'],
                            activity['start'],
                            activity['end'],
                            activity['duration_seconds'] / 60,
                            tags
                        ])
        
        print(f"Saved activity data to: {activities_filename}")
        
        # Export daily summary to CSV
        summary_filename = os.path.join(args.output, f"manictime_daily_summary_{date_range}.csv")
        with open(summary_filename, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Get all timeline IDs
            all_timeline_ids = set()
            for day in daily_data:
                all_timeline_ids.update(day['timelines'].keys())
            
            # Write header
            header = ['Date', 'Total Hours']
            for timeline_id in sorted(all_timeline_ids):
                header.append(f"{timeline_id} Hours")
            writer.writerow(header)
            
            # Write data
            for day in daily_data:
                date = day['date']
                row = [date]
                
                # Calculate total hours for the day
                total_seconds = sum(
                    timeline_data['total_seconds'] 
                    for timeline_data in day['timelines'].values()
                )
                row.append(total_seconds / 3600)
                
                # Add hours for each timeline
                for timeline_id in sorted(all_timeline_ids):
                    if timeline_id in day['timelines']:
                        hours = day['timelines'][timeline_id]['total_seconds'] / 3600
                    else:
                        hours = 0
                    row.append(hours)
                
                writer.writerow(row)
        
        print(f"Saved daily summary to: {summary_filename}")
        
        # Export application summary to CSV
        app_summary_filename = os.path.join(args.output, f"manictime_app_summary_{date_range}.csv")
        
        # Gather application data
        app_data = {}
        for day in daily_data:
            date = day['date']
            for timeline_id, timeline_data in day['timelines'].items():
                for activity in timeline_data['activities']:
                    app_name = activity['application']
                    if app_name not in app_data:
                        app_data[app_name] = {'total_seconds': 0, 'days': {}}
                    
                    # Add to total
                    app_data[app_name]['total_seconds'] += activity['duration_seconds']
                    
                    # Add to daily total
                    if date not in app_data[app_name]['days']:
                        app_data[app_name]['days'][date] = 0
                    app_data[app_name]['days'][date] += activity['duration_seconds']
        
        # Write application summary
        with open(app_summary_filename, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Write header
            writer.writerow(['Application', 'Total Hours', 'Days Used', 'Average Hours Per Day'])
            
            # Write data
            for app_name, data in sorted(
                app_data.items(), 
                key=lambda x: x[1]['total_seconds'], 
                reverse=True
            ):
                total_hours = data['total_seconds'] / 3600
                days_used = len(data['days'])
                avg_hours = total_hours / days_used if days_used > 0 else 0
                
                writer.writerow([
                    app_name,
                    total_hours,
                    days_used,
                    avg_hours
                ])
        
        print(f"Saved application summary to: {app_summary_filename}")
    
    print(f"\nAll export operations completed successfully.")
    print(f"Files saved to: {args.output}/")

if __name__ == "__main__":
    main()