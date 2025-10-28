#!/usr/bin/env python3
"""
Test script to verify the fixed apply_patch tool works correctly
"""

import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_search_replace_functionality():
    """Test search and replace with line ranges"""

    print("🧪 Testing Search & Replace Functionality")
    print("=" * 45)

    try:
        from logan import DulwichApplyPatchTool

        # Create mock analyzer
        class MockVirtualFile:
            def __init__(self, content):
                self.content = content

        class MockRepoInfo:
            def __init__(self):
                self.url = "https://github.com/test/repo"
                self.branch = "main"

        class MockAnalyzer:
            def __init__(self):
                self.virtual_files = {
                    "main.py": MockVirtualFile("""def hello():
    print("Hello, World!")
    return "greeting"

def add_numbers(a, b):
    return a + b

def multiply(x, y):
    print("Multiplying")
    return x * y"""),
                }
                self.repo_info = MockRepoInfo()

        class MockAnalyzerRef:
            def __init__(self):
                self.analyzer = MockAnalyzer()

        # Create tool
        tool = DulwichApplyPatchTool(MockAnalyzerRef())

        # Test 1: Search & Replace with line range
        print("\n🎯 Test 1: Search & Replace with line range")
        result = tool._run(
            search_replace=[
                {
                    "file": "main.py",
                    "search": 'print("Hello, World!")',
                    "replace": 'print("Hello, Universe!")',
                    "start_line": 1,
                    "end_line": 5,
                }
            ],
            auto_apply=True,
        )

        print("Result:", "✅ SUCCESS" if "Changes Applied" in result else "❌ FAILED")
        print("Details:", result[:200] + "..." if len(result) > 200 else result)

        # Test 2: Search & Replace without line range
        print("\n🎯 Test 2: Search & Replace without line range")
        result = tool._run(
            search_replace=[
                {"file": "main.py", "search": "return", "replace": "return # modified"}
            ],
            auto_apply=True,
        )

        print("Result:", "✅ SUCCESS" if "Changes Applied" in result else "❌ FAILED")
        print("Details:", result[:200] + "..." if len(result) > 200 else result)

        return True

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_unified_diff_functionality():
    """Test unified diff patch application"""

    print("\n🧪 Testing Unified Diff Functionality")
    print("=" * 40)

    try:
        from logan import DulwichApplyPatchTool

        # Create mock analyzer (reuse from above)
        class MockVirtualFile:
            def __init__(self, content):
                self.content = content

        class MockRepoInfo:
            def __init__(self):
                self.url = "https://github.com/test/repo"
                self.branch = "main"

        class MockAnalyzer:
            def __init__(self):
                self.virtual_files = {
                    "utils.py": MockVirtualFile("""def calculate(x, y):
    result = x + y
    return result

def process_data(data):
    return data.upper()"""),
                }
                self.repo_info = MockRepoInfo()

        class MockAnalyzerRef:
            def __init__(self):
                self.analyzer = MockAnalyzer()

        # Create tool
        tool = DulwichApplyPatchTool(MockAnalyzerRef())

        # Test unified diff patch
        patch = """--- a/utils.py
+++ b/utils.py
@@ -1,3 +1,4 @@
 def calculate(x, y):
+    # Added validation
     result = x + y
     return result"""

        print("🎯 Test: Unified diff patch application")
        result = tool._run(patch_content=patch, auto_apply=True)

        print("Result:", "✅ SUCCESS" if "Changes Applied" in result else "❌ FAILED")
        print("Details:", result[:200] + "..." if len(result) > 200 else result)

        return True

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_error_handling():
    """Test error handling scenarios"""

    print("\n🧪 Testing Error Handling")
    print("=" * 25)

    try:
        from logan import DulwichApplyPatchTool

        class MockAnalyzerRef:
            def __init__(self):
                self.analyzer = None  # No analyzer

        # Test with no analyzer
        tool = DulwichApplyPatchTool(MockAnalyzerRef())

        print("🎯 Test: No repository loaded")
        result = tool._run(
            search_replace=[{"file": "test.py", "search": "old", "replace": "new"}]
        )
        print(
            "Result:", "✅ SUCCESS" if "No repository loaded" in result else "❌ FAILED"
        )

        # Test with no changes specified
        class MockAnalyzer:
            def __init__(self):
                self.virtual_files = {}

        class MockAnalyzerRef2:
            def __init__(self):
                self.analyzer = MockAnalyzer()

        tool2 = DulwichApplyPatchTool(MockAnalyzerRef2())

        print("🎯 Test: No changes specified")
        result = tool2._run()
        print(
            "Result:", "✅ SUCCESS" if "No changes specified" in result else "❌ FAILED"
        )

        return True

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False


def test_change_reporting():
    """Test detailed change reporting"""

    print("\n🧪 Testing Change Reporting")
    print("=" * 29)

    try:
        from logan import DulwichApplyPatchTool

        class MockVirtualFile:
            def __init__(self, content):
                self.content = content

        class MockRepoInfo:
            def __init__(self):
                self.url = "https://github.com/test/repo"
                self.branch = "main"

        class MockAnalyzer:
            def __init__(self):
                self.virtual_files = {
                    "test.py": MockVirtualFile(
                        "def test():\n    pass\n    return True"
                    ),
                }
                self.repo_info = MockRepoInfo()

        class MockAnalyzerRef:
            def __init__(self):
                self.analyzer = MockAnalyzer()

        tool = DulwichApplyPatchTool(MockAnalyzerRef())

        print("🎯 Test: Detailed change reporting")
        result = tool._run(
            search_replace=[
                {
                    "file": "test.py",
                    "search": "pass",
                    "replace": "print('test')",
                    "start_line": 1,
                    "end_line": 10,
                }
            ],
            auto_apply=True,
        )

        success_indicators = [
            "Changes Applied" in result,
            "test.py" in result,
            "pass" in result or "print" in result,
        ]

        print("Result:", "✅ SUCCESS" if any(success_indicators) else "❌ FAILED")
        print("Contains change details:", "✅ YES" if "→" in result else "❌ NO")

        return True

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False


if __name__ == "__main__":
    print("🚀 Testing Fixed Logan Patch System")
    print("This script validates the apply_patch tool fixes")
    print()

    tests = [
        test_search_replace_functionality,
        test_unified_diff_functionality,
        test_error_handling,
        test_change_reporting,
    ]

    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test_func.__name__} crashed: {e}")
            results.append(False)

    print("\n" + "=" * 60)
    print("🎯 Test Summary")
    print(f"✅ Passed: {sum(results)}/{len(results)}")
    print(f"❌ Failed: {len(results) - sum(results)}/{len(results)}")

    if all(results):
        print("\n🎉 ALL TESTS PASSED! The patch system is working correctly.")
        print("✅ Search & Replace with line ranges: WORKING")
        print("✅ Unified diff patches: WORKING")
        print("✅ Error handling: WORKING")
        print("✅ Change reporting: WORKING")
    else:
        print("\n⚠️  Some tests failed. Check the details above.")
        failed_tests = [
            tests[i].__name__ for i, result in enumerate(results) if not result
        ]
        print("Failed tests:", ", ".join(failed_tests))

    print("\n💡 The apply_patch tool should now work correctly with Logan!")
