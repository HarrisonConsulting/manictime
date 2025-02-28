#!/usr/bin/env python3
"""
Data visualization example for the ManicTime client.
Shows how to generate charts and graphs from ManicTime data.

Requirements:
- pandas
- matplotlib
- seaborn (optional, for better styling)

Install with: pip install pandas matplotlib seaborn
"""

from datetime import datetime, timedelta
import json
from dotenv import load_dotenv
import logging
import os
import sys

# Import the ManicTime client library
from manictime import ManicTimeClient, Config

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Load environment variables from .env file
load_dotenv()

def main():
    """Main function demonstrating data visualization"""
    print("ManicTime API Client - Data Visualization Example")
    print("-----------------------------------------------")
    
    # Check for required packages
    try:
        import pandas as pd
        import matplotlib.pyplot as plt
        try:
            import seaborn as sns
            sns.set(style="darkgrid")
        except ImportError:
            print("Seaborn not found. Using default matplotlib styling.")
    except ImportError:
        print("ERROR: This example requires pandas and matplotlib.")
        print("Install with: pip install pandas matplotlib seaborn")
        return
    
    # Create configuration from environment variables
    config = Config.from_env()
    print(f"Connecting to: {config.server_url}")
    
    # Initialize client
    client = ManicTimeClient(config)
    
    # Time period to analyze (last 30 days by default)
    days_to_analyze = 30
    try:
        if len(sys.argv) > 1:
            days_to_analyze = int(sys.argv[1])
    except ValueError:
        print(f"Invalid days argument. Using default of {days_to_analyze} days.")
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_to_analyze)
    
    print(f"\nFetching daily activities from {start_date.date()} to {end_date.date()}...")
    print(f"This will analyze {days_to_analyze} days of data.")
    
    daily_data = client.get_daily_activities(start_date, end_date)
    print(f"Retrieved data for {len(daily_data)} days.")
    
    if not daily_data:
        print("No data found for the specified date range.")
        return
    
    # Convert to pandas DataFrame
    print("\nProcessing data...")
    
    # Create DataFrames for different types of analysis
    
    # 1. Daily summary DataFrame
    daily_summary = []
    for day in daily_data:
        date = day['date']
        
        # Start with zero hours for this day
        day_record = {'date': date}
        day_record['total_hours'] = 0
        
        # Add hours for each timeline
        for timeline_id, timeline_data in day['timelines'].items():
            hours = timeline_data['total_seconds'] / 3600
            day_record[f'{timeline_id}_hours'] = hours
            day_record['total_hours'] += hours
        
        daily_summary.append(day_record)
    
    # 2. Activities DataFrame (all activities flattened)
    activities = []
    for day in daily_data:
        date = day['date']
        for timeline_id, timeline_data in day['timelines'].items():
            for activity in timeline_data['activities']:
                activities.append({
                    'date': date,
                    'timeline': timeline_id,
                    'application': activity['application'],
                    'title': activity['title'],
                    'start': activity['start'],
                    'end': activity['end'],
                    'hours': activity['duration_seconds'] / 3600
                })
    
    # Create DataFrames
    if daily_summary:
        df_daily = pd.DataFrame(daily_summary)
        df_daily['date'] = pd.to_datetime(df_daily['date'])
        df_daily.set_index('date', inplace=True)
        df_daily.sort_index(inplace=True)
    else:
        print("No daily summary data available.")
        return
        
    if activities:
        df_activities = pd.DataFrame(activities)
        df_activities['date'] = pd.to_datetime(df_activities['date'])
    else:
        print("No activity data available.")
        return
    
    # Create output directory for visualizations
    output_dir = "manictime_visualizations"
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate visualizations
    print("\nGenerating visualizations...")
    
    # 1. Daily hours by timeline
    plt.figure(figsize=(12, 6))
    timeline_columns = [col for col in df_daily.columns if col.endswith('_hours') and col != 'total_hours']
    if timeline_columns:
        df_daily[timeline_columns].plot(kind='bar', stacked=True)
        plt.title(f'Daily Hours by Timeline (Last {days_to_analyze} Days)')
        plt.xlabel('Date')
        plt.ylabel('Hours')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(f"{output_dir}/daily_hours_by_timeline.png")
        print(f"Saved: {output_dir}/daily_hours_by_timeline.png")
    
    # 2. Total hours by day of week
    plt.figure(figsize=(10, 6))
    df_daily['day_of_week'] = df_daily.index.day_name()
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    day_of_week = df_daily.groupby('day_of_week')['total_hours'].mean().reindex(day_order)
    day_of_week.plot(kind='bar')
    plt.title('Average Hours by Day of Week')
    plt.xlabel('Day of Week')
    plt.ylabel('Average Hours')
    plt.tight_layout()
    plt.savefig(f"{output_dir}/hours_by_day_of_week.png")
    print(f"Saved: {output_dir}/hours_by_day_of_week.png")
    
    # 3. Top 10 applications by time
    plt.figure(figsize=(12, 6))
    top_apps = df_activities.groupby('application')['hours'].sum().sort_values(ascending=False).head(10)
    top_apps.plot(kind='bar')
    plt.title('Top 10 Applications by Time Spent')
    plt.xlabel('Application')
    plt.ylabel('Total Hours')
    plt.tight_layout()
    plt.savefig(f"{output_dir}/top_applications.png")
    print(f"Saved: {output_dir}/top_applications.png")
    
    # 4. Hours distribution by hour of day
    plt.figure(figsize=(12, 6))
    df_activities['hour'] = pd.to_datetime(df_activities['start']).dt.hour
    hours_by_hour = df_activities.groupby('hour')['hours'].sum()
    hours_by_hour.plot(kind='bar')
    plt.title('Activity Distribution by Hour of Day')
    plt.xlabel('Hour (24-hour format)')
    plt.ylabel('Total Hours')
    plt.tight_layout()
    plt.savefig(f"{output_dir}/hours_by_hour_of_day.png")
    print(f"Saved: {output_dir}/hours_by_hour_of_day.png")
    
    # 5. Heatmap of activity by day and hour (if we have seaborn)
    try:
        import seaborn as sns
        plt.figure(figsize=(12, 8))
        
        # Create day and hour columns
        df_activities['date_only'] = pd.to_datetime(df_activities['date']).dt.date
        df_activities['hour'] = pd.to_datetime(df_activities['start']).dt.hour
        
        # Create pivot table for the heatmap
        pivot_data = df_activities.pivot_table(
            index='date_only',
            columns='hour',
            values='hours',
            aggfunc='sum',
            fill_value=0
        )
        
        # Create heatmap
        sns.heatmap(pivot_data, cmap='YlOrRd', linewidths=.5)
        plt.title('Activity Heatmap by Day and Hour')
        plt.xlabel('Hour of Day')
        plt.ylabel('Date')
        plt.tight_layout()
        plt.savefig(f"{output_dir}/activity_heatmap.png")
        print(f"Saved: {output_dir}/activity_heatmap.png")
    except ImportError:
        pass
    
    # Export processed data as CSV for further analysis
    df_daily.to_csv(f"{output_dir}/daily_summary.csv")
    df_activities.to_csv(f"{output_dir}/activities.csv")
    print(f"Saved: {output_dir}/daily_summary.csv")
    print(f"Saved: {output_dir}/activities.csv")
    
    print(f"\nAll visualizations and data files saved to the '{output_dir}' directory.")
    print("\nExample completed.")

if __name__ == "__main__":
    main()