#!/usr/bin/env python3
"""
Streaming Examples for HTTP Monitor with Exception Yielding

This module demonstrates how to use the updated HTTP monitoring system
that yields exceptions in real-time for immediate handling.
"""

import asyncio
import logging
from datetime import datetime
from typing import AsyncGenerator

from http_monitor import MonitorConfig, HTTPMonitor, MultiHTTPMonitor, ExceptionEvent
from exception_handlers import (
    LoggingExceptionHandler,
    FileExceptionHandler,
    AlertExceptionHandler,
    CompositeExceptionHandler,
    ExceptionProcessor,
    ExceptionFilter,
    CallbackExceptionHandler,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def example_1_basic_exception_streaming():
    """Example 1: Basic exception streaming from a single monitor"""
    print("=" * 60)
    print("EXAMPLE 1: Basic Exception Streaming")
    print("=" * 60)

    config = MonitorConfig(
        url="https://httpbin.org/status/500",  # Will generate exceptions
        interval=3.0,
        context_lines=5,
        max_retries=1,
    )

    async with HTTPMonitor(config) as monitor:
        print(f"Starting monitor for {config.url}")
        print("Listening for exceptions (will run for 20 seconds)...")

        exception_count = 0
        try:
            async with asyncio.timeout(20.0):  # Run for 20 seconds
                async for exception in monitor.monitor_with_exceptions():
                    exception_count += 1
                    print(f"\n🚨 Exception #{exception_count}:")
                    print(f"  Time: {exception.timestamp}")
                    print(f"  Type: {exception.exception_type}")
                    print(f"  Message: {exception.exception}")
                    print(f"  Status: {exception.response_status}")

                    # Show some context
                    if exception.context_lines:
                        print("  Recent context:")
                        for line in exception.context_lines[-2:]:
                            print(f"    {line}")

        except asyncio.TimeoutError:
            print(f"\nExample completed. Captured {exception_count} exceptions.")


async def example_2_multiple_monitors_streaming():
    """Example 2: Stream exceptions from multiple monitors"""
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Multiple Monitors Exception Streaming")
    print("=" * 60)

    configs = [
        MonitorConfig(
            url="https://httpbin.org/status/500",
            interval=4.0,
            context_lines=3,
            max_retries=1,
        ),
        MonitorConfig(
            url="https://httpbin.org/status/404",
            interval=5.0,
            context_lines=3,
            max_retries=1,
        ),
        MonitorConfig(
            url="https://httpbin.org/delay/10",  # Will timeout
            interval=6.0,
            timeout=3.0,
            context_lines=3,
            max_retries=1,
        ),
    ]

    multi_monitor = MultiHTTPMonitor(configs)
    exception_count = 0

    print("Starting multiple monitors...")
    print("Listening for exceptions from all monitors (30 seconds)...")

    try:
        async with asyncio.timeout(30.0):
            async for url, exception in multi_monitor.monitor_all_with_exceptions():
                exception_count += 1
                print(f"\n🚨 Exception #{exception_count} from {url}:")
                print(f"  Type: {exception.exception_type}")
                print(f"  Message: {exception.exception[:100]}...")
                print(f"  Time: {exception.timestamp}")

    except asyncio.TimeoutError:
        print(
            f"\nMultiple monitor example completed. Total exceptions: {exception_count}"
        )
    finally:
        multi_monitor.stop_all_monitors()


async def example_3_exception_handlers():
    """Example 3: Using exception handlers to process streamed exceptions"""
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Exception Handlers")
    print("=" * 60)

    config = MonitorConfig(
        url="https://httpbin.org/status/500",
        interval=2.0,
        context_lines=8,
        max_retries=1,
    )

    # Create composite handler with logging and file output
    composite_handler = CompositeExceptionHandler(
        [
            LoggingExceptionHandler(log_level=logging.ERROR, include_context=True),
            FileExceptionHandler("streaming_exceptions.jsonl", format="jsonl"),
            AlertExceptionHandler(alert_threshold=3, time_window=30),
        ]
    )

    async with HTTPMonitor(config) as monitor:
        print("Starting monitor with composite exception handler...")

        # Create processor
        processor = ExceptionProcessor(composite_handler)

        async def exception_generator():
            """Convert single monitor to URL/exception pairs"""
            async for exception in monitor.monitor_with_exceptions():
                yield config.url, exception

        try:
            # Process exceptions for 25 seconds
            await asyncio.wait_for(
                processor.process_exceptions(exception_generator()), timeout=25.0
            )
        except asyncio.TimeoutError:
            print(
                f"Handler example completed. Processed {processor.processed_count} exceptions."
            )


async def example_4_custom_exception_handling():
    """Example 4: Custom exception handling with callbacks"""
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Custom Exception Handling")
    print("=" * 60)

    # Custom callback function
    async def custom_exception_callback(url: str, exception: ExceptionEvent):
        """Custom callback to handle exceptions"""
        print(f"🔧 CUSTOM HANDLER: {exception.exception_type} from {url}")

        # Custom logic based on exception type
        if "timeout" in exception.exception.lower():
            print(f"   ⏰ Timeout detected - consider increasing timeout for {url}")
        elif exception.response_status and exception.response_status >= 500:
            print(f"   🔴 Server error detected - {url} may be down")
        elif exception.response_status and exception.response_status >= 400:
            print(f"   ⚠️  Client error detected - check {url} configuration")

        # Log context if available
        if exception.context_lines:
            print(f"   📝 Last context: {exception.context_lines[-1]}")

    configs = [
        MonitorConfig(
            url="https://httpbin.org/status/500",
            interval=3.0,
            max_retries=1,
        ),
        MonitorConfig(
            url="https://httpbin.org/delay/8",
            interval=4.0,
            timeout=2.0,
            max_retries=1,
        ),
    ]

    # Create handler with custom callback
    callback_handler = CallbackExceptionHandler(custom_exception_callback)
    multi_monitor = MultiHTTPMonitor(configs)

    processor = ExceptionProcessor(callback_handler)

    print("Starting monitors with custom exception handling...")

    try:
        await asyncio.wait_for(
            processor.process_exceptions(multi_monitor.monitor_all_with_exceptions()),
            timeout=30.0,
        )
    except asyncio.TimeoutError:
        print(
            f"Custom handling example completed. Processed {processor.processed_count} exceptions."
        )
    finally:
        multi_monitor.stop_all_monitors()


async def example_5_exception_filtering():
    """Example 5: Filtering exceptions before handling"""
    print("\n" + "=" * 60)
    print("EXAMPLE 5: Exception Filtering")
    print("=" * 60)

    configs = [
        MonitorConfig(
            url="https://httpbin.org/status/404",
            interval=3.0,
            max_retries=1,
        ),
        MonitorConfig(
            url="https://httpbin.org/status/500",
            interval=4.0,
            max_retries=1,
        ),
        MonitorConfig(
            url="https://httpbin.org/delay/10",
            interval=5.0,
            timeout=2.0,
            max_retries=1,
        ),
    ]

    multi_monitor = MultiHTTPMonitor(configs)

    # Create filter that only processes server errors (5xx) and timeouts
    exception_filter = ExceptionFilter(
        exception_types=["HTTPStatusError", "ConnectTimeout", "ReadTimeout"],
        min_severity="medium",  # Only 500+ status codes
    )

    # Handler that only gets filtered exceptions
    filtered_handler = LoggingExceptionHandler(
        log_level=logging.WARNING, include_context=True
    )

    print("Starting monitors with exception filtering...")
    print("Filter: Only server errors (5xx) and timeouts will be processed")

    processed_count = 0
    filtered_count = 0

    try:
        async with asyncio.timeout(35.0):
            raw_stream = multi_monitor.monitor_all_with_exceptions()
            filtered_stream = exception_filter.filter_stream(raw_stream)

            async with filtered_handler:
                async for url, exception in filtered_stream:
                    await filtered_handler.handle(url, exception)
                    processed_count += 1
                    print(
                        f"   ✅ Processed exception #{processed_count}: {exception.exception_type}"
                    )

    except asyncio.TimeoutError:
        print(f"Filtering example completed.")
        print(f"Processed exceptions: {processed_count}")
    finally:
        multi_monitor.stop_all_monitors()


async def example_6_real_time_monitoring_dashboard():
    """Example 6: Real-time monitoring dashboard simulation"""
    print("\n" + "=" * 60)
    print("EXAMPLE 6: Real-time Monitoring Dashboard")
    print("=" * 60)

    configs = [
        MonitorConfig(
            url="https://httpbin.org/get",
            interval=5.0,
            context_lines=3,
        ),
        MonitorConfig(
            url="https://httpbin.org/status/500",
            interval=4.0,
            max_retries=1,
            context_lines=3,
        ),
        MonitorConfig(
            url="https://httpbin.org/delay/8",
            interval=6.0,
            timeout=3.0,
            max_retries=1,
            context_lines=3,
        ),
    ]

    # Dashboard state
    dashboard_state = {
        "total_exceptions": 0,
        "exceptions_by_url": {},
        "last_exception_time": None,
        "exception_types": {},
    }

    async def update_dashboard(url: str, exception: ExceptionEvent):
        """Update dashboard state with new exception"""
        dashboard_state["total_exceptions"] += 1
        dashboard_state["last_exception_time"] = exception.timestamp

        # Update per-URL counters
        if url not in dashboard_state["exceptions_by_url"]:
            dashboard_state["exceptions_by_url"][url] = 0
        dashboard_state["exceptions_by_url"][url] += 1

        # Update exception type counters
        exc_type = exception.exception_type
        if exc_type not in dashboard_state["exception_types"]:
            dashboard_state["exception_types"][exc_type] = 0
        dashboard_state["exception_types"][exc_type] += 1

        # Print dashboard update
        print(f"\n📊 DASHBOARD UPDATE ({exception.timestamp.strftime('%H:%M:%S')})")
        print(f"   Total Exceptions: {dashboard_state['total_exceptions']}")
        print(f"   From {url}: {dashboard_state['exceptions_by_url'][url]}")
        print(f"   Exception Type: {exc_type}")
        print(f"   Current Exception Types: {dict(dashboard_state['exception_types'])}")

    # Create dashboard handler
    dashboard_handler = CallbackExceptionHandler(update_dashboard)
    multi_monitor = MultiHTTPMonitor(configs)
    processor = ExceptionProcessor(dashboard_handler)

    print("Starting real-time monitoring dashboard...")
    print("Dashboard will update as exceptions occur...")

    try:
        await asyncio.wait_for(
            processor.process_exceptions(multi_monitor.monitor_all_with_exceptions()),
            timeout=40.0,
        )
    except asyncio.TimeoutError:
        print(f"\n📊 FINAL DASHBOARD STATE:")
        print(f"   Total Exceptions: {dashboard_state['total_exceptions']}")
        print(f"   Exceptions by URL:")
        for url, count in dashboard_state["exceptions_by_url"].items():
            print(f"     {url}: {count}")
        print(f"   Exception Types:")
        for exc_type, count in dashboard_state["exception_types"].items():
            print(f"     {exc_type}: {count}")
    finally:
        multi_monitor.stop_all_monitors()


async def example_7_production_pattern():
    """Example 7: Production-ready exception streaming pattern"""
    print("\n" + "=" * 60)
    print("EXAMPLE 7: Production Pattern")
    print("=" * 60)

    # Production configuration
    configs = [
        MonitorConfig(
            url="https://httpbin.org/status/500",
            interval=5.0,
            max_retries=2,
            context_lines=10,
            headers={"User-Agent": "ProductionMonitor/1.0"},
        ),
        MonitorConfig(
            url="https://httpbin.org/delay/10",
            interval=8.0,
            timeout=4.0,
            max_retries=2,
            context_lines=10,
        ),
    ]

    # Production handler setup
    production_handler = CompositeExceptionHandler(
        [
            # Log all exceptions
            LoggingExceptionHandler(log_level=logging.ERROR, include_context=True),
            # Save to structured file for analysis
            FileExceptionHandler("production_exceptions.jsonl", format="jsonl"),
            # Alert on patterns (3 exceptions in 2 minutes)
            AlertExceptionHandler(alert_threshold=3, time_window=120),
            # Custom production callback
            CallbackExceptionHandler(
                lambda url, exc: print(
                    f"🏭 PRODUCTION ALERT: {exc.exception_type} on {url} at {exc.timestamp}"
                )
            ),
        ]
    )

    multi_monitor = MultiHTTPMonitor(configs)
    processor = ExceptionProcessor(production_handler)

    print("Starting production monitoring pattern...")
    print("- All exceptions logged to console and file")
    print("- Alerts triggered on exception patterns")
    print("- Structured data saved for analysis")

    start_time = datetime.now()

    try:
        await asyncio.wait_for(
            processor.process_exceptions(multi_monitor.monitor_all_with_exceptions()),
            timeout=45.0,
        )
    except asyncio.TimeoutError:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        print(f"\n🏭 PRODUCTION MONITORING SUMMARY:")
        print(f"   Duration: {duration:.1f} seconds")
        print(f"   Exceptions Processed: {processor.processed_count}")
        print(
            f"   Rate: {processor.processed_count / duration * 60:.1f} exceptions/minute"
        )
        print(f"   Data saved to: production_exceptions.jsonl")
    finally:
        multi_monitor.stop_all_monitors()


async def run_all_streaming_examples():
    """Run all streaming examples"""
    print("🌊 Starting HTTP Monitor Streaming Examples")
    print("These examples demonstrate real-time exception handling")
    print("Total estimated time: ~4-5 minutes")

    examples = [
        example_1_basic_exception_streaming,
        example_2_multiple_monitors_streaming,
        example_3_exception_handlers,
        example_4_custom_exception_handling,
        example_5_exception_filtering,
        example_6_real_time_monitoring_dashboard,
        example_7_production_pattern,
    ]

    for i, example_func in enumerate(examples, 1):
        try:
            print(f"\n⏳ Running Streaming Example {i}/7...")
            await example_func()
            await asyncio.sleep(2)  # Brief pause between examples
        except Exception as e:
            print(f"❌ Streaming Example {i} failed: {e}")

    print("\n🎉 All streaming examples completed!")
    print("\nKEY TAKEAWAYS:")
    print("✅ Exceptions are yielded in real-time as they occur")
    print("✅ Multiple handlers can process the same exception stream")
    print("✅ Filtering allows selective exception processing")
    print("✅ Custom callbacks enable application-specific logic")
    print("✅ Composite handlers support complex production patterns")
    print("✅ Exception data is preserved with full context")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        example_num = sys.argv[1]

        examples_map = {
            "1": example_1_basic_exception_streaming,
            "2": example_2_multiple_monitors_streaming,
            "3": example_3_exception_handlers,
            "4": example_4_custom_exception_handling,
            "5": example_5_exception_filtering,
            "6": example_6_real_time_monitoring_dashboard,
            "7": example_7_production_pattern,
            "all": run_all_streaming_examples,
        }

        if example_num in examples_map:
            print(f"Running streaming example {example_num}...")
            asyncio.run(examples_map[example_num]())
        else:
            print("Usage: python streaming_examples.py [1|2|3|4|5|6|7|all]")
            print("Streaming Examples:")
            print("  1 - Basic exception streaming")
            print("  2 - Multiple monitors streaming")
            print("  3 - Exception handlers")
            print("  4 - Custom exception handling")
            print("  5 - Exception filtering")
            print("  6 - Real-time dashboard")
            print("  7 - Production pattern")
            print("  all - Run all examples")
    else:
        # Run all examples by default
        asyncio.run(run_all_streaming_examples())
