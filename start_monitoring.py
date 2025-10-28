#!/usr/bin/env python3
"""
Simple Starter Script for HTTP Stream Monitoring with Exception Yielding

This script shows the simplest way to start monitoring HTTP endpoints
and handle exceptions as they occur in real-time.

Usage:
    python start_monitoring.py
    python start_monitoring.py --url https://example.com/api
    python start_monitoring.py --urls https://api1.com https://api2.com
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime
from typing import List

# Configure simple logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SimpleStreamMonitor:
    """Simple streaming monitor that yields exceptions in real-time"""

    def __init__(self, urls: List[str], interval: float = 30.0):
        self.urls = urls
        self.interval = interval
        self.running = False

    async def start_monitoring(self):
        """Start monitoring and yield exceptions as they occur"""
        from http_monitor import MonitorConfig, MultiHTTPMonitor

        # Create monitor configurations
        configs = []
        for url in self.urls:
            config = MonitorConfig(
                url=url,
                interval=self.interval,
                timeout=10.0,
                max_retries=3,
                context_lines=10,
                headers={"User-Agent": "StreamMonitor/1.0"},
            )
            configs.append(config)

        # Create multi-monitor
        multi_monitor = MultiHTTPMonitor(configs)
        self.running = True

        logger.info(f"🚀 Starting monitoring for {len(self.urls)} URLs")
        logger.info(f"📊 Check interval: {self.interval} seconds")

        try:
            # Start streaming exceptions
            async for url, exception in multi_monitor.monitor_all_with_exceptions():
                if not self.running:
                    break

                # Handle each exception as it occurs
                await self.handle_exception(url, exception)

        except asyncio.CancelledError:
            logger.info("Monitoring cancelled")
        finally:
            multi_monitor.stop_all_monitors()
            logger.info("✅ Monitoring stopped")

    async def handle_exception(self, url: str, exception):
        """Handle a single exception - customize this method"""

        # Print exception details
        print(f"\n🚨 EXCEPTION DETECTED")
        print(f"   URL: {url}")
        print(f"   Time: {exception.timestamp}")
        print(f"   Type: {exception.exception_type}")
        print(f"   Message: {exception.exception}")

        if exception.response_status:
            print(f"   HTTP Status: {exception.response_status}")

        # Show recent context
        if exception.context_lines:
            print(f"   Recent activity:")
            for line in exception.context_lines[-3:]:  # Last 3 lines
                print(f"     {line}")

        # Custom logic based on exception type
        if "timeout" in exception.exception.lower():
            print(f"   💡 Suggestion: Consider increasing timeout for {url}")

        elif exception.response_status and exception.response_status >= 500:
            print(f"   💡 Suggestion: Server error - {url} may be experiencing issues")

        elif exception.response_status and exception.response_status >= 400:
            print(f"   💡 Suggestion: Client error - check configuration for {url}")

        # Log to file (optional)
        await self.log_to_file(url, exception)

    async def log_to_file(self, url: str, exception):
        """Log exception to file for later analysis"""
        import json

        log_entry = {
            "timestamp": exception.timestamp.isoformat(),
            "url": url,
            "exception_type": exception.exception_type,
            "exception_message": exception.exception,
            "response_status": exception.response_status,
            "context_lines": exception.context_lines[-5:]
            if exception.context_lines
            else [],
        }

        # Append to log file
        filename = f"monitor_exceptions_{datetime.now().strftime('%Y%m%d')}.jsonl"
        with open(filename, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

    def stop(self):
        """Stop monitoring"""
        self.running = False


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Simple HTTP Stream Monitor")
    parser.add_argument("--url", help="Single URL to monitor")
    parser.add_argument("--urls", nargs="+", help="Multiple URLs to monitor")
    parser.add_argument(
        "--interval",
        type=float,
        default=30.0,
        help="Check interval in seconds (default: 30)",
    )

    args = parser.parse_args()

    # Determine URLs to monitor
    if args.url:
        urls = [args.url]
    elif args.urls:
        urls = args.urls
    else:
        # Default demo URLs that will generate exceptions
        urls = [
            "https://httpbin.org/get",  # Should work fine
            "https://httpbin.org/status/500",  # Will generate server errors
            "https://httpbin.org/delay/15",  # Will generate timeouts
        ]
        print("No URLs specified, using demo endpoints:")
        for i, url in enumerate(urls, 1):
            print(f"  {i}. {url}")
        print()

    # Create and configure monitor
    monitor = SimpleStreamMonitor(urls, args.interval)

    # Setup signal handling for graceful shutdown
    def signal_handler(signum, frame):
        print(f"\n📡 Received signal {signum}, stopping monitor...")
        monitor.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("🌊 Simple HTTP Stream Monitor")
    print("=" * 50)
    print("This monitor will:")
    print("• Check each URL at the specified interval")
    print("• Yield exceptions in real-time as they occur")
    print("• Show detailed exception information")
    print("• Log exceptions to a daily log file")
    print("• Provide suggestions for common issues")
    print()
    print("Press Ctrl+C to stop monitoring")
    print("=" * 50)

    try:
        await monitor.start_monitoring()
    except KeyboardInterrupt:
        print("\n👋 Monitoring stopped by user")
    except Exception as e:
        print(f"\n💥 Error: {e}")
        return 1

    return 0


# Example of how to extend the monitor for custom use cases
class CustomStreamMonitor(SimpleStreamMonitor):
    """Extended monitor with custom exception handling"""

    def __init__(self, urls: List[str], interval: float = 30.0):
        super().__init__(urls, interval)
        self.exception_counts = {}
        self.alert_threshold = 5

    async def handle_exception(self, url: str, exception):
        """Custom exception handling with alerting"""

        # Count exceptions per URL
        if url not in self.exception_counts:
            self.exception_counts[url] = 0
        self.exception_counts[url] += 1

        # Call parent handler for basic processing
        await super().handle_exception(url, exception)

        # Custom alerting logic
        if self.exception_counts[url] >= self.alert_threshold:
            print(
                f"\n🚨 ALERT: {url} has reached {self.exception_counts[url]} exceptions!"
            )
            print(f"   Consider investigating service health for {url}")

            # Reset counter after alert
            self.exception_counts[url] = 0

            # Here you could:
            # - Send email/Slack notifications
            # - Call webhook endpoints
            # - Update monitoring dashboards
            # - Trigger automated remediation


# Simple usage examples
async def example_single_url():
    """Example: Monitor single URL"""
    monitor = SimpleStreamMonitor(["https://httpbin.org/status/500"], interval=5.0)

    print("Monitoring single URL for 30 seconds...")
    try:
        await asyncio.wait_for(monitor.start_monitoring(), timeout=30.0)
    except asyncio.TimeoutError:
        monitor.stop()
        print("Example completed")


async def example_multiple_urls():
    """Example: Monitor multiple URLs"""
    urls = [
        "https://httpbin.org/get",
        "https://httpbin.org/status/404",
        "https://httpbin.org/status/500",
    ]

    monitor = CustomStreamMonitor(urls, interval=8.0)

    print(f"Monitoring {len(urls)} URLs for 45 seconds...")
    try:
        await asyncio.wait_for(monitor.start_monitoring(), timeout=45.0)
    except asyncio.TimeoutError:
        monitor.stop()
        print("Example completed")


if __name__ == "__main__":
    # Check if we have dependencies
    try:
        from http_monitor import MonitorConfig, MultiHTTPMonitor
    except ImportError:
        print(
            "❌ Required modules not found. Make sure http_monitor.py is in the same directory."
        )
        print("   Also ensure 'httpx' is installed: pip install httpx")
        sys.exit(1)

    # Run main or examples
    if len(sys.argv) > 1 and sys.argv[1] == "examples":
        print("Running examples...")
        asyncio.run(example_single_url())
        asyncio.run(example_multiple_urls())
    else:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
