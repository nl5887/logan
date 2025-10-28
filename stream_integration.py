#!/usr/bin/env python3
"""
Stream Integration Guide for HTTP Monitor with Exception Yielding

This module demonstrates how to integrate the HTTP monitoring system
with real-world streaming scenarios, showing practical patterns for
monitoring multiple endpoints and handling exceptions as they occur.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, AsyncGenerator
from dataclasses import asdict

from http_monitor import MonitorConfig, HTTPMonitor, MultiHTTPMonitor, ExceptionEvent
from exception_handlers import (
    ExceptionHandler,
    LoggingExceptionHandler,
    FileExceptionHandler,
    CompositeExceptionHandler,
    ExceptionProcessor,
    CallbackExceptionHandler,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class StreamMonitorManager:
    """Manager for streaming HTTP monitors with real-time exception handling"""

    def __init__(self):
        self.monitors: List[HTTPMonitor] = []
        self.exception_handlers: List[ExceptionHandler] = []
        self.running = False
        self.exception_count = 0

    def add_endpoints(self, endpoints: List[Dict[str, Any]]):
        """Add endpoints to monitor from configuration"""
        for endpoint_config in endpoints:
            config = MonitorConfig(
                url=endpoint_config["url"],
                interval=endpoint_config.get("interval", 30.0),
                timeout=endpoint_config.get("timeout", 10.0),
                max_retries=endpoint_config.get("max_retries", 3),
                context_lines=endpoint_config.get("context_lines", 10),
                method=endpoint_config.get("method", "GET"),
                headers=endpoint_config.get("headers", {}),
                payload=endpoint_config.get("payload"),
            )
            monitor = HTTPMonitor(config)
            self.monitors.append(monitor)

    def add_exception_handler(self, handler: ExceptionHandler):
        """Add an exception handler"""
        self.exception_handlers.add(handler)

    async def start_streaming(self) -> AsyncGenerator[tuple[str, ExceptionEvent], None]:
        """Start monitoring all endpoints and yield exceptions in real-time"""
        if not self.monitors:
            raise ValueError("No monitors configured. Add endpoints first.")

        self.running = True
        logger.info(f"Starting {len(self.monitors)} monitors for streaming")

        # Create a queue to collect exceptions from all monitors
        exception_queue = asyncio.Queue()
        monitor_tasks = []

        async def monitor_endpoint(monitor: HTTPMonitor):
            """Monitor single endpoint and queue exceptions"""
            async with monitor:
                async for exception in monitor.monitor_with_exceptions():
                    if not self.running:
                        break
                    await exception_queue.put((monitor.config.url, exception))

        # Start all monitors
        for monitor in self.monitors:
            task = asyncio.create_task(monitor_endpoint(monitor))
            monitor_tasks.append(task)

        try:
            while self.running:
                try:
                    # Wait for exceptions with timeout
                    url, exception = await asyncio.wait_for(
                        exception_queue.get(), timeout=1.0
                    )
                    self.exception_count += 1
                    yield url, exception

                except asyncio.TimeoutError:
                    # Check if all tasks are done
                    if all(task.done() for task in monitor_tasks):
                        break
                    continue

        except asyncio.CancelledError:
            logger.info("Stream monitoring cancelled")
        finally:
            # Stop all monitors
            self.running = False
            for monitor in self.monitors:
                monitor.stop_monitoring()

            # Cancel tasks
            for task in monitor_tasks:
                if not task.done():
                    task.cancel()

    def stop_streaming(self):
        """Stop all streaming monitors"""
        self.running = False


class RealTimeExceptionProcessor:
    """Process exceptions in real-time with various handling strategies"""

    def __init__(self):
        self.handlers: List[ExceptionHandler] = []
        self.filters = []
        self.stats = {
            "total_exceptions": 0,
            "exceptions_by_url": {},
            "exceptions_by_type": {},
            "start_time": None,
            "last_exception_time": None,
        }

    def add_handler(self, handler: ExceptionHandler):
        """Add exception handler"""
        self.handlers.append(handler)

    def add_filter(self, filter_func):
        """Add exception filter function"""
        self.filters.append(filter_func)

    async def process_stream(
        self, exception_stream: AsyncGenerator[tuple[str, ExceptionEvent], None]
    ):
        """Process the exception stream with all configured handlers"""
        self.stats["start_time"] = datetime.now()

        # Initialize all handlers
        for handler in self.handlers:
            await handler.__aenter__()

        try:
            async for url, exception in exception_stream:
                # Update stats
                self.stats["total_exceptions"] += 1
                self.stats["last_exception_time"] = exception.timestamp

                if url not in self.stats["exceptions_by_url"]:
                    self.stats["exceptions_by_url"][url] = 0
                self.stats["exceptions_by_url"][url] += 1

                if exception.exception_type not in self.stats["exceptions_by_type"]:
                    self.stats["exceptions_by_type"][exception.exception_type] = 0
                self.stats["exceptions_by_type"][exception.exception_type] += 1

                # Apply filters
                should_process = True
                for filter_func in self.filters:
                    if not filter_func(url, exception):
                        should_process = False
                        break

                if not should_process:
                    continue

                # Process with all handlers
                for handler in self.handlers:
                    try:
                        await handler.handle(url, exception)
                    except Exception as e:
                        logger.error(f"Handler {type(handler).__name__} failed: {e}")

        finally:
            # Clean up handlers
            for handler in self.handlers:
                await handler.__aexit__(None, None, None)

    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics"""
        stats = self.stats.copy()
        if stats["start_time"]:
            stats["duration"] = (datetime.now() - stats["start_time"]).total_seconds()
            if stats["duration"] > 0:
                stats["exceptions_per_minute"] = (
                    stats["total_exceptions"] / stats["duration"]
                ) * 60
        return stats


# Practical Integration Examples


async def monitor_api_endpoints():
    """Example: Monitor API endpoints and handle exceptions"""

    # Define endpoints to monitor
    endpoints = [
        {
            "url": "https://httpbin.org/get",
            "interval": 10.0,
            "headers": {"User-Agent": "APIMonitor/1.0"},
        },
        {
            "url": "https://httpbin.org/status/500",  # Will generate errors
            "interval": 15.0,
            "max_retries": 2,
        },
        {
            "url": "https://httpbin.org/delay/8",  # Will timeout
            "interval": 20.0,
            "timeout": 5.0,
            "max_retries": 1,
        },
    ]

    # Create manager and add endpoints
    manager = StreamMonitorManager()
    manager.add_endpoints(endpoints)

    # Create exception processor with multiple handlers
    processor = RealTimeExceptionProcessor()

    # Add logging handler
    processor.add_handler(
        LoggingExceptionHandler(log_level=logging.WARNING, include_context=True)
    )

    # Add file handler for persistence
    processor.add_handler(FileExceptionHandler("api_exceptions.jsonl", format="jsonl"))

    # Add custom handler for alerts
    async def alert_handler(url: str, exception: ExceptionEvent):
        if "500" in str(exception.response_status):
            print(f"🚨 CRITICAL: Server error on {url}")
        elif "timeout" in exception.exception.lower():
            print(f"⏰ WARNING: Timeout on {url}")

    processor.add_handler(CallbackExceptionHandler(alert_handler))

    # Add filter to only process serious errors
    processor.add_filter(
        lambda url, exc: exc.response_status is None
        or exc.response_status >= 500
        or "timeout" in exc.exception.lower()
    )

    print("🚀 Starting API endpoint monitoring...")
    print("Press Ctrl+C to stop")

    try:
        # Start streaming and processing
        exception_stream = manager.start_streaming()
        await processor.process_stream(exception_stream)

    except KeyboardInterrupt:
        manager.stop_streaming()

    # Show statistics
    stats = processor.get_stats()
    print(f"\n📊 Monitoring Statistics:")
    print(f"   Total exceptions: {stats['total_exceptions']}")
    print(f"   Duration: {stats.get('duration', 0):.1f} seconds")
    print(f"   Exceptions by URL: {stats['exceptions_by_url']}")
    print(f"   Exception types: {stats['exceptions_by_type']}")


async def monitor_with_custom_logic():
    """Example: Monitor with custom business logic"""

    endpoints = [
        {
            "url": "https://httpbin.org/status/404",
            "interval": 8.0,
        },
        {
            "url": "https://httpbin.org/status/500",
            "interval": 12.0,
        },
    ]

    manager = StreamMonitorManager()
    manager.add_endpoints(endpoints)

    # Custom exception handling with business logic
    service_health = {}
    alert_threshold = 3

    async def business_logic_handler(url: str, exception: ExceptionEvent):
        """Custom business logic for handling exceptions"""

        # Track service health
        if url not in service_health:
            service_health[url] = {"error_count": 0, "last_errors": []}

        service_health[url]["error_count"] += 1
        service_health[url]["last_errors"].append(
            {
                "timestamp": exception.timestamp.isoformat(),
                "type": exception.exception_type,
                "message": exception.exception,
            }
        )

        # Keep only last 10 errors
        service_health[url]["last_errors"] = service_health[url]["last_errors"][-10:]

        # Business logic decisions
        error_count = service_health[url]["error_count"]

        if error_count >= alert_threshold:
            print(f"🔴 SERVICE DEGRADED: {url} has {error_count} errors")

            # Simulate taking action (e.g., switching to backup, alerting team)
            if error_count >= alert_threshold * 2:
                print(f"🚨 CRITICAL: Taking automated action for {url}")
                # Here you would integrate with your incident management system

        elif error_count >= alert_threshold // 2:
            print(f"🟡 SERVICE WARNING: {url} showing errors ({error_count})")

    processor = RealTimeExceptionProcessor()
    processor.add_handler(CallbackExceptionHandler(business_logic_handler))
    processor.add_handler(
        FileExceptionHandler("business_exceptions.json", format="json")
    )

    print("🏢 Starting monitoring with business logic...")

    try:
        exception_stream = manager.start_streaming()
        await asyncio.wait_for(processor.process_stream(exception_stream), timeout=60.0)
    except asyncio.TimeoutError:
        print("⏰ Monitoring session completed")
    finally:
        manager.stop_streaming()

    # Show final service health
    print(f"\n🏥 Final Service Health Report:")
    for url, health in service_health.items():
        print(f"   {url}: {health['error_count']} errors")


async def monitor_configuration_from_file():
    """Example: Load monitoring configuration from file"""

    # Example configuration that could be loaded from JSON/YAML
    config = {
        "monitoring": {
            "endpoints": [
                {
                    "name": "Main API",
                    "url": "https://httpbin.org/get",
                    "interval": 30.0,
                    "timeout": 10.0,
                    "headers": {"Authorization": "Bearer token123"},
                },
                {
                    "name": "Status Check",
                    "url": "https://httpbin.org/status/500",
                    "interval": 60.0,
                    "max_retries": 2,
                },
            ],
            "handlers": {
                "log_level": "ERROR",
                "file_output": "monitoring_exceptions.jsonl",
                "alert_threshold": 5,
                "alert_window_minutes": 10,
            },
        }
    }

    # Convert config to monitor setup
    manager = StreamMonitorManager()

    for endpoint_config in config["monitoring"]["endpoints"]:
        endpoint_config["url"] = endpoint_config["url"]  # Keep URL as-is
        manager.add_endpoints([endpoint_config])

    # Setup handlers from config
    processor = RealTimeExceptionProcessor()

    handler_config = config["monitoring"]["handlers"]

    # Add configured handlers
    processor.add_handler(
        LoggingExceptionHandler(log_level=getattr(logging, handler_config["log_level"]))
    )

    processor.add_handler(
        FileExceptionHandler(handler_config["file_output"], format="jsonl")
    )

    # Alert logic from config
    alert_counts = {}

    async def configured_alert_handler(url: str, exception: ExceptionEvent):
        if url not in alert_counts:
            alert_counts[url] = 0
        alert_counts[url] += 1

        if alert_counts[url] >= handler_config["alert_threshold"]:
            print(
                f"🔔 CONFIGURED ALERT: {url} exceeded threshold ({alert_counts[url]} exceptions)"
            )
            alert_counts[url] = 0  # Reset counter

    processor.add_handler(CallbackExceptionHandler(configured_alert_handler))

    print("📋 Starting monitoring from configuration...")

    try:
        exception_stream = manager.start_streaming()
        await asyncio.wait_for(processor.process_stream(exception_stream), timeout=45.0)
    except asyncio.TimeoutError:
        print("⏰ Configuration-based monitoring completed")
    finally:
        manager.stop_streaming()


# Main execution examples
async def main():
    """Run integration examples"""
    examples = [
        ("API Endpoints Monitoring", monitor_api_endpoints),
        ("Custom Business Logic", monitor_with_custom_logic),
        ("Configuration File Based", monitor_configuration_from_file),
    ]

    print("🔗 HTTP Monitor Stream Integration Examples")
    print("=" * 60)

    for i, (name, example_func) in enumerate(examples, 1):
        print(f"\n🎯 Example {i}: {name}")
        print("-" * 40)

        try:
            await example_func()
        except KeyboardInterrupt:
            print(f"\n⏹️  Example {i} stopped by user")
        except Exception as e:
            print(f"\n❌ Example {i} failed: {e}")

        print(f"✅ Example {i} completed")

        if i < len(examples):
            print("\nPress Enter to continue to next example...")
            # In real usage, you might want to pause here
            await asyncio.sleep(1)

    print(f"\n🎊 All integration examples completed!")


if __name__ == "__main__":
    print("🌊 Stream Integration for HTTP Monitor")
    print("This demonstrates practical patterns for monitoring HTTP endpoints")
    print("and handling exceptions in real-time streaming scenarios.")
    print()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Integration examples stopped by user")
    except Exception as e:
        print(f"\n💥 Integration failed: {e}")
