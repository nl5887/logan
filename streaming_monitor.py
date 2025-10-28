#!/usr/bin/env python3
"""
Simple Streaming HTTP Monitor Runner

This script demonstrates the exception yielding pattern for HTTP monitoring.
Run this to see real-time exception handling in action.
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime
from typing import Optional

from http_monitor import MonitorConfig, HTTPMonitor, MultiHTTPMonitor
from exception_handlers import (
    LoggingExceptionHandler,
    FileExceptionHandler,
    CompositeExceptionHandler,
    ExceptionProcessor,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class StreamingMonitorRunner:
    """Simple runner for streaming HTTP monitor"""

    def __init__(self):
        self.running = False
        self.processor: Optional[ExceptionProcessor] = None

    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""

        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            self.running = False
            if self.processor:
                self.processor.stop()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def run_single_monitor(self, url: str, interval: float = 10.0):
        """Run a single monitor with exception streaming"""
        config = MonitorConfig(
            url=url,
            interval=interval,
            timeout=5.0,
            max_retries=2,
            context_lines=8,
            headers={"User-Agent": "StreamingMonitor/1.0"},
        )

        # Create handler that logs exceptions
        handler = CompositeExceptionHandler(
            [
                LoggingExceptionHandler(log_level=logging.ERROR, include_context=True),
                FileExceptionHandler(
                    f"exceptions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl",
                    format="jsonl",
                ),
            ]
        )

        self.processor = ExceptionProcessor(handler)
        self.running = True

        async with HTTPMonitor(config) as monitor:
            logger.info(f"🚀 Starting streaming monitor for {url}")
            logger.info(f"📊 Interval: {interval}s, Press Ctrl+C to stop")

            async def exception_generator():
                """Convert single monitor to URL/exception pairs"""
                async for exception in monitor.monitor_with_exceptions():
                    if not self.running:
                        break
                    yield url, exception

            try:
                await self.processor.process_exceptions(exception_generator())
            except asyncio.CancelledError:
                logger.info("Monitor cancelled")
            except Exception as e:
                logger.error(f"Error in monitor: {e}")

        logger.info(
            f"✅ Monitor stopped. Processed {self.processor.processed_count} exceptions"
        )

    async def run_multiple_monitors(self, urls: list[str], interval: float = 15.0):
        """Run multiple monitors with exception streaming"""
        configs = []
        for url in urls:
            config = MonitorConfig(
                url=url,
                interval=interval,
                timeout=8.0,
                max_retries=2,
                context_lines=10,
                headers={"User-Agent": "StreamingMultiMonitor/1.0"},
            )
            configs.append(config)

        # Create comprehensive handler
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        handler = CompositeExceptionHandler(
            [
                LoggingExceptionHandler(
                    log_level=logging.WARNING, include_context=True
                ),
                FileExceptionHandler(
                    f"multi_exceptions_{timestamp}.jsonl", format="jsonl"
                ),
            ]
        )

        self.processor = ExceptionProcessor(handler)
        multi_monitor = MultiHTTPMonitor(configs)
        self.running = True

        logger.info(f"🚀 Starting streaming monitors for {len(urls)} URLs")
        logger.info(f"📊 Interval: {interval}s, Press Ctrl+C to stop")

        for i, url in enumerate(urls, 1):
            logger.info(f"  {i}. {url}")

        try:
            await self.processor.process_exceptions(
                multi_monitor.monitor_all_with_exceptions()
            )
        except asyncio.CancelledError:
            logger.info("Monitors cancelled")
        except Exception as e:
            logger.error(f"Error in monitors: {e}")
        finally:
            multi_monitor.stop_all_monitors()

        logger.info(
            f"✅ All monitors stopped. Processed {self.processor.processed_count} exceptions"
        )

    async def run_demo(self):
        """Run a demo with error-generating endpoints"""
        demo_configs = [
            MonitorConfig(
                url="https://httpbin.org/status/500",  # Server errors
                interval=8.0,
                max_retries=1,
                context_lines=5,
                headers={"Demo": "ServerError"},
            ),
            MonitorConfig(
                url="https://httpbin.org/status/404",  # Not found
                interval=10.0,
                max_retries=1,
                context_lines=5,
                headers={"Demo": "NotFound"},
            ),
            MonitorConfig(
                url="https://httpbin.org/delay/10",  # Timeouts
                interval=12.0,
                timeout=3.0,
                max_retries=1,
                context_lines=5,
                headers={"Demo": "Timeout"},
            ),
            MonitorConfig(
                url="https://httpbin.org/get",  # Success (no exceptions)
                interval=15.0,
                context_lines=3,
                headers={"Demo": "Success"},
            ),
        ]

        # Demo handler with custom callback
        async def demo_callback(url: str, exception):
            """Custom demo callback"""
            print(f"\n🎯 DEMO EXCEPTION CAUGHT!")
            print(f"   URL: {url}")
            print(f"   Type: {exception.exception_type}")
            print(f"   Message: {exception.exception}")

            if "500" in str(exception.response_status):
                print(f"   💡 This is a server error - the endpoint returns HTTP 500")
            elif "404" in str(exception.response_status):
                print(f"   💡 This is a not found error - HTTP 404")
            elif "timeout" in exception.exception.lower():
                print(
                    f"   💡 This is a timeout - the endpoint takes too long to respond"
                )

        from exception_handlers import CallbackExceptionHandler

        handler = CompositeExceptionHandler(
            [
                LoggingExceptionHandler(log_level=logging.INFO, include_context=False),
                CallbackExceptionHandler(demo_callback),
                FileExceptionHandler(
                    f"demo_exceptions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    format="json",
                ),
            ]
        )

        self.processor = ExceptionProcessor(handler)
        multi_monitor = MultiHTTPMonitor(demo_configs)
        self.running = True

        print("\n" + "=" * 60)
        print("🎬 HTTP MONITOR DEMO")
        print("=" * 60)
        print(
            "This demo monitors several endpoints that will generate different types of exceptions:"
        )
        print("• https://httpbin.org/status/500 - Returns server errors (HTTP 500)")
        print("• https://httpbin.org/status/404 - Returns not found errors (HTTP 404)")
        print(
            "• https://httpbin.org/delay/10 - Causes timeout errors (takes 10s, timeout is 3s)"
        )
        print(
            "• https://httpbin.org/get - Success endpoint (should not generate exceptions)"
        )
        print("\nWatch for real-time exception handling below...")
        print("Press Ctrl+C to stop the demo")
        print("=" * 60)

        try:
            await self.processor.process_exceptions(
                multi_monitor.monitor_all_with_exceptions()
            )
        except asyncio.CancelledError:
            pass
        finally:
            multi_monitor.stop_all_monitors()

        print(
            f"\n🎬 Demo completed! Processed {self.processor.processed_count} exceptions"
        )


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Streaming HTTP Monitor")
    parser.add_argument("--url", "-u", help="Single URL to monitor")
    parser.add_argument("--urls", "-m", nargs="+", help="Multiple URLs to monitor")
    parser.add_argument(
        "--interval",
        "-i",
        type=float,
        default=10.0,
        help="Interval between requests (default: 10.0)",
    )
    parser.add_argument(
        "--demo",
        "-d",
        action="store_true",
        help="Run demo with error-generating endpoints",
    )

    args = parser.parse_args()

    runner = StreamingMonitorRunner()
    runner.setup_signal_handlers()

    try:
        if args.demo:
            await runner.run_demo()
        elif args.url:
            await runner.run_single_monitor(args.url, args.interval)
        elif args.urls:
            await runner.run_multiple_monitors(args.urls, args.interval)
        else:
            # Default demo
            print("No URLs specified, running demo...")
            await runner.run_demo()

    except KeyboardInterrupt:
        logger.info("Stopped by user")
    except Exception as e:
        logger.error(f"Error: {e}")


if __name__ == "__main__":
    print("🌊 Streaming HTTP Monitor")
    print("Monitor HTTP endpoints and handle exceptions in real-time")
    print()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 Fatal error: {e}")
        sys.exit(1)
