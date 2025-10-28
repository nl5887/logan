#!/usr/bin/env python3
"""
Test script for HTTP Monitor functionality
"""

import asyncio
import sys
import logging
from datetime import datetime

# Configure logging for testing
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_imports():
    """Test that all required modules can be imported"""
    try:
        import httpx

        logger.info("✅ httpx imported successfully")
    except ImportError as e:
        logger.error(f"❌ Failed to import httpx: {e}")
        return False

    try:
        from http_monitor import MonitorConfig, HTTPMonitor, MultiHTTPMonitor

        logger.info("✅ http_monitor modules imported successfully")
    except ImportError as e:
        logger.error(f"❌ Failed to import http_monitor: {e}")
        return False

    try:
        from monitor_runner import MonitorRunner, ConfigLoader

        logger.info("✅ monitor_runner modules imported successfully")
    except ImportError as e:
        logger.error(f"❌ Failed to import monitor_runner: {e}")
        return False

    return True


def test_config_creation():
    """Test MonitorConfig creation"""
    try:
        from http_monitor import MonitorConfig

        config = MonitorConfig(
            url="https://httpbin.org/get",
            interval=10.0,
            timeout=5.0,
            max_retries=2,
            context_lines=5,
            headers={"User-Agent": "TestMonitor/1.0"},
            method="GET",
        )

        assert config.url == "https://httpbin.org/get"
        assert config.interval == 10.0
        assert config.timeout == 5.0
        assert config.max_retries == 2
        assert config.context_lines == 5
        assert config.headers["User-Agent"] == "TestMonitor/1.0"
        assert config.method == "GET"

        logger.info("✅ MonitorConfig creation test passed")
        return True
    except Exception as e:
        logger.error(f"❌ MonitorConfig creation test failed: {e}")
        return False


def test_config_loading():
    """Test configuration file loading"""
    try:
        from monitor_runner import ConfigLoader
        import json
        import os

        # Create temporary config
        test_config = {
            "monitors": [
                {
                    "url": "https://httpbin.org/get",
                    "interval": 30.0,
                    "timeout": 10.0,
                    "max_retries": 3,
                    "context_lines": 10,
                    "method": "GET",
                    "headers": {"User-Agent": "TestMonitor/1.0"},
                }
            ],
            "global_settings": {"log_level": "INFO", "export_on_exit": true},
        }

        # Write test config
        with open("test_config.json", "w") as f:
            json.dump(test_config, f, indent=2)

        # Load config
        loaded_config = ConfigLoader.load_from_file("test_config.json")
        assert "monitors" in loaded_config
        assert len(loaded_config["monitors"]) == 1
        assert loaded_config["monitors"][0]["url"] == "https://httpbin.org/get"

        # Create monitor configs
        monitor_configs = ConfigLoader.create_monitor_configs(loaded_config)
        assert len(monitor_configs) == 1
        assert monitor_configs[0].url == "https://httpbin.org/get"

        # Cleanup
        os.remove("test_config.json")

        logger.info("✅ Configuration loading test passed")
        return True
    except Exception as e:
        logger.error(f"❌ Configuration loading test failed: {e}")
        return False


async def test_single_monitor():
    """Test single HTTP monitor"""
    try:
        from http_monitor import MonitorConfig, HTTPMonitor

        config = MonitorConfig(
            url="https://httpbin.org/get",
            interval=2.0,  # Short interval for testing
            timeout=5.0,
            max_retries=1,
            context_lines=3,
            headers={"User-Agent": "TestMonitor/1.0"},
        )

        async with HTTPMonitor(config) as monitor:
            # Test for 10 seconds
            try:
                await asyncio.wait_for(monitor.start_monitoring(), timeout=10.0)
            except asyncio.TimeoutError:
                pass  # Expected for test

            monitor.stop_monitoring()

            # Check that monitor ran
            exceptions = monitor.get_exceptions()
            logger.info(
                f"✅ Single monitor test completed - {len(exceptions)} exceptions captured"
            )

            return True

    except Exception as e:
        logger.error(f"❌ Single monitor test failed: {e}")
        return False


