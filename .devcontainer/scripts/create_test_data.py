#!/usr/bin/env python3
"""
Script to create test data in ManicTime server for development purposes.
This will populate the server with sample activities and tags.
"""
import os
import sys
import json
import requests
from datetime import datetime, timedelta

def main():
    """Main function to create test data"""
    print("Creating test data for development...")
    
    # Get environment variables or use defaults
    server_url = os.environ.get("MANICTIME_SERVER_URL", "http://manictime-server:8080")
    username = os.environ.get("MANICTIME_USERNAME", "admin")
    password = os.environ.get("MANICTIME_PASSWORD", "admin123")
    
    # Authenticate
    try:
        auth_response = requests.post(
            f"{server_url}/api/token",
            json={"username": username, "password": password}
        )
        auth_response.raise_for_status()
        token_data = auth_response.json()
        
        if "access_token" not in token_data:
            print("Failed to get access token")
            sys.exit(1)
            
        token = token_data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Get timelines
        timelines_response = requests.get(f"{server_url}/api/timelines", headers=headers)
        timelines_response.raise_for_status()
        
        timelines = timelines_response.json()
        if not timelines:
            print("No timelines found. Please run setup-manictime.sh first.")
            sys.exit(1)
        
        # Find Applications timeline
        apps_timeline = next((t for t in timelines if t["name"] == "Applications"), None)
        if not apps_timeline:
            print("Applications timeline not found.")
            sys.exit(1)
            
        timeline_id = apps_timeline["timelineId"]
        
        # Create some tag combinations if they don't exist
        tags_response = requests.get(f"{server_url}/api/tags", headers=headers)
        tags_response.raise_for_status()
        
        existing_tags = tags_response.json()
        existing_tag_names = [t["name"] for t in existing_tags]
        
        # Define tag combinations to create
        tag_combinations = [
            {"name": "Work", "tags": ["Work"], "color": "#4285F4"},
            {"name": "Personal", "tags": ["Personal"], "color": "#34A853"},
            {"name": "Meeting", "tags": ["Meeting"], "color": "#EA4335"},
            {"name": "Development", "tags": ["Development"], "color": "#FBBC05"}
        ]
        
        for tag in tag_combinations:
            if tag["name"] not in existing_tag_names:
                print(f"Creating tag combination: {tag['name']}")
                create_tag_response = requests.post(
                    f"{server_url}/api/tags",
                    headers=headers,
                    json=tag
                )
                create_tag_response.raise_for_status()
        
        # Create sample activities for the past 7 days (if needed)
        # First check if we already have activities to avoid duplicates
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        from_time = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
        
        activities_response = requests.get(
            f"{server_url}/api/timelines/{timeline_id}/activities",
            headers=headers,
            params={
                "fromTime": yesterday.isoformat(),
                "toTime": now.isoformat()
            }
        )
        activities_response.raise_for_status()
        activities_data = activities_response.json()
        
        # If we already have activities for yesterday, don't create more
        if activities_data.get("activities", []):
            print("Activities already exist for recent days. Skipping activity creation.")
            return
        
        # Create sample activities
        print("Creating sample activities...")
        
        # Sample applications
        applications = [
            "Visual Studio Code",
            "Chrome",
            "Terminal",
            "Microsoft Teams",
            "Slack",
            "Excel",
            "PowerPoint",
            "Word",
            "Outlook"
        ]
        
        # Generate activities for the past 7 days
        for day in range(7):
            day_date = now - timedelta(days=day)
            start_time = day_date.replace(hour=9, minute=0, second=0, microsecond=0)
            
            # Create 8 hours of activities for each day
            current_time = start_time
            while (current_time.hour < 17):
                # Random duration between 15 and 60 minutes
                duration_minutes = [15, 30, 45, 60][day % 4]
                end_time = current_time + timedelta(minutes=duration_minutes)
                
                # Select application
                app_index = (day + (current_time.hour - 9)) % len(applications)
                application = applications[app_index]
                
                # Create activity data
                activity = {
                    "start": current_time.isoformat(),
                    "end": end_time.isoformat(),
                    "application": application,
                    "title": f"{application} - Sample Activity",
                }
                
                # Add tag based on application
                if "Code" in application:
                    activity["tags"] = ["Development", "Work"]
                elif "Teams" in application or "Slack" in application:
                    activity["tags"] = ["Meeting", "Work"]
                elif "Chrome" in application:
                    activity["tags"] = ["Work"] if current_time.hour < 12 else ["Personal"]
                else:
                    activity["tags"] = ["Work"]
                
                # Send activity to server
                try:
                    # Note: ManicTime API doesn't typically support direct activity creation
                    # This is for demonstration purposes and might need adjustment
                    # for your specific ManicTime API version
                    activity_response = requests.post(
                        f"{server_url}/api/activities",
                        headers=headers,
                        json=activity
                    )
                    # Don't raise exception as this might not be supported
                    if activity_response.status_code == 404:
                        print("Note: Direct activity creation not supported by this ManicTime server version.")
                        print("Sample activity creation skipped.")
                        return
                except Exception as e:
                    print(f"Activity creation failed: {e}")
                    return
                
                current_time = end_time
        
        print("Test data creation completed!")
        
    except Exception as e:
        print(f"Error creating test data: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()