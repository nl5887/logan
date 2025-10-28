#!/usr/bin/env python3
"""
HTTP Monitor Runner with Configuration Loading

This script loads monitoring configurations from JSON and runs multiple
HTTP monitors asynchronously with enhanced exception tracking.
"""

import asyncio
import json
import logging
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from http_monitor import MonitorConfig, MultiHTTPMonitor, HTTPMonitor


class ConfigLoader:
    """Loads and validates monitoring configuration from JSON"""

    @staticmethod
    def load_from_file(config_path: str) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
            return config
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {e}")

    @staticmethod
    def create_monitor_configs(config_data: Dict[str, Any]) -> List[MonitorConfig]:
        """Convert JSON config to MonitorConfig objects"""
        monitors_config = config_data.get("monitors", [])
        configs = []

        for monitor_data in monitors_config:
            # Handle dynamic timestamp in payload
            payload = monitor_data.get("payload")
            if payload and payload.get("timestamp") == "auto":
                payload["timestamp"] = datetime.now().isoformat()

            config = MonitorConfig(
                url=monitor_data["url"],
                interval=monitor_data.get("interval", 30.0),
                timeout=monitor_data.get("timeout", 10.0),
                max_retries=monitor_data.get("max_retries", 3),
                context_lines=monitor_data.get("context_lines", 10),
                headers=monitor_data.get("headers", {}),
                method=monitor_data.get("method", "GET"),
                payload=payload,
            )
            configs.append(config)

        return configs

    @staticmethod
    def setup_logging(config_data: Dict[str, Any]):
        """Setup logging based on configuration"""
        global_settings = config_data.get("global_settings", {})
        log_level = global_settings.get("log_level", "INFO")
        log_file = global_settings.get("log_file", "http_monitor.log")

        # Configure logging
        numeric_level = getattr(logging, log_level.upper(), logging.INFO)

        # Remove existing handlers
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

        # Setup new handlers
        logging.basicConfig(
            level=numeric_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(log_file)],
        )


class MonitorRunner:
    """Main runner for HTTP monitoring system"""

    def __init__(self, config_path: str = "monitor_config.json"):
        self.config_path = config_path
        self.config_data: Optional[Dict[str, Any]] = None
        self.multi_monitor: Optional[MultiHTTPMonitor] = None
        self.logger = logging.getLogger(__name__)
        self.running = False

    def load_configuration(self):
        """Load and validate configuration"""
        try:
            self.config_data = ConfigLoader.load_from_file(self.config_path)
            ConfigLoader.setup_logging(self.config_data)
            self.logger.info(f"Loaded configuration from {self.config_path}")

            # Validate that we have monitors configured
            if not self.config_data.get("monitors"):
                raise ValueError("No monitors configured in the configuration file")

        except Exception as e:
            print(f"Failed to load configuration: {e}", file=sys.stderr)
            sys.exit(1)

    def create_monitors(self) -> List[MonitorConfig]:
        """Create monitor configurations from loaded config"""
        return ConfigLoader.create_monitor_configs(self.config_data)

    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""

        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating shutdown...")
            self.running = False
            if self.multi_monitor:
                self.multi_monitor.stop_all_monitors()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def run_monitors(self):
        """Run the monitoring system"""
        try:
            monitor_configs = self.create_monitors()
            self.multi_monitor = MultiHTTPMonitor(monitor_configs)

            self.logger.info(f"Starting {len(monitor_configs)} HTTP monitors")
            self.running = True

            # Get monitor duration from config
            global_settings = self.config_data.get("global_settings", {})
            monitor_duration = global_settings.get("monitor_duration")

            if monitor_duration:
                self.logger.info(f"Running monitors for {monitor_duration} seconds")
                await asyncio.wait_for(
                    self.multi_monitor.start_all_monitors(), timeout=monitor_duration
                )
            else:
                self.logger.info("Running monitors indefinitely (Ctrl+C to stop)")
                await self.multi_monitor.start_all_monitors()

        except asyncio.TimeoutError:
            self.logger.info("Monitor duration timeout reached")
        except KeyboardInterrupt:
            self.logger.info("Interrupted by user")
        except Exception as e:
            self.logger.error(f"Unexpected error in monitor runner: {e}")
        finally:
            await self.cleanup()

    async def cleanup(self):
        """Cleanup and export results"""
        if not self.multi_monitor:
            return

        self.logger.info("Cleaning up monitors...")
        self.multi_monitor.stop_all_monitors()

        # Export exceptions if configured
        global_settings = self.config_data.get("global_settings", {})
        if global_settings.get("export_on_exit", True):
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"monitor_exceptions_{timestamp}.json"
                exported_file = self.multi_monitor.export_all_exceptions(filename)
                self.logger.info(f"Exception report exported to: {exported_file}")
            except Exception as e:
                self.logger.error(f"Failed to export exceptions: {e}")

        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print monitoring summary"""
        if not self.multi_monitor:
            return

        all_exceptions = self.multi_monitor.get_all_exceptions()
        total_exceptions = sum(
            len(exceptions) for exceptions in all_exceptions.values()
        )

        print("\n" + "=" * 60)
        print("MONITORING SUMMARY")
        print("=" * 60)
        print(f"Total monitors: {len(self.multi_monitor.monitors)}")
        print(f"Total exceptions captured: {total_exceptions}")
        print()

        for url, exceptions in all_exceptions.items():
            if exceptions:
                print(f"📍 {url}")
                print(f"   └─ {len(exceptions)} exception(s)")

                # Show latest exception details
                latest_exc = exceptions[-1]
                print(
                    f"   └─ Latest: {latest_exc.exception_type} at {latest_exc.timestamp}"
                )
                print(f"      └─ {latest_exc.exception}")

                # Show context if available
                if latest_exc.context_lines:
                    print(f"      └─ Context ({len(latest_exc.context_lines)} lines):")
                    for line in latest_exc.context_lines[-3:]:  # Last 3 context lines
                        print(f"         {line}")
                print()

        if total_exceptions == 0:
            print("✅ No exceptions detected during monitoring period")

        print("=" * 60)


class SimpleMonitorRunner:
    """Simple runner for quick monitoring without config files"""

    @staticmethod
    def run_simple_monitor(
        urls: List[str], interval: float = 30.0, duration: float = 300.0
    ):
        """Run a simple monitor for a list of URLs"""
        configs = []
        for url in urls:
            config = MonitorConfig(
                url=url,
                interval=interval,
                timeout=10.0,
                max_retries=3,
                context_lines=10,
                headers={"User-Agent": "SimpleHTTPMonitor/1.0"},
            )
            configs.append(config)

        async def run():
            multi_monitor = MultiHTTPMonitor(configs)
            try:
                await asyncio.wait_for(
                    multi_monitor.start_all_monitors(), timeout=duration
                )
            except asyncio.TimeoutError:
                print(f"Monitoring completed after {duration} seconds")
            finally:
                multi_monitor.stop_all_monitors()
                filename = multi_monitor.export_all_exceptions()
                print(f"Results exported to: {filename}")

        asyncio.run(run())


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="HTTP Monitor with Exception Tracking")
    parser.add_argument(
        "--config",
        "-c",
        default="monitor_config.json",
        help="Configuration file path (default: monitor_config.json)",
    )
    parser.add_argument(
        "--simple", "-s", nargs="+", help="Simple mode: provide URLs to monitor"
    )
    parser.add_argument(
        "--interval",
        "-i",
        type=float,
        default=30.0,
        help="Interval between requests in simple mode (default: 30.0)",
    )
    parser.add_argument(
        "--duration",
        "-d",
        type=float,
        default=300.0,
        help="Duration to run in simple mode (default: 300.0)",
    )

    args = parser.parse_args()

    if args.simple:
        # Simple mode
        print(f"Running simple monitor for {len(args.simple)} URLs")
        print(f"Interval: {args.interval}s, Duration: {args.duration}s")
        SimpleMonitorRunner.run_simple_monitor(
            args.simple, args.interval, args.duration
        )
    else:
        # Configuration file mode
        runner = MonitorRunner(args.config)
        runner.load_configuration()
        runner.setup_signal_handlers()
        await runner.run_monitors()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)
