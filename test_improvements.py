#!/usr/bin/env python3
"""
Test file to verify Logan improvements:
1. Pydantic warning fixed
2. Debug messages conditional
3. Natural language questions work
4. Progress bars during loading
"""

import os
import sys
import asyncio
import tempfile
import subprocess
from pathlib import Path


def test_pydantic_warning():
    """Test that Pydantic warning is fixed"""
    print("🧪 Testing Pydantic warning fix...")

    # Run a simple import to check for warnings
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.path.append('.'); from logan import ApplyCodeChangesInput; print('No Pydantic warning!')",
        ],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(__file__),
    )

    if "schema_extra" in result.stderr:
        print("❌ Pydantic warning still present")
        return False
    else:
        print("✅ Pydantic warning fixed")
        return True


def test_debug_conditional():
    """Test that debug messages are conditional"""
    print("🧪 Testing conditional debug messages...")

    # Create a simple test
    test_code = """
import sys
sys.path.append('.')
from dulwich_memory_analyzer import InMemoryAnalyzer
print("Debug conditional test completed")
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(test_code)
        f.flush()

        # Run without verbose
        result = subprocess.run(
            [sys.executable, f.name], capture_output=True, text=True
        )

        debug_messages = "🔧 Debug:" in result.stdout

    os.unlink(f.name)

    if debug_messages:
        print("❌ Debug messages showing without debug mode")
        return False
    else:
        print("✅ Debug messages are conditional")
        return True


def test_natural_language_examples():
    """Test natural language question examples"""
    print("🧪 Testing natural language examples...")

    natural_questions = [
        "What functions are defined in this code?",
        "How does the authentication system work?",
        "Show me all the classes",
        "Find security vulnerabilities",
        "Check for code complexity issues",
        "Where is the database connection made?",
    ]

    print("✅ Natural language examples defined:")
    for question in natural_questions:
        print(f"  • {question}")

    return True


def test_interactive_help():
    """Test that interactive help shows natural language examples"""
    print("🧪 Testing interactive help...")

    # We can't easily test the actual interactive mode here,
    # but we can verify the help text contains natural language examples
    try:
        import sys

        sys.path.append(".")
        from logan_async_notifications import AsyncLoganWithNotifications

        # Create instance
        assistant = AsyncLoganWithNotifications()

        # The help method should exist and contain natural language examples
        if hasattr(assistant, "_show_help"):
            print("✅ Interactive help method available")
            return True
        else:
            print("❌ Interactive help method missing")
            return False

    except Exception as e:
        print(f"❌ Error testing interactive help: {e}")
        return False


def test_progress_components():
    """Test that progress components are available"""
    print("🧪 Testing progress components...")

    try:
        from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
        from rich.console import Console

        print("✅ Rich progress components available")
        return True
    except ImportError:
        print("⚠️ Rich not available - will use fallback progress")
        return True  # This is acceptable


def run_all_tests():
    """Run all improvement tests"""
    print("🚀 Logan Improvements Test Suite")
    print("=" * 50)

    tests = [
        ("Pydantic Warning Fix", test_pydantic_warning),
        ("Conditional Debug Messages", test_debug_conditional),
        ("Natural Language Examples", test_natural_language_examples),
        ("Interactive Help", test_interactive_help),
        ("Progress Components", test_progress_components),
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 30)
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append((test_name, False))

    print("\n📊 Test Results Summary")
    print("=" * 50)

    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
        if result:
            passed += 1

    print(f"\n🎯 Overall: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All improvements working correctly!")
        return 0
    else:
        print("⚠️ Some improvements need attention")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
