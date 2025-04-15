#!/bin/bash
set -e

echo "Setting up ManicTime server for development..."

# Wait for server to be available
echo "Waiting for ManicTime server..."
timeout 60 bash -c 'until curl -s http://manictime-server:8080/api/server/info; do sleep 1; done'

# Create some default timelines for testing if they don't exist
python - << EOF
import requests
import os
import json
import sys

SERVER_URL = os.environ.get("MANICTIME_SERVER_URL", "http://manictime-server:8080")
USERNAME = os.environ.get("MANICTIME_USERNAME", "admin")
PASSWORD = os.environ.get("MANICTIME_PASSWORD", "admin123")

# Authenticate
try:
    auth_response = requests.post(
        f"{SERVER_URL}/api/token",
        json={"username": USERNAME, "password": PASSWORD}
    )
    auth_response.raise_for_status()
    token = auth_response.json().get("access_token")
    
    if not token:
        print("Failed to get access token")
        sys.exit(1)
        
    # Set up headers for subsequent requests
    headers = {"Authorization": f"Bearer {token}"}
    
    # Check if default timelines exist, create if not
    timelines_response = requests.get(f"{SERVER_URL}/api/timelines", headers=headers)
    timelines_response.raise_for_status()
    
    timelines = timelines_response.json()
    timeline_names = [t.get("name") for t in timelines]
    
    # Create default timelines if they don't exist
    default_timelines = ["Applications", "Documents", "Web"]
    
    for timeline in default_timelines:
        if timeline not in timeline_names:
            print(f"Creating timeline: {timeline}")
            create_response = requests.post(
                f"{SERVER_URL}/api/timelines",
                headers=headers,
                json={"name": timeline, "description": f"Default {timeline} timeline"}
            )
            create_response.raise_for_status()
    
    print("ManicTime server setup completed successfully!")
    
except Exception as e:
    print(f"Error setting up ManicTime server: {str(e)}")
    sys.exit(1)
EOF

echo "ManicTime server setup completed!"