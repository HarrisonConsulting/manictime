# ManicTime Python API Client

A robust Python wrapper for the ManicTime API that can be used for data analytics projects and applications that integrate with ManicTime time tracking software.

## Installation

```bash
pip install manictime
```

## Features

- Comprehensive wrapper for ManicTime API
- Multiple authentication methods (NTLM, Bearer token)
- Robust error handling and retries with backoff
- Structured data models using dataclasses 
- Helper methods for analytics use cases
- 100% test coverage

## Quick Start

```python
from manictime import ManicTimeClient, Config
from datetime import datetime, timedelta

# Configure the client
config = Config(
    server_url="https://your-manictime-server.com",
    auth_type="bearer",
    token="your-access-token"
)

# Initialize the client
client = ManicTimeClient(config)

# Get all timelines
timelines = client.get_timelines()

# Get activities for a specific timeline and date range
start_date = datetime.now() - timedelta(days=7)
end_date = datetime.now()
activities = client.get_activities_for_date_range(
    timeline_id="your-timeline-id",
    start_date=start_date,
    end_date=end_date
)

# Process activity data
for activity in activities:
    print(f"{activity.start} - {activity.end}: {activity.title} ({activity.application})")
    print(f"Duration: {activity.duration}")
    if activity.tags:
        print(f"Tags: {', '.join(activity.tags)}")
    print("---")
```

## Authentication Options

### Environment Variables

The client can be configured using environment variables:

```bash
MANICTIME_SERVER_URL="https://your-manictime-server.com"
MANICTIME_AUTH_TYPE="bearer"
MANICTIME_TOKEN="your-access-token"
MANICTIME_USERNAME="your-username"  # Alternative to token
MANICTIME_PASSWORD="your-password"  # Alternative to token
MANICTIME_DOMAIN="your-domain"      # For NTLM auth
MANICTIME_TIMEOUT=30                # Request timeout in seconds
```

Load from environment:

```python
from manictime import ManicTimeClient, Config

# Load config from environment variables
config = Config.from_env()
client = ManicTimeClient(config)
```

### Bearer Token Authentication

```python
config = Config(
    server_url="https://api.manictime.com",
    auth_type="bearer",
    token="your-access-token"
)
```

### Username/Password Authentication

```python
config = Config(
    server_url="https://your-manictime-server.com",
    auth_type="bearer",
    username="your-username",
    password="your-password"
)
```

### Windows Authentication (NTLM)

```python
config = Config(
    server_url="https://your-manictime-server.com",
    auth_type="ntlm",
    username="your-username",
    password="your-password",
    domain="your-domain"  # Optional
)
```

## Working with Timelines

```python
# Get all available timelines
timelines = client.get_timelines()

# Find timeline by name
def find_timeline_by_name(timelines, name):
    for timeline in timelines:
        if timeline.get("name") == name:
            return timeline
    return None

# Get Computer Usage timeline
computer_timeline = find_timeline_by_name(timelines, "Computer Usage")
if computer_timeline:
    timeline_id = computer_timeline.get("timelineId")
    # Use timeline_id for further queries
```

## Getting Activities

### Simple Activity Query

```python
# Get activities for a specific time range
from datetime import datetime, timedelta

# Time range: yesterday to today
today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
yesterday = today - timedelta(days=1)

# Get activities for a specific timeline
activities_data = client.get_activities(
    timeline_id="your-timeline-id", 
    from_time=yesterday,
    to_time=today
)

# Activities response contains a dict with 'activities' list
activity_list = activities_data.get("activities", [])
```

### Working with Date Ranges

```python
# Get activities for a longer date range (handles pagination automatically)
start_date = datetime(2023, 1, 1)
end_date = datetime(2023, 1, 31)

# Returns list of Activity objects
activities = client.get_activities_for_date_range(
    timeline_id="your-timeline-id",
    start_date=start_date,
    end_date=end_date,
    batch_size=timedelta(days=7)  # Optional: adjust batch size for pagination
)

# Calculate total duration
total_duration = sum((activity.duration for activity in activities), timedelta())
print(f"Total tracked time: {total_duration}")

# Group activities by application
apps = {}
for activity in activities:
    app_name = activity.application
    apps[app_name] = apps.get(app_name, timedelta()) + activity.duration

# Print summary by application
for app_name, duration in sorted(apps.items(), key=lambda x: x[1], reverse=True):
    print(f"{app_name}: {duration}")
```

### Daily Activity Reports

```python
# Get daily activities across all timelines
start_date = datetime(2023, 1, 1)
end_date = datetime(2023, 1, 7)

daily_data = client.get_daily_activities(start_date, end_date)

# Process daily data
for day in daily_data:
    date = day["date"]
    print(f"=== Activities for {date} ===")
    
    for timeline_id, timeline_data in day["timelines"].items():
        total_seconds = timeline_data["total_seconds"]
        total_hours = total_seconds / 3600
        print(f"{timeline_id}: {total_hours:.2f} hours")
        
        # List top 5 activities for this timeline
        sorted_activities = sorted(
            timeline_data["activities"], 
            key=lambda a: a["duration_seconds"],
            reverse=True
        )
        
        for i, activity in enumerate(sorted_activities[:5], 1):
            duration_hours = activity["duration_seconds"] / 3600
            print(f"  {i}. {activity['title']} - {duration_hours:.2f} hours")
            
        print()
```

## Error Handling

The client includes robust error handling for common API issues:

```python
from manictime import ManicTimeClient, Config
from manictime import AuthenticationError, NotFoundError, ManicTimeClientError

try:
    config = Config(
        server_url="https://your-manictime-server.com",
        auth_type="bearer",
        token="invalid-token"
    )
    client = ManicTimeClient(config)
    
    # This will raise an AuthenticationError if token is invalid
    client.get_timelines()
    
except AuthenticationError:
    print("Authentication failed - check your credentials")
except NotFoundError as e:
    print(f"Resource not found: {e}")
except ManicTimeClientError as e:
    print(f"API error: {e}")
```

## Data Models

The client includes data models for common ManicTime entities:

```python
from manictime import Activity, Timeline, TagCombination

# Creating an Activity object manually
from datetime import datetime, timedelta

activity = Activity(
    start=datetime(2023, 1, 1, 9, 0),
    end=datetime(2023, 1, 1, 9, 30),
    title="Code review",
    application="Visual Studio Code",
    tags=["Work", "Development"]
)

# The duration is calculated automatically
print(activity.duration)  # timedelta(minutes=30)
```

## Example Use Cases

### Exporting to Pandas DataFrame

```python
import pandas as pd
from manictime import ManicTimeClient, Config
from datetime import datetime, timedelta

# Initialize client
config = Config.from_env()
client = ManicTimeClient(config)

# Get activities
start_date = datetime.now() - timedelta(days=30)
end_date = datetime.now()
activities = client.get_activities_for_date_range(
    "your-timeline-id", 
    start_date, 
    end_date
)

# Convert to DataFrame
data = [
    {
        "start": activity.start,
        "end": activity.end,
        "title": activity.title,
        "application": activity.application,
        "duration_minutes": activity.duration.total_seconds() / 60,
        "tags": ", ".join(activity.tags) if activity.tags else "",
    }
    for activity in activities
]

df = pd.DataFrame(data)

# Example analysis
# Group by application and calculate total duration
app_summary = df.groupby("application")["duration_minutes"].sum().sort_values(ascending=False)
print(app_summary)
```

### Creating Activity Visualizations

```python
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime, timedelta

# Assuming df is a DataFrame created from activities as shown above

# Plot total hours by day
df["date"] = df["start"].dt.date
daily_hours = df.groupby("date")["duration_minutes"].sum() / 60

plt.figure(figsize=(12, 6))
daily_hours.plot(kind="bar")
plt.title("Hours Tracked by Day")
plt.xlabel("Date")
plt.ylabel("Hours")
plt.tight_layout()
plt.savefig("daily_hours.png")

# Plot application usage breakdown
top_apps = df.groupby("application")["duration_minutes"].sum().nlargest(10) / 60

plt.figure(figsize=(10, 6))
top_apps.plot(kind="pie", autopct="%1.1f%%")
plt.title("Top 10 Applications by Usage")
plt.ylabel("")
plt.tight_layout()
plt.savefig("app_usage.png")
```

## For More Examples

See the [`examples`](./examples/) directory for additional usage scenarios:

- Basic usage examples
- Daily activity reporting
- Data visualization with Matplotlib
- Exporting data to CSV

## Documentation

For more information on ManicTime API, see the [official documentation](https://docs.manictime.com/server/api/cloud-authentication).

## Contributing

Contributions are welcome! Please see our contributing guidelines.

## License

[MIT License](LICENSE)