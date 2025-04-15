"""Command-line interface for the ManicTime Python library."""
import sys
import os
import argparse
import logging
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path
import textwrap

from . import __version__
from .client import ManicTimeClient
from .config import Config
from .oauth import OAuthClient
from .webhook import WebhookManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("manictime.cli")


class ManicTimeCLI:
    """Main CLI class for ManicTime operations"""
    
    def __init__(self):
        """Initialize CLI parser and commands"""
        self.parser = self._create_parser()
        self.config = None
        self.client = None
        
    def _create_parser(self) -> argparse.ArgumentParser:
        """Create and configure argument parser"""
        # Main parser
        parser = argparse.ArgumentParser(
            description="ManicTime API Client",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=textwrap.dedent("""
                Environment variables:
                  MANICTIME_SERVER_URL - Server URL
                  MANICTIME_AUTH_TYPE - Auth type (bearer, ntlm)
                  MANICTIME_USERNAME - Username
                  MANICTIME_PASSWORD - Password
                  MANICTIME_TOKEN - Bearer token
                  MANICTIME_DOMAIN - Domain for NTLM auth
                  
                Examples:
                  # List timelines
                  manictime timelines list
                  
                  # Get activities
                  manictime activities get --timeline-id "timeline-id" --from "2023-01-01" --to "2023-01-02"
                  
                  # Export activities to CSV
                  manictime activities export --timeline-id "timeline-id" --from "2023-01-01" --format csv --output activities.csv
            """)
        )
        parser.add_argument("--version", action="version", version=f"ManicTime CLI {__version__}")
        parser.add_argument("--server", dest="server_url", help="ManicTime server URL")
        parser.add_argument("--debug", action="store_true", help="Enable debug logging")
        
        # Auth group
        auth_group = parser.add_argument_group("Authentication")
        auth_group.add_argument("--auth-type", choices=["bearer", "ntlm", "oauth"], help="Authentication type")
        auth_group.add_argument("--username", help="Username for authentication")
        auth_group.add_argument("--password", help="Password for authentication")
        auth_group.add_argument("--token", help="Bearer token for authentication")
        auth_group.add_argument("--domain", help="Domain for NTLM authentication")
        auth_group.add_argument("--client-id", help="OAuth client ID")
        auth_group.add_argument("--client-secret", help="OAuth client secret")
        
        # Subparsers for commands
        subparsers = parser.add_subparsers(dest="command", help="Command to execute")
        
        # Auth command
        auth_parser = subparsers.add_parser("auth", help="Authentication commands")
        auth_subparsers = auth_parser.add_subparsers(dest="auth_command")
        
        # Auth login command
        login_parser = auth_subparsers.add_parser("login", help="Log in to ManicTime server")
        login_parser.add_argument("--save", action="store_true", help="Save authentication token")
        
        # Auth logout command
        logout_parser = auth_subparsers.add_parser("logout", help="Log out from ManicTime server")
        
        # Auth status command
        status_parser = auth_subparsers.add_parser("status", help="Check authentication status")
        
        # Timelines command
        timelines_parser = subparsers.add_parser("timelines", help="Timeline operations")
        timelines_subparsers = timelines_parser.add_subparsers(dest="timelines_command")
        
        # Timelines list command
        list_timelines_parser = timelines_subparsers.add_parser("list", help="List timelines")
        list_timelines_parser.add_argument("--format", choices=["json", "table"], default="table", 
                                          help="Output format")
        
        # Timelines get command
        get_timeline_parser = timelines_subparsers.add_parser("get", help="Get timeline details")
        get_timeline_parser.add_argument("timeline_id", help="Timeline ID")
        get_timeline_parser.add_argument("--format", choices=["json", "table"], default="table", 
                                        help="Output format")
        
        # Activities command
        activities_parser = subparsers.add_parser("activities", help="Activity operations")
        activities_subparsers = activities_parser.add_subparsers(dest="activities_command")
        
        # Activities get command
        get_activities_parser = activities_subparsers.add_parser("get", help="Get activities")
        get_activities_parser.add_argument("--timeline-id", required=True, help="Timeline ID")
        get_activities_parser.add_argument("--from", dest="from_date", required=True, 
                                          help="Start date (YYYY-MM-DD)")
        get_activities_parser.add_argument("--to", dest="to_date", 
                                          help="End date (YYYY-MM-DD), defaults to today")
        get_activities_parser.add_argument("--format", choices=["json", "table"], default="table", 
                                          help="Output format")
        get_activities_parser.add_argument("--limit", type=int, help="Limit number of activities")
        
        # Activities stats command
        stats_activities_parser = activities_subparsers.add_parser("stats", 
                                                                help="Get activity statistics")
        stats_activities_parser.add_argument("--timeline-id", required=True, help="Timeline ID")
        stats_activities_parser.add_argument("--from", dest="from_date", required=True, 
                                            help="Start date (YYYY-MM-DD)")
        stats_activities_parser.add_argument("--to", dest="to_date", 
                                            help="End date (YYYY-MM-DD), defaults to today")
        
        # Activities export command
        export_activities_parser = activities_subparsers.add_parser("export", 
                                                                  help="Export activities")
        export_activities_parser.add_argument("--timeline-id", required=True, help="Timeline ID")
        export_activities_parser.add_argument("--from", dest="from_date", required=True, 
                                             help="Start date (YYYY-MM-DD)")
        export_activities_parser.add_argument("--to", dest="to_date", 
                                             help="End date (YYYY-MM-DD), defaults to today")
        export_activities_parser.add_argument("--format", choices=["csv", "json", "excel", "html"], 
                                            default="csv", help="Export format")
        export_activities_parser.add_argument("--output", required=True, help="Output file path")
        
        # Tags command
        tags_parser = subparsers.add_parser("tags", help="Tag operations")
        tags_subparsers = tags_parser.add_subparsers(dest="tags_command")
        
        # Tags list command
        list_tags_parser = tags_subparsers.add_parser("list", help="List tag combinations")
        list_tags_parser.add_argument("--format", choices=["json", "table"], default="table", 
                                     help="Output format")
        
        # Tags create command
        create_tag_parser = tags_subparsers.add_parser("create", help="Create tag combination")
        create_tag_parser.add_argument("--name", required=True, help="Tag combination name")
        create_tag_parser.add_argument("--tags", required=True, nargs="+", 
                                      help="Tags (space-separated)")
        create_tag_parser.add_argument("--color", help="Color (hex code)")
        create_tag_parser.add_argument("--description", help="Description")
        
        # Tags update command
        update_tag_parser = tags_subparsers.add_parser("update", help="Update tag combination")
        update_tag_parser.add_argument("combination_id", help="Tag combination ID")
        update_tag_parser.add_argument("--name", help="New name")
        update_tag_parser.add_argument("--tags", nargs="+", help="New tags (space-separated)")
        update_tag_parser.add_argument("--color", help="New color (hex code)")
        update_tag_parser.add_argument("--description", help="New description")
        
        # Tags delete command
        delete_tag_parser = tags_subparsers.add_parser("delete", help="Delete tag combination")
        delete_tag_parser.add_argument("combination_id", help="Tag combination ID")
        
        # Webhooks command
        webhooks_parser = subparsers.add_parser("webhooks", help="Webhook operations")
        webhooks_subparsers = webhooks_parser.add_subparsers(dest="webhooks_command")
        
        # Webhooks list command
        list_webhooks_parser = webhooks_subparsers.add_parser("list", help="List webhooks")
        list_webhooks_parser.add_argument("--format", choices=["json", "table"], default="table", 
                                         help="Output format")
        
        # Webhooks create command
        create_webhook_parser = webhooks_subparsers.add_parser("create", help="Create webhook")
        create_webhook_parser.add_argument("--url", required=True, help="Webhook URL")
        create_webhook_parser.add_argument("--events", required=True, nargs="+", 
                                          help="Events (space-separated)")
        create_webhook_parser.add_argument("--secret", help="Secret for signature verification")
        create_webhook_parser.add_argument("--description", help="Description")
        
        # Webhooks update command
        update_webhook_parser = webhooks_subparsers.add_parser("update", help="Update webhook")
        update_webhook_parser.add_argument("webhook_id", help="Webhook ID")
        update_webhook_parser.add_argument("--url", help="New URL")
        update_webhook_parser.add_argument("--events", nargs="+", help="New events (space-separated)")
        update_webhook_parser.add_argument("--secret", help="New secret")
        update_webhook_parser.add_argument("--description", help="New description")
        
        # Webhooks delete command
        delete_webhook_parser = webhooks_subparsers.add_parser("delete", help="Delete webhook")
        delete_webhook_parser.add_argument("webhook_id", help="Webhook ID")
        
        # Webhooks test command
        test_webhook_parser = webhooks_subparsers.add_parser("test", help="Test webhook")
        test_webhook_parser.add_argument("webhook_id", help="Webhook ID")
        
        return parser
        
    def _setup_logging(self, debug: bool) -> None:
        """Configure logging level"""
        level = logging.DEBUG if debug else logging.INFO
        logging.getLogger("manictime").setLevel(level)
        
    def _create_config(self, args) -> Config:
        """Create configuration from args and environment"""
        config = Config(
            server_url=args.server_url,
            auth_type=args.auth_type,
            username=args.username,
            password=args.password,
            domain=args.domain,
            token=args.token
        )
        
        # If auth_type is oauth, handle OAuth flow
        if args.auth_type == "oauth":
            if not args.client_id:
                logger.error("Client ID is required for OAuth authentication")
                sys.exit(1)
                
            try:
                oauth_client = OAuthClient(
                    client_id=args.client_id,
                    client_secret=args.client_secret or "",
                    auth_url=config.server_url.rstrip("/") + "/identity"
                )
                
                token = oauth_client.get_access_token()
                config.token = token
                config.auth_type = "bearer"
                
                logger.info("OAuth authentication successful")
            except Exception as e:
                logger.error(f"OAuth authentication failed: {str(e)}")
                sys.exit(1)
        
        return config
        
    def _create_client(self, config: Config) -> ManicTimeClient:
        """Create ManicTime client from config"""
        return ManicTimeClient(config)
        
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string in YYYY-MM-DD format"""
        if not date_str:
            return None
            
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            logger.error(f"Invalid date format: {date_str}, expected YYYY-MM-DD")
            sys.exit(1)
            
    def _format_output_table(self, headers: List[str], rows: List[List[str]]) -> str:
        """Format output as ASCII table"""
        # Calculate column widths
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(cell)))
                
        # Create separator line
        sep = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
        
        # Create header
        header = "|" + "|".join(f" {h:<{col_widths[i]}} " for i, h in enumerate(headers)) + "|"
        
        # Create rows
        table_rows = []
        for row in rows:
            table_rows.append("|" + "|".join(f" {str(c):<{col_widths[i]}} " for i, c in enumerate(row)) + "|")
            
        # Combine all parts
        return "\n".join([sep, header, sep] + table_rows + [sep])
    
    def _handle_auth_commands(self, args) -> None:
        """Handle auth subcommands"""
        if args.auth_command == "login":
            # Set up config and client
            self.config = self._create_config(args)
            self.client = self._create_client(self.config)
            
            logger.info("Login successful")
            
        elif args.auth_command == "logout":
            # Implement logout logic (e.g., remove stored tokens)
            if args.auth_type == "oauth":
                try:
                    oauth_client = OAuthClient(
                        client_id=args.client_id or "",
                        client_secret=args.client_secret or "",
                        auth_url=args.server_url.rstrip("/") + "/identity"
                    )
                    oauth_client.logout()
                    logger.info("Logout successful")
                except Exception as e:
                    logger.error(f"Logout failed: {str(e)}")
                    sys.exit(1)
            else:
                logger.info("Logout not applicable for current authentication type")
                
        elif args.auth_command == "status":
            # Set up config and client
            self.config = self._create_config(args)
            self.client = self._create_client(self.config)
            
            # Check authentication
            try:
                # Try to make a simple API call to verify credentials
                self.client.get_timelines()
                logger.info("Authentication status: Authenticated")
            except Exception as e:
                logger.info(f"Authentication status: Not authenticated ({str(e)})")
                sys.exit(1)
                
    def _handle_timelines_commands(self, args) -> None:
        """Handle timelines subcommands"""
        if args.timelines_command == "list":
            timelines = self.client.get_timelines()
            
            if args.format == "json":
                print(json.dumps(timelines, indent=2))
            else:
                headers = ["ID", "Name", "Description"]
                rows = []
                for timeline in timelines:
                    rows.append([
                        timeline.get("timelineId", ""),
                        timeline.get("name", ""),
                        timeline.get("description", "")
                    ])
                print(self._format_output_table(headers, rows))
                
        elif args.timelines_command == "get":
            # Get timeline details (not directly supported by API, so we get all and filter)
            timelines = self.client.get_timelines()
            timeline = next((t for t in timelines if t.get("timelineId") == args.timeline_id), None)
            
            if not timeline:
                logger.error(f"Timeline not found: {args.timeline_id}")
                sys.exit(1)
                
            if args.format == "json":
                print(json.dumps(timeline, indent=2))
            else:
                # Display timeline details in table format
                headers = ["Property", "Value"]
                rows = [[k, v] for k, v in timeline.items()]
                print(self._format_output_table(headers, rows))
                
    def _handle_activities_commands(self, args) -> None:
        """Handle activities subcommands"""
        if args.activities_command in ["get", "stats", "export"]:
            # Parse dates
            from_date = self._parse_date(args.from_date)
            if not from_date:
                logger.error("From date is required")
                sys.exit(1)
                
            to_date = self._parse_date(args.to_date) or datetime.now()
            
            # Get activities
            activities = self.client.get_activities_for_date_range(
                timeline_id=args.timeline_id,
                start_date=from_date,
                end_date=to_date
            )
            
            # Apply limit if specified
            if hasattr(args, "limit") and args.limit:
                activities = activities[:args.limit]
                
            if args.activities_command == "get":
                if args.format == "json":
                    # Convert activities to dictionaries
                    activity_dicts = [
                        {
                            "start": a.start.isoformat(),
                            "end": a.end.isoformat(),
                            "duration": str(a.duration),
                            "title": a.title,
                            "application": a.application,
                            "tags": a.tags,
                            "notes": a.notes
                        }
                        for a in activities
                    ]
                    print(json.dumps(activity_dicts, indent=2))
                else:
                    headers = ["Start", "End", "Duration", "Application", "Title", "Tags"]
                    rows = []
                    for activity in activities:
                        rows.append([
                            activity.start.strftime("%Y-%m-%d %H:%M:%S"),
                            activity.end.strftime("%Y-%m-%d %H:%M:%S"),
                            str(activity.duration).split('.')[0],  # Remove microseconds
                            activity.application,
                            activity.title[:30] + "..." if len(activity.title) > 33 else activity.title,
                            ", ".join(activity.tags)
                        ])
                    print(self._format_output_table(headers, rows))
                    
            elif args.activities_command == "stats":
                stats = self.client.get_activity_statistics(activities)
                
                # Print statistics
                print(f"Total activities: {stats['total_count']}")
                print(f"Total duration: {timedelta(seconds=stats['total_duration_seconds'])}")
                print(f"Average duration: {timedelta(seconds=stats['average_duration_seconds'])}")
                print(f"Min duration: {timedelta(seconds=stats['min_duration_seconds'])}")
                print(f"Max duration: {timedelta(seconds=stats['max_duration_seconds'])}")
                print(f"Total days: {stats['total_days']}")
                print("\nTop applications:")
                for app, duration in stats["applications"]["durations"].items():
                    print(f"  {app}: {timedelta(seconds=duration)}")
                print("\nTop tags:")
                for tag, duration in stats["tags"]["durations"].items():
                    print(f"  {tag}: {timedelta(seconds=duration)}")
                    
            elif args.activities_command == "export":
                # Export activities
                output_path = args.output
                
                if args.format == "csv":
                    self.client.export_activities_to_csv(activities, output_path)
                elif args.format == "json":
                    self.client.export_activities_to_json(activities, output_path)
                elif args.format == "excel":
                    self.client.export_activities_to_excel(activities, output_path)
                elif args.format == "html":
                    self.client.export_activities_to_html(activities, output_path)
                    
                logger.info(f"Exported {len(activities)} activities to {output_path}")
                
    def _handle_tags_commands(self, args) -> None:
        """Handle tags subcommands"""
        if args.tags_command == "list":
            tags = self.client.get_tag_combinations()
            
            if args.format == "json":
                print(json.dumps(tags, indent=2))
            else:
                headers = ["ID", "Name", "Tags"]
                rows = []
                for tag in tags:
                    rows.append([
                        tag.get("combinationId", ""),
                        tag.get("name", ""),
                        ", ".join(tag.get("tags", []))
                    ])
                print(self._format_output_table(headers, rows))
                
        elif args.tags_command == "create":
            result = self.client.create_tag_combination(
                name=args.name,
                tags=args.tags,
                description=args.description,
                color=args.color
            )
            logger.info(f"Tag combination created with ID: {result.get('combinationId')}")
            
        elif args.tags_command == "update":
            result = self.client.update_tag_combination(
                combination_id=args.combination_id,
                name=args.name,
                tags=args.tags,
                description=args.description,
                color=args.color
            )
            logger.info(f"Tag combination updated: {args.combination_id}")
            
        elif args.tags_command == "delete":
            self.client.delete_tag_combination(args.combination_id)
            logger.info(f"Tag combination deleted: {args.combination_id}")
            
    def _handle_webhooks_commands(self, args) -> None:
        """Handle webhooks subcommands"""
        # Create webhook manager
        webhook_manager = WebhookManager(self.client)
        
        if args.webhooks_command == "list":
            webhooks = webhook_manager.get_webhooks()
            
            if args.format == "json":
                print(json.dumps(webhooks, indent=2))
            else:
                headers = ["ID", "URL", "Events"]
                rows = []
                for webhook in webhooks:
                    rows.append([
                        webhook.get("webhookId", ""),
                        webhook.get("url", ""),
                        ", ".join(webhook.get("events", []))
                    ])
                print(self._format_output_table(headers, rows))
                
        elif args.webhooks_command == "create":
            result = webhook_manager.register_webhook(
                url=args.url,
                events=args.events,
                secret=args.secret,
                description=args.description
            )
            logger.info(f"Webhook created with ID: {result.get('webhookId')}")
            
        elif args.webhooks_command == "update":
            result = webhook_manager.update_webhook(
                webhook_id=args.webhook_id,
                url=args.url,
                events=args.events,
                secret=args.secret,
                description=args.description
            )
            logger.info(f"Webhook updated: {args.webhook_id}")
            
        elif args.webhooks_command == "delete":
            webhook_manager.delete_webhook(args.webhook_id)
            logger.info(f"Webhook deleted: {args.webhook_id}")
            
        elif args.webhooks_command == "test":
            result = webhook_manager.test_webhook(args.webhook_id)
            logger.info(f"Webhook test sent: {args.webhook_id}")
            print(json.dumps(result, indent=2))
            
    def run(self, args=None) -> None:
        """Run CLI with args"""
        args = self.parser.parse_args(args)
        
        # Handle no command
        if not args.command:
            self.parser.print_help()
            sys.exit(0)
            
        # Set up logging
        self._setup_logging(args.debug)
        
        # Auth commands don't need a client yet
        if args.command == "auth":
            self._handle_auth_commands(args)
            sys.exit(0)
            
        # All other commands need a client
        self.config = self._create_config(args)
        self.client = self._create_client(self.config)
        
        # Handle commands
        if args.command == "timelines":
            self._handle_timelines_commands(args)
        elif args.command == "activities":
            self._handle_activities_commands(args)
        elif args.command == "tags":
            self._handle_tags_commands(args)
        elif args.command == "webhooks":
            self._handle_webhooks_commands(args)


def main():
    """Main entry point for CLI"""
    try:
        cli = ManicTimeCLI()
        cli.run()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        if logger.getEffectiveLevel() == logging.DEBUG:
            import traceback
            traceback.print_exc()
        sys.exit(1)
    
    
if __name__ == "__main__":
    main()