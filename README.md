# ManicTime API Python Client

A robust Python wrapper for the ManicTime API that can be used for data analytics projects and applications that integrate with ManicTime time tracking software.

## Installation

```bash
pip install manictime
```

## Features

- Comprehensive wrapper for ManicTime API
- Multiple authentication methods (NTLM, Bearer token)
- Robust error handling and retries
- Structured data models
- Helper methods for analytics use cases
- Configurable caching

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

# Get activities for a date range
start_date = datetime.now() - timedelta(days=7)
end_date = datetime.now()
activities = client.get_activities_for_date_range(
    timeline_id="your-timeline-id",
    start_date=start_date,
    end_date=end_date
)

# Get daily activities across all timelines
daily_data = client.get_daily_activities(start_date, end_date)
```

## Authentication Options

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

## Data Analytics Examples

See the [`examples`](./manictime/examples/) directory for usage scenarios:

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
