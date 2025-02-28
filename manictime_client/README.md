# ManicTime API Client

A Python client for interacting with the ManicTime Server API. This client provides a simple, Pythonic interface with built-in retry handling and connection management.

## Key Features

- Environment-based configuration
- Automatic request retry with exponential backoff
- Connection pooling and session management
- Strong typing via dataclasses
- Simple NTLM and Bearer token authentication
- Daily activity data organized by timeline

## Installation

```bash
pip install -e .
```

## Configuration

Set the following environment variables in `.env`:

- `MANICTIME_SERVER_URL`: ManicTime server URL
- `MANICTIME_AUTH_TYPE`: Authentication type ('ntlm' or 'bearer')
- `MANICTIME_USERNAME`: Username
- `MANICTIME_PASSWORD`: Password
- `MANICTIME_DOMAIN`: Domain (for NTLM auth)
- `MANICTIME_TOKEN`: Bearer token
- `MANICTIME_TIMEOUT`: Request timeout in seconds

## Usage

### Basic Usage

```python
from manictime import ManicTimeClient, Config
from datetime import datetime, timedelta

# Initialize client
config = Config()
config.server_url = "http://your-manictime-server"
config.auth_type = "bearer"
config.token = "your-access-token"

client = ManicTimeClient(config)

# Get timelines
timelines = client.get_timelines()
print(f"Found {len(timelines)} timelines")

# Get activities for last 24 hours
now = datetime.now()
yesterday = now - timedelta(days=1)

activities = client.get_activities(
    timeline_id="your_timeline_id",
    from_time=yesterday,
    to_time=now
)
```

### Loading Config from Environment Variables

```python
from manictime import ManicTimeClient, Config

# Load config from environment variables in .env file
config = Config.from_env()
client = ManicTimeClient(config)
```

### Getting Daily Activities

```python
from manictime import ManicTimeClient, Config
from datetime import datetime, timedelta
import json

# Initialize client with config from environment variables
config = Config.from_env()
client = ManicTimeClient(config)

# Get activities for last 7 days
end_date = datetime.now()
start_date = end_date - timedelta(days=7)

# Get daily timeline activities
daily_data = client.get_daily_activities(start_date, end_date)

# Process the data
for day in daily_data:
    print(f"Date: {day['date']}")
    for timeline_id, timeline_data in day['timelines'].items():
        print(f"  Timeline: {timeline_id}")
        print(f"  Total time: {timeline_data['total_seconds'] / 3600:.2f} hours")
        print(f"  Activities: {len(timeline_data['activities'])}")
        
        # Access individual activities if needed
        for activity in timeline_data['activities']:
            print(f"    - {activity['title']} ({activity['duration_seconds'] / 60:.1f} min)")
```

### Data Analysis Example

```python
from manictime import ManicTimeClient, Config
from datetime import datetime, timedelta
import pandas as pd
import matplotlib.pyplot as plt

# Initialize client
config = Config.from_env()
client = ManicTimeClient(config)

# Get data for the last 30 days
end_date = datetime.now()
start_date = end_date - timedelta(days=30)
daily_data = client.get_daily_activities(start_date, end_date)

# Convert to pandas DataFrame for analysis
records = []
for day in daily_data:
    date = day['date']
    for timeline_id, timeline_data in day['timelines'].items():
        # Timeline summary
        records.append({
            'date': date,
            'timeline': timeline_id,
            'hours': timeline_data['total_seconds'] / 3600,
            'activity_count': len(timeline_data['activities'])
        })
        
        # Individual activities
        for activity in timeline_data['activities']:
            records.append({
                'date': date,
                'timeline': timeline_id,
                'application': activity['application'],
                'title': activity['title'],
                'minutes': activity['duration_seconds'] / 60,
                'start_time': activity['start'],
                'end_time': activity['end']
            })

# Create DataFrame
df = pd.DataFrame(records)

# Example: Daily hours by timeline
pivot_df = df.pivot_table(
    index='date', 
    columns='timeline', 
    values='hours',
    aggfunc='sum'
)

# Plot
pivot_df.plot(kind='bar', figsize=(12, 6))
plt.title('Daily Hours by Timeline')
plt.xlabel('Date')
plt.ylabel('Hours')
plt.tight_layout()
plt.show()

# Example: Top applications by time spent
app_usage = df.groupby('application')['minutes'].sum().sort_values(ascending=False).head(10)
app_usage.plot(kind='bar', figsize=(10, 6))
plt.title('Top 10 Applications by Time Spent')
plt.xlabel('Application')
plt.ylabel('Minutes')
plt.tight_layout()
plt.show()
```

### Exporting Data

```python
from manictime import ManicTimeClient, Config
from datetime import datetime, timedelta
import json
import csv

# Initialize client
config = Config.from_env()
client = ManicTimeClient(config)

# Get data for current month
now = datetime.now()
start_date = datetime(now.year, now.month, 1)
daily_data = client.get_daily_activities(start_date, now)

# Export as JSON
with open('manictime_data.json', 'w') as f:
    json.dump(daily_data, f, indent=2)

# Export as CSV (flattened)
with open('manictime_activities.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    # Write header
    writer.writerow(['Date', 'Timeline', 'Application', 'Title', 'Start', 'End', 'Duration (min)'])
    
    # Write data
    for day in daily_data:
        date = day['date']
        for timeline_id, timeline_data in day['timelines'].items():
            for activity in timeline_data['activities']:
                writer.writerow([
                    date,
                    timeline_id,
                    activity['application'],
                    activity['title'],
                    activity['start'],
                    activity['end'],
                    activity['duration_seconds'] / 60
                ])
```

## Testing

```bash
pytest tests/
```

## Why Use This Client?

This Python implementation complements the official C# client by providing:

1. A lightweight library-first approach (vs CLI-first)
2. Native Python data structures and typing
3. Simplified configuration via environment variables
4. Built-in resilience with retry handling
5. Daily activity data organized for easy analysis and visualization