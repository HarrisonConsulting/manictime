# ManicTime Python Client Examples

This directory contains example scripts demonstrating how to use the ManicTime Python client for various common tasks.

## Requirements

All examples require the basic ManicTime client to be installed:

```bash
pip install -e .
```

Some examples have additional requirements that are noted in their documentation.

## Available Examples

### 1. Basic Usage (`basic_usage.py`)

Demonstrates how to connect to the ManicTime API and retrieve basic timeline data.

```bash
# From the manictime_client directory
python examples/basic_usage.py

# Or as a module
python -m examples.basic_usage
```

### 2. Daily Activities (`daily_activities.py`)

Shows how to retrieve and analyze activity data organized by day.

```bash
# From the manictime_client directory
python examples/daily_activities.py

# Or as a module
python -m examples.daily_activities
```

### 3. Data Visualization (`data_visualization.py`)

Creates charts and visualizations from ManicTime data.

Requirements:
- pandas
- matplotlib
- seaborn (optional, for better styling)

```bash
# Install dependencies
pip install pandas matplotlib seaborn

# From the manictime_client directory
# Run with default settings (30 days)
python examples/data_visualization.py

# Run with custom days
python examples/data_visualization.py 14  # analyze last 14 days

# Or as a module
python -m examples.data_visualization
python -m examples.data_visualization 14
```

Output will be saved to a `manictime_visualizations` directory.

### 4. Export to CSV (`export_to_csv.py`)

Exports ManicTime data to CSV or JSON files for further analysis in other tools.

```bash
# From the manictime_client directory
# Export last 30 days to CSV
python examples/export_to_csv.py

# Export with custom options
python examples/export_to_csv.py --days 14 --output my_data --format both

# Or as a module
python -m examples.export_to_csv
python -m examples.export_to_csv --days 14 --output my_data --format both
```

Command line options:
- `--days`: Number of days to export (default: 30)
- `--output`: Output directory (default: manictime_export)
- `--format`: Export format: csv, json, or both (default: csv)

## Environment Setup

All examples load configuration from environment variables. Before running, make sure you have a `.env` file in the project root with your ManicTime server settings:

```
MANICTIME_SERVER_URL=http://your-manictime-server
MANICTIME_AUTH_TYPE=bearer  # or ntlm
MANICTIME_TOKEN=your-access-token  # for bearer auth
# Alternatively for username/password auth:
# MANICTIME_USERNAME=your-username
# MANICTIME_PASSWORD=your-password
# MANICTIME_DOMAIN=your-domain  # for NTLM auth
```