#!/usr/bin/env python3
"""
Simple test for HTTP Monitor exception yielding functionality
"""

import asyncio
import logging
from http_monitor import MonitorConfig, HTTPMonitor, MultiHTTPMonitor

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_single_monitor_yielding():
    """Test single monitor yielding exceptions"""
    print("=" * 50)
    print("Testing Single Monitor Exception Yielding")
    print("=" * 50)

    config = MonitorConfig(
        url="https://httpbin.org/status/500",
        interval=2.0,
        max_retries=1,
        context_lines=3,
    )

    exception_count = 0

    async with HTTPMonitor(config) as monitor:
        print(f"Starting monitor for {config.url}")
        print("Waiting for exceptions (10 seconds)...")

        try:
            async with asyncio.timeout(10.0):
                async for exception in monitor.monitor_with_exceptions():
                    exception_count += 1
                    print(
                        f"✅ Exception #{exception_count}: {exception.exception_type}"
                    )

                    if exception_count >= 3:  # Stop after 3 exceptions
                        break

        except asyncio.TimeoutError:
            pass

    print(f"Single monitor test completed. Caught {exception_count} exceptions.")
    return exception_count > 0


async def test_multi_monitor_yielding():
    """Test multiple monitors yielding exceptions"""
    print("\n" + "=" * 50)
    print("Testing Multi Monitor Exception Yielding")
    print("=" * 50)

    configs = [
        MonitorConfig(
            url="https://httpbin.org/status/500",
            interval=3.0,
            max_retries=1,
            context_lines=2,
        ),
        MonitorConfig(
            url="https://httpbin.org/status/404",
            interval=4.0,
            max_retries=1,
            context_lines=2,
        ),
    ]

    multi_monitor = MultiHTTPMonitor(configs)
    exception_count = 0

    print("Starting multiple monitors...")
    print("Waiting for exceptions (15 seconds)...")

    try:
        async with asyncio.timeout(15.0):
            async for url, exception in multi_monitor.monitor_all_with_exceptions():
                exception_count += 1
                print(
                    f"✅ Exception #{exception_count} from {url}: {exception.exception_type}"
                )

                if exception_count >= 4:  # Stop after 4 exceptions
                    break

    except asyncio.TimeoutError:
        pass
    finally:
        multi_monitor.stop_all_monitors()

    print(f"Multi monitor test completed. Caught {exception_count} exceptions.")
    return exception_count > 0


async def test_exception_handling():
    """Test exception handling with custom logic"""
    print("\n" + "=" * 50)
    print("Testing Exception Handling Logic")
    print("=" * 50)

    config = MonitorConfig(
        url="https://httpbin.org/status/500",
        interval=2.5,
        max_retries=1,
        context_lines=5,
    )

    handled_exceptions = []

    async def handle_exception(url: str, exception):
        """Custom exception handler"""
        handled_exceptions.append((url, exception))
        print(f"🔧 Handled: {exception.exception_type} from {url}")
        print(f"   Message: {exception.exception}")
        print(f"   Time: {exception.timestamp}")
        if exception.context_lines:
            print(f"   Context lines: {len(exception.context_lines)}")

    async with HTTPMonitor(config) as monitor:
        print(f"Starting monitor with custom handler...")

        try:
            async with asyncio.timeout(12.0):
                async for exception in monitor.monitor_with_exceptions():
                    await handle_exception(config.url, exception)

                    if len(handled_exceptions) >= 3:
                        break

        except asyncio.TimeoutError:
            pass

    print(
        f"Exception handling test completed. Handled {len(handled_exceptions)} exceptions."
    )
    return len(handled_exceptions) > 0


async def main():
    """Run all tests"""
    print("🧪 Testing HTTP Monitor Exception Yielding")
    print("This will test the real-time exception yielding functionality")

    tests = [
        ("Single Monitor Yielding", test_single_monitor_yielding),
        ("Multi Monitor Yielding", test_multi_monitor_yielding),
        ("Exception Handling Logic", test_exception_handling),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n🔬 Running: {test_name}")
        try:
            result = await test_func()
            if result:
                print(f"✅ {test_name}: PASSED")
                passed += 1
            else:
                print(f"❌ {test_name}: FAILED (no exceptions caught)")
        except Exception as e:
            print(f"💥 {test_name}: ERROR - {e}")

    print("\n" + "=" * 50)
    print("TEST RESULTS")
    print("=" * 50)
    print(f"Passed: {passed}/{total}")
    print(f"Failed: {total - passed}/{total}")

    if passed == total:
        print("🎉 All tests passed! Exception yielding is working correctly.")
        return 0
    else:
        print(f"⚠️  {total - passed} tests failed.")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️ Tests interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n💥 Test suite failed: {e}")
        exit(1)
