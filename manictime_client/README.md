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
client = ManicTimeClient(config)

# Get activities for last 24 hours
now = datetime.now()
yesterday = now - timedelta(days=1)

activities = client.get_activities(
    timeline_id="your_timeline_id",
    from_time=yesterday,
    to_time=now
)
```

### Getting Daily Activities

```python
from manictime import ManicTimeClient, Config
from datetime import datetime, timedelta

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