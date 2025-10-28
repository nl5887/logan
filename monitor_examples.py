#!/usr/bin/env python3
"""
HTTP Monitor Usage Examples

This module provides various examples of how to use the HTTP monitoring system
with different configurations and scenarios.
"""

import asyncio
from datetime import datetime
from http_monitor import MonitorConfig, HTTPMonitor, MultiHTTPMonitor


async def example_1_basic_single_monitor():
    """Example 1: Basic single endpoint monitoring"""
    print("=" * 60)
    print("EXAMPLE 1: Basic Single Monitor")
    print("=" * 60)

    config = MonitorConfig(
        url="https://httpbin.org/get",
        interval=5.0,  # Check every 5 seconds
        context_lines=5,
        headers={"User-Agent": "Example-Monitor/1.0"},
    )

    async with HTTPMonitor(config) as monitor:
        # Run for 30 seconds
        try:
            await asyncio.wait_for(monitor.start_monitoring(), timeout=30.0)
        except asyncio.TimeoutError:
            print("Example completed")

        monitor.stop_monitoring()

        # Check for exceptions
        exceptions = monitor.get_exceptions()
        print(f"Captured {len(exceptions)} exceptions")

        if exceptions:
            for exc in exceptions:
                print(f"- {exc.timestamp}: {exc.exception_type} - {exc.exception}")


async def example_2_multiple_endpoints():
    """Example 2: Monitor multiple endpoints simultaneously"""
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Multiple Endpoints")
    print("=" * 60)

    configs = [
        MonitorConfig(
            url="https://httpbin.org/get",
            interval=10.0,
            context_lines=8,
            headers={"Service": "GET-Monitor"},
        ),
        MonitorConfig(
            url="https://httpbin.org/status/200",
            interval=15.0,
            context_lines=5,
            headers={"Service": "Status-Monitor"},
        ),
        MonitorConfig(
            url="https://httpbin.org/json",
            interval=12.0,
            context_lines=10,
            headers={"Service": "JSON-Monitor"},
        ),
    ]

    multi_monitor = MultiHTTPMonitor(configs)

    try:
        # Run for 60 seconds
        await asyncio.wait_for(multi_monitor.start_all_monitors(), timeout=60.0)
    except asyncio.TimeoutError:
        print("Multiple monitor example completed")
    finally:
        multi_monitor.stop_all_monitors()

        # Export and show results
        filename = multi_monitor.export_all_exceptions()
        print(f"Results exported to: {filename}")

        all_exceptions = multi_monitor.get_all_exceptions()
        for url, exceptions in all_exceptions.items():
            print(f"\n{url}: {len(exceptions)} exceptions")


async def example_3_error_scenarios():
    """Example 3: Monitor endpoints that will generate errors"""
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Error Scenarios")
    print("=" * 60)

    configs = [
        # This will return 500 errors
        MonitorConfig(
            url="https://httpbin.org/status/500",
            interval=8.0,
            max_retries=2,
            context_lines=15,
            headers={"Test": "Server-Error"},
        ),
        # This might timeout (3 second delay with 2 second timeout)
        MonitorConfig(
            url="https://httpbin.org/delay/3",
            interval=10.0,
            timeout=2.0,
            max_retries=1,
            context_lines=12,
            headers={"Test": "Timeout"},
        ),
        # This will return 404 errors
        MonitorConfig(
            url="https://httpbin.org/status/404",
            interval=12.0,
            max_retries=3,
            context_lines=10,
            headers={"Test": "Not-Found"},
        ),
    ]

    multi_monitor = MultiHTTPMonitor(configs)

    try:
        # Run for 45 seconds to see multiple error cycles
        await asyncio.wait_for(multi_monitor.start_all_monitors(), timeout=45.0)
    except asyncio.TimeoutError:
        print("Error scenario testing completed")
    finally:
        multi_monitor.stop_all_monitors()

        # Show detailed exception analysis
        all_exceptions = multi_monitor.get_all_exceptions()

        print(f"\nERROR ANALYSIS:")
        print("-" * 40)

        total_exceptions = 0
        for url, exceptions in all_exceptions.items():
            total_exceptions += len(exceptions)
            if exceptions:
                print(f"\n🔴 {url}")
                print(f"   Total exceptions: {len(exceptions)}")

                # Group by exception type
                exc_types = {}
                for exc in exceptions:
                    exc_type = exc.exception_type
                    if exc_type not in exc_types:
                        exc_types[exc_type] = []
                    exc_types[exc_type].append(exc)

                for exc_type, exc_list in exc_types.items():
                    print(f"   - {exc_type}: {len(exc_list)} occurrences")

                    # Show context from last occurrence
                    last_exc = exc_list[-1]
                    if last_exc.context_lines:
                        print(f"     Last context:")
                        for line in last_exc.context_lines[-3:]:
                            print(f"       {line}")

        print(f"\nTotal exceptions across all monitors: {total_exceptions}")


async def example_4_post_requests():
    """Example 4: Monitor POST endpoints with payloads"""
    print("\n" + "=" * 60)
    print("EXAMPLE 4: POST Requests with Payloads")
    print("=" * 60)

    configs = [
        MonitorConfig(
            url="https://httpbin.org/post",
            method="POST",
            interval=15.0,
            context_lines=12,
            payload={
                "service": "monitor",
                "timestamp": datetime.now().isoformat(),
                "data": {"key1": "value1", "key2": "value2"},
            },
            headers={"Content-Type": "application/json", "Service": "POST-Monitor"},
        ),
        MonitorConfig(
            url="https://httpbin.org/put",
            method="PUT",
            interval=20.0,
            context_lines=8,
            payload={
                "update_type": "monitor_data",
                "timestamp": datetime.now().isoformat(),
            },
            headers={"Content-Type": "application/json", "Service": "PUT-Monitor"},
        ),
    ]

    multi_monitor = MultiHTTPMonitor(configs)

    try:
        await asyncio.wait_for(multi_monitor.start_all_monitors(), timeout=50.0)
    except asyncio.TimeoutError:
        print("POST request monitoring completed")
    finally:
        multi_monitor.stop_all_monitors()

        # Export results
        filename = multi_monitor.export_all_exceptions()
        print(f"POST monitoring results exported to: {filename}")


async def example_5_authentication():
    """Example 5: Monitor endpoints requiring authentication"""
    print("\n" + "=" * 60)
    print("EXAMPLE 5: Authentication Examples")
    print("=" * 60)

    configs = [
        # Basic Auth (this will succeed)
        MonitorConfig(
            url="https://httpbin.org/basic-auth/user/pass",
            interval=10.0,
            context_lines=8,
            headers={
                "Authorization": "Basic dXNlcjpwYXNz",  # base64 of user:pass
                "Service": "Basic-Auth-Monitor",
            },
        ),
        # Basic Auth with wrong credentials (this will fail)
        MonitorConfig(
            url="https://httpbin.org/basic-auth/user/pass",
            interval=12.0,
            context_lines=10,
            max_retries=2,
            headers={
                "Authorization": "Basic d3JvbmdjcmVkcw==",  # wrong credentials
                "Service": "Wrong-Auth-Monitor",
            },
        ),
        # Bearer token example (will fail since httpbin doesn't support this specific endpoint)
        MonitorConfig(
            url="https://httpbin.org/bearer",
            interval=15.0,
            context_lines=8,
            headers={
                "Authorization": "Bearer sample-token-12345",
                "Service": "Bearer-Token-Monitor",
            },
        ),
    ]

    multi_monitor = MultiHTTPMonitor(configs)

    try:
        await asyncio.wait_for(multi_monitor.start_all_monitors(), timeout=40.0)
    except asyncio.TimeoutError:
        print("Authentication monitoring completed")
    finally:
        multi_monitor.stop_all_monitors()

        # Show authentication results
        all_exceptions = multi_monitor.get_all_exceptions()

        print(f"\nAUTHENTICATION RESULTS:")
        print("-" * 40)

        for url, exceptions in all_exceptions.items():
            auth_failures = [
                exc
                for exc in exceptions
                if "401" in str(exc.exception) or "403" in str(exc.exception)
            ]

            if auth_failures:
                print(f"🔐 {url}")
                print(f"   Authentication failures: {len(auth_failures)}")
                if auth_failures:
                    last_failure = auth_failures[-1]
                    print(f"   Last failure: {last_failure.exception}")
            else:
                print(f"✅ {url}: No authentication issues")


async def example_6_custom_monitoring():
    """Example 6: Custom monitoring with specific requirements"""
    print("\n" + "=" * 60)
    print("EXAMPLE 6: Custom Monitoring Setup")
    print("=" * 60)

    # Create a custom monitor for a specific scenario
    config = MonitorConfig(
        url="https://httpbin.org/anything",
        method="POST",
        interval=8.0,
        timeout=15.0,
        max_retries=5,  # More retries
        context_lines=20,  # More context
        payload={
            "monitor_id": "custom-001",
            "check_time": datetime.now().isoformat(),
            "custom_data": {
                "version": "1.0",
                "environment": "testing",
                "parameters": ["param1", "param2", "param3"],
            },
        },
        headers={
            "Content-Type": "application/json",
            "X-Monitor-Type": "Custom",
            "X-Monitor-Version": "1.0",
            "User-Agent": "CustomMonitor/1.0",
        },
    )

    async with HTTPMonitor(config) as monitor:
        print("Starting custom monitoring...")

        try:
            await asyncio.wait_for(monitor.start_monitoring(), timeout=35.0)
        except asyncio.TimeoutError:
            print("Custom monitoring completed")

        monitor.stop_monitoring()

        # Detailed analysis
        exceptions = monitor.get_exceptions()
        print(f"\nCustom monitor captured {len(exceptions)} exceptions")

        if exceptions:
            for i, exc in enumerate(exceptions, 1):
                print(f"\nException {i}:")
                print(f"  Time: {exc.timestamp}")
                print(f"  Type: {exc.exception_type}")
                print(f"  Message: {exc.exception}")

                if exc.response_status:
                    print(f"  Response Status: {exc.response_status}")

                print(f"  Context lines ({len(exc.context_lines)}):")
                for line in exc.context_lines[-5:]:  # Show last 5 context lines
                    print(f"    {line}")

        # Export custom results
        filename = monitor.export_exceptions("custom_monitor_results.json")
        print(f"\nCustom results exported to: {filename}")


async def run_all_examples():
    """Run all examples sequentially"""
    examples = [
        example_1_basic_single_monitor,
        example_2_multiple_endpoints,
        example_3_error_scenarios,
        example_4_post_requests,
        example_5_authentication,
        example_6_custom_monitoring,
    ]

    print("🚀 Starting HTTP Monitor Examples")
    print("This will run multiple monitoring scenarios to demonstrate capabilities")
    print("Total estimated time: ~5-6 minutes")

    for i, example_func in enumerate(examples, 1):
        try:
            print(f"\n⏳ Running Example {i}/6...")
            await example_func()
            await asyncio.sleep(2)  # Brief pause between examples
        except Exception as e:
            print(f"❌ Example {i} failed: {e}")

    print("\n🎉 All examples completed!")
    print("\nSUMMARY:")
    print("- Check the exported JSON files for detailed exception data")
    print("- Review the log file 'http_monitor.log' for detailed monitoring logs")
    print("- The examples demonstrated various monitoring scenarios:")
    print("  1. Single endpoint monitoring")
    print("  2. Multiple endpoint monitoring")
    print("  3. Error scenario handling")
    print("  4. POST request monitoring")
    print("  5. Authentication monitoring")
    print("  6. Custom monitoring setup")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        example_num = sys.argv[1]

        examples_map = {
            "1": example_1_basic_single_monitor,
            "2": example_2_multiple_endpoints,
            "3": example_3_error_scenarios,
            "4": example_4_post_requests,
            "5": example_5_authentication,
            "6": example_6_custom_monitoring,
            "all": run_all_examples,
        }

        if example_num in examples_map:
            print(f"Running example {example_num}...")
            asyncio.run(examples_map[example_num]())
        else:
            print("Usage: python monitor_examples.py [1|2|3|4|5|6|all]")
            print("Examples:")
            print("  1 - Basic single monitor")
            print("  2 - Multiple endpoints")
            print("  3 - Error scenarios")
            print("  4 - POST requests")
            print("  5 - Authentication")
            print("  6 - Custom monitoring")
            print("  all - Run all examples")
    else:
        # Run all examples by default
        asyncio.run(run_all_examples())
