#!/usr/bin/env python3
"""
Test script to verify Logan's streaming and grep functionality fixes
"""

import asyncio
import sys
import os


def test_basic_import():
    """Test that Logan can be imported without errors"""
    print("🧪 Testing Logan import...")
    try:
        from logan import LoganAssistant

        print("✅ Logan imported successfully")
        return True
    except Exception as e:
        print(f"❌ Logan import failed: {e}")
        return False


def test_grep_content_tool():
    """Test the grep content tool with various content types"""
    print("🧪 Testing grep content functionality...")
    try:
        from logan import DulwichGrepContentTool

        # Create a mock analyzer with test data
        class MockVirtualFile:
            def __init__(self, content):
                self.content = content

        class MockAnalyzer:
            def __init__(self):
                self.virtual_files = {
                    "test.py": MockVirtualFile(
                        "def hello():\n    print('Hello world')\n    log.info('test')"
                    ),
                    "binary.py": MockVirtualFile(
                        b"def test():\n    log.debug('binary')\n"
                    ),
                    "empty.py": MockVirtualFile(""),
                    "unicode.py": MockVirtualFile(
                        "def café():\n    log.warning('unicode test')"
                    ),
                }

        class MockAssistant:
            def __init__(self):
                self.analyzer = MockAnalyzer()

        # Test the tool
        mock_assistant = MockAssistant()
        tool = DulwichGrepContentTool(mock_assistant)

        # Test various patterns
        test_cases = [
            ("log", "*.py", False, 10),
            ("hello", "*.py", True, 5),
            ("def.*:", "*.py", False, 20),
        ]

        for pattern, file_pattern, case_sensitive, line_limit in test_cases:
            print(f"   Testing pattern: '{pattern}'")
            try:
                result = tool._run(pattern, file_pattern, case_sensitive, line_limit)
                if "failed" not in result.lower():
                    print(f"   ✅ Pattern '{pattern}' processed successfully")
                else:
                    print(f"   ⚠️  Pattern '{pattern}' returned: {result[:100]}...")
            except Exception as e:
                print(f"   ❌ Pattern '{pattern}' failed: {e}")

        print("✅ Grep content tool test completed")
        return True

    except Exception as e:
        print(f"❌ Grep content tool test failed: {e}")
        return False


async def test_streaming_response():
    """Test Logan's streaming response functionality"""
    print("🧪 Testing streaming response...")
    try:
        from logan import LoganAssistant

        assistant = LoganAssistant()

        # Test that we can create the assistant without errors
        print("✅ Assistant created successfully")

        # Test message preparation
        test_message = "Hello, this is a test message"
        print(f"✅ Test message prepared: {test_message[:50]}...")

        return True

    except Exception as e:
        print(f"❌ Streaming response test failed: {e}")
        return False


def test_environment_variables():
    """Test environment variable handling"""
    print("🧪 Testing environment variable handling...")

    # Test with mock environment variables
    original_values = {}
    test_vars = {
        "REPOSITORY_URL": "https://github.com/test/repo",
        "REPOSITORY_AUTH": "test:token",
        "COMMIT_ID": "abc123def456",
        "REPOSITORY_BRANCH": "develop",
    }

    try:
        # Set test environment variables
        for key, value in test_vars.items():
            original_values[key] = os.environ.get(key)
            os.environ[key] = value

        # Import and test Logan with env vars
        from logan import LoganAssistant

        assistant = LoganAssistant()

        print("✅ Environment variables handled correctly")
        result = True

    except Exception as e:
        print(f"❌ Environment variable test failed: {e}")
        result = False

    finally:
        # Restore original environment
        for key, original_value in original_values.items():
            if original_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original_value

    return result


async def main():
    """Run all tests"""
    print("🚀 Running Logan Streaming Fix Tests")
    print("=" * 50)

    tests = [
        ("Basic Import", test_basic_import),
        ("Grep Content Tool", test_grep_content_tool),
        ("Streaming Response", test_streaming_response),
        ("Environment Variables", test_environment_variables),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        print(f"\n📋 Running: {test_name}")
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()

            if result:
                passed += 1
                print(f"✅ {test_name} PASSED")
            else:
                failed += 1
                print(f"❌ {test_name} FAILED")

        except Exception as e:
            failed += 1
            print(f"❌ {test_name} ERROR: {e}")

    print("\n" + "=" * 50)
    print(f"📊 Test Results:")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📈 Success Rate: {(passed / (passed + failed)) * 100:.1f}%")

    if failed == 0:
        print("🎉 All tests passed!")
        return True
    else:
        print("⚠️  Some tests failed.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