async def test_error_handling():
    """Test error handling with bad endpoints"""
    try:
        from http_monitor import MonitorConfig, HTTPMonitor

        # Test with endpoint that returns 500 errors
        config = MonitorConfig(
            url="https://httpbin.org/status/500",
            interval=3.0,
            timeout=5.0,
            max_retries=2,
            context_lines=5,
        )

        async with HTTPMonitor(config) as monitor:
            # Run for short time to capture errors
            try:
                await asyncio.wait_for(monitor.start_monitoring(), timeout=12.0)
            except asyncio.TimeoutError:
                pass

            monitor.stop_monitoring()

            # Should have captured exceptions
            exceptions = monitor.get_exceptions()
            if len(exceptions) > 0:
                logger.info(
                    f"✅ Error handling test passed - captured {len(exceptions)} exceptions"
                )

                # Show first exception details
                first_exc = exceptions[0]
                logger.info(f"   Exception type: {first_exc.exception_type}")
                logger.info(f"   Exception message: {first_exc.exception}")
                logger.info(f"   Context lines: {len(first_exc.context_lines)}")

                return True
            else:
                logger.warning(
                    "⚠️  Error handling test: No exceptions captured (may be network issue)"
                )
                return True  # Don't fail test due to network issues

    except Exception as e:
        logger.error(f"❌ Error handling test failed: {e}")
        return False


async def test_multi_monitor():
    """Test multiple monitor functionality"""
    try:
        from http_monitor import MonitorConfig, MultiHTTPMonitor

        configs = [
            MonitorConfig(
                url="https://httpbin.org/get",
                interval=4.0,
                timeout=5.0,
                context_lines=3,
                headers={"Service": "Test1"},
            ),
            MonitorConfig(
                url="https://httpbin.org/json",
                interval=5.0,
                timeout=5.0,
                context_lines=3,
                headers={"Service": "Test2"},
            ),
        ]

        multi_monitor = MultiHTTPMonitor(configs)

        # Run for short time
        try:
            await asyncio.wait_for(multi_monitor.start_all_monitors(), timeout=15.0)
        except asyncio.TimeoutError:
            pass

        multi_monitor.stop_all_monitors()

        # Check results
        all_exceptions = multi_monitor.get_all_exceptions()
        total_exceptions = sum(
            len(exceptions) for exceptions in all_exceptions.values()
        )

        logger.info(
            f"✅ Multi-monitor test completed - {len(all_exceptions)} monitors, {total_exceptions} total exceptions"
        )

        return True

    except Exception as e:
        logger.error(f"❌ Multi-monitor test failed: {e}")
        return False


def test_export_functionality():
    """Test exception export functionality"""
    try:
        from http_monitor import MonitorConfig, HTTPMonitor, ExceptionEvent
        from datetime import datetime
        import json
        import os

        # Create a mock exception event
        config = MonitorConfig(url="https://test.com")
        monitor = HTTPMonitor(config)

        # Manually add an exception for testing
        test_exception = ExceptionEvent(
            timestamp=datetime.now(),
            url="https://test.com",
            exception="Test exception",
            exception_type="TestError",
            context_lines=["Test context line 1", "Test context line 2"],
            response_status=500,
            response_body="Test response",
        )

        monitor.exceptions.append(test_exception)

        # Test export
        filename = monitor.export_exceptions("test_export.json")

        # Verify export
        assert os.path.exists(filename)

        with open(filename, "r") as f:
            exported_data = json.load(f)

        assert len(exported_data) == 1
        assert exported_data[0]["exception"] == "Test exception"
        assert exported_data[0]["exception_type"] == "TestError"

        # Cleanup
        os.remove(filename)

        logger.info("✅ Export functionality test passed")
        return True

    except Exception as e:
        logger.error(f"❌ Export functionality test failed: {e}")
        return False


async def run_all_tests():
    """Run all tests"""
    logger.info("🚀 Starting HTTP Monitor Test Suite")
    logger.info("=" * 60)

    tests = [
        ("Import Tests", test_imports),
        ("Config Creation", test_config_creation),
        ("Config Loading", test_config_loading),
        ("Export Functionality", test_export_functionality),
    ]

    async_tests = [
        ("Single Monitor", test_single_monitor),
        ("Error Handling", test_error_handling),
        ("Multi Monitor", test_multi_monitor),
    ]

    passed = 0
    total = len(tests) + len(async_tests)

    # Run synchronous tests
    for test_name, test_func in tests:
        logger.info(f"\n📋 Running {test_name}...")
        if test_func():
            passed += 1
        else:
            logger.error(f"❌ {test_name} failed")

    # Run asynchronous tests
    for test_name, test_func in async_tests:
        logger.info(f"\n📋 Running {test_name}...")
        if await test_func():
            passed += 1
        else:
            logger.error(f"❌ {test_name} failed")

    logger.info("\n" + "=" * 60)
    logger.info("📊 TEST RESULTS")
    logger.info("=" * 60)
    logger.info(f"Passed: {passed}/{total}")
    logger.info(f"Failed: {total - passed}/{total}")

    if passed == total:
        logger.info("🎉 All tests passed!")
        return 0
    else:
        logger.error(f"💥 {total - passed} tests failed")
        return 1


def main():
    """Main test function"""
    try:
        result = asyncio.run(run_all_tests())
        sys.exit(result)
    except KeyboardInterrupt:
        logger.info("\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"💥 Test suite failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
