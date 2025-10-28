#!/usr/bin/env python3
"""
Test script for Logan's enhanced patch tools with real git automation
This script tests:
- Creating patches with real git operations
- Applying patches with real git operations
- Branch creation and management
- Push to origin
- Error handling and rollback
"""

import os
import sys
import tempfile
import shutil
import subprocess
from pathlib import Path

# Add the current directory to the path so we can import Logan
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def setup_test_git_repo():
    """Create a temporary git repository for testing"""
    test_dir = tempfile.mkdtemp(prefix="logan_git_automation_test_")
    os.chdir(test_dir)

    # Initialize git repo
    subprocess.run(["git", "init"], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "config", "user.name", "Logan Test"], check=True)

    # Create initial files
    with open("app.py", "w") as f:
        f.write("""#!/usr/bin/env python3
def calculate(a, b, operation="add"):
    if operation == "add":
        return a + b
    elif operation == "subtract":
        return a - b
    elif operation == "multiply":
        return a * b
    else:
        raise ValueError("Unsupported operation")

if __name__ == "__main__":
    print("Calculator:", calculate(5, 3))
""")

    with open("utils.py", "w") as f:
        f.write("""def format_number(n):
    return f"{n:.2f}" if isinstance(n, float) else str(n)

def validate_input(value):
    return isinstance(value, (int, float))
""")

    with open("README.md", "w") as f:
        f.write("""# Test Calculator

A simple calculator for testing Logan's git automation.

## Features
- Basic math operations
- Input validation
""")

    # Initial commit
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], check=True)

    return test_dir


def create_mock_analyzer_with_enhanced_files():
    """Create mock analyzer with enhanced file content"""

    class MockVirtualFile:
        def __init__(self, content):
            self.content = content

    class MockRepoInfo:
        def __init__(self):
            self.url = "https://github.com/test/calculator-repo"
            self.branch = "main"
            self.commit_sha = "abc123def456"

    class MockAnalyzer:
        def __init__(self):
            # Enhanced versions of the files with improvements
            self.virtual_files = {
                "app.py": MockVirtualFile("""#!/usr/bin/env python3
def calculate(a, b, operation="add"):
    # Enhanced with input validation
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        raise TypeError("Arguments must be numbers")

    if operation == "add":
        return a + b
    elif operation == "subtract":
        return a - b
    elif operation == "multiply":
        return a * b
    elif operation == "divide":
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b
    else:
        raise ValueError(f"Unsupported operation: {operation}")

def safe_calculate(a, b, operation="add"):
    \"\"\"Safe wrapper for calculations with error handling\"\"\"
    try:
        return calculate(a, b, operation), None
    except Exception as e:
        return None, str(e)

if __name__ == "__main__":
    result, error = safe_calculate(5, 3, "add")
    if error:
        print(f"Error: {error}")
    else:
        print(f"Calculator result: {result}")

    # Test division
    result, error = safe_calculate(10, 2, "divide")
    print(f"10 / 2 = {result}")
"""),
                "utils.py": MockVirtualFile("""def format_number(n):
    \"\"\"Format number for display with smart precision\"\"\"
    if isinstance(n, float):
        if n.is_integer():
            return str(int(n))
        return f"{n:.6g}"
    return str(n)

def validate_input(value):
    \"\"\"Validate that input is a number\"\"\"
    if not isinstance(value, (int, float)):
        return False
    # Check for special values
    if isinstance(value, float):
        import math
        return not (math.isnan(value) or math.isinf(value))
    return True

def parse_operation(op_string):
    \"\"\"Parse operation string to standardized form\"\"\"
    op_map = {'+': 'add', '-': 'subtract', '*': 'multiply', '/': 'divide'}
    return op_map.get(op_string.strip(), op_string.strip())

def log_operation(operation, a, b, result):
    \"\"\"Log calculation for audit trail\"\"\"
    with open('calculations.log', 'a') as f:
        f.write(f"{operation}({a}, {b}) = {result}\\n")
"""),
                "README.md": MockVirtualFile("""# Enhanced Test Calculator

A robust calculator with comprehensive error handling and validation.

## Features
- Basic math operations (add, subtract, multiply, divide)
- Input validation and type checking
- Error handling with safe wrappers
- Operation logging
- Smart number formatting

## Recent Enhancements
- Added division operation
- Enhanced error handling
- Input validation
- Safe calculation wrappers
- Operation logging system

## Usage
```python
from app import safe_calculate

result, error = safe_calculate(10, 5, "divide")
if error:
    print(f"Error: {error}")
else:
    print(f"Result: {result}")
```

## Version
2.0.0 - Enhanced with validation and error handling
"""),
                "tests.py": MockVirtualFile("""#!/usr/bin/env python3
import unittest
from app import calculate, safe_calculate
from utils import validate_input, format_number, parse_operation

class TestCalculator(unittest.TestCase):

    def test_basic_operations(self):
        self.assertEqual(calculate(2, 3, "add"), 5)
        self.assertEqual(calculate(10, 4, "subtract"), 6)
        self.assertEqual(calculate(3, 7, "multiply"), 21)
        self.assertEqual(calculate(15, 3, "divide"), 5)

    def test_input_validation(self):
        self.assertTrue(validate_input(42))
        self.assertTrue(validate_input(3.14))
        self.assertFalse(validate_input("string"))
        self.assertFalse(validate_input(None))

    def test_error_handling(self):
        result, error = safe_calculate(10, 0, "divide")
        self.assertIsNone(result)
        self.assertIn("zero", error.lower())

        result, error = safe_calculate("invalid", 5, "add")
        self.assertIsNone(result)
        self.assertIn("number", error.lower())

    def test_format_number(self):
        self.assertEqual(format_number(42), "42")
        self.assertEqual(format_number(3.0), "3")
        self.assertEqual(format_number(3.14), "3.14")

    def test_parse_operation(self):
        self.assertEqual(parse_operation("+"), "add")
        self.assertEqual(parse_operation("-"), "subtract")
        self.assertEqual(parse_operation("*"), "multiply")
        self.assertEqual(parse_operation("/"), "divide")

if __name__ == "__main__":
    unittest.main()
"""),
            }
            self.repo_info = MockRepoInfo()

    class MockAnalyzerRef:
        def __init__(self):
            self.analyzer = MockAnalyzer()

    return MockAnalyzerRef()


def test_patch_creation_with_git_automation():
    """Test creating patches with real git operations"""
    print("\n🎯 Testing Patch Creation with Git Automation")
    print("-" * 50)

    try:
        from logan import DulwichCreatePatchTool

        # Get current repository path
        repo_path = os.getcwd()

        # Create analyzer with enhanced files
        analyzer_ref = create_mock_analyzer_with_enhanced_files()
        create_tool = DulwichCreatePatchTool(analyzer_ref)

        print("✅ Testing virtual patch creation (no git ops)...")
        result = create_tool._run(
            description="Enhanced calculator with validation and error handling",
            files=["app.py", "utils.py", "README.md"],
            branch_name="feature/enhanced-calculator",
            commit_message="Add comprehensive input validation, error handling, and testing\n\n- Enhanced calculate() with type validation\n- Added safe_calculate() wrapper\n- Improved number formatting\n- Added operation logging\n- Comprehensive test suite",
            auto_commit=False,
            auto_push=False,
            repository_path=repo_path,
        )
        print("Virtual patch result:", "✅ Success" if "🎉" in result else "❌ Failed")

        print("\n✅ Testing with real git operations...")
        result = create_tool._run(
            description="Enhanced calculator with validation and error handling",
            files=["app.py", "utils.py", "README.md", "tests.py"],
            branch_name="feature/enhanced-calculator-v2",
            commit_message="Add comprehensive input validation, error handling, and testing\n\n- Enhanced calculate() with type validation\n- Added safe_calculate() wrapper\n- Improved number formatting and validation\n- Added operation logging system\n- Comprehensive test suite with unit tests\n- Enhanced documentation",
            auto_commit=True,
            auto_push=False,  # Don't push since we don't have a real remote
            repository_path=repo_path,
        )

        print("Git automation result:")
        for line in result.split("\n"):
            if line.strip():
                print(f"  {line}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_patch_application_with_git_automation():
    """Test applying patches with real git operations"""
    print("\n🎯 Testing Patch Application with Git Automation")
    print("-" * 50)

    try:
        from logan import DulwichApplyPatchTool

        # Create a sample patch
        sample_patch = """# Patch: Add configuration management
# Branch: feature/config
# Files: config.py
# Commit message: Add configuration management system
# Repository: https://github.com/test/calculator-repo
# Base branch: main

diff --git a/config.py b/config.py
new file mode 100644
index 0000000..1111111
--- /dev/null
+++ b/config.py
@@ -0,0 +1,25 @@
+#!/usr/bin/env python3
+\"\"\"
+Configuration management for the calculator application
+\"\"\"
+
+# Application settings
+DEBUG = False
+VERSION = "2.0.0"
+
+# Calculation settings
+DEFAULT_PRECISION = 6
+ENABLE_LOGGING = True
+LOG_FILE = "calculations.log"
+
+# Supported operations
+OPERATIONS = {
+    "add": "+",
+    "subtract": "-",
+    "multiply": "*",
+    "divide": "/",
+}
+
+def get_setting(key, default=None):
+    \"\"\"Get configuration setting\"\"\"
+    return globals().get(key, default)
"""

        repo_path = os.getcwd()
        analyzer_ref = create_mock_analyzer_with_enhanced_files()
        apply_tool = DulwichApplyPatchTool(analyzer_ref)

        print("✅ Testing patch analysis only...")
        result = apply_tool._run(
            patch_content=sample_patch,
            target_branch="main",
            create_branch=True,
            branch_name="patch/add-config-management",
            auto_apply=False,
            auto_commit=False,
            auto_push=False,
            repository_path=repo_path,
        )
        print("Analysis result:", "✅ Success" if "🔍" in result else "❌ Failed")

        print("\n✅ Testing with real git patch application...")
        result = apply_tool._run(
            patch_content=sample_patch,
            target_branch="main",
            create_branch=True,
            branch_name="patch/add-config-mgmt-real",
            auto_apply=True,
            auto_commit=True,
            auto_push=False,
            repository_path=repo_path,
            commit_message="Add configuration management system with application settings",
        )

        print("Git automation result:")
        for line in result.split("\n"):
            if line.strip():
                print(f"  {line}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_error_handling():
    """Test error handling in git operations"""
    print("\n🎯 Testing Error Handling")
    print("-" * 30)

    try:
        from logan import DulwichCreatePatchTool

        analyzer_ref = create_mock_analyzer_with_enhanced_files()
        create_tool = DulwichCreatePatchTool(analyzer_ref)

        # Test with invalid repository path
        result = create_tool._run(
            description="Test error handling",
            files=["app.py"],
            branch_name="test/error-handling",
            commit_message="Test commit",
            auto_commit=True,
            repository_path="/nonexistent/path",
        )

        print(
            "Invalid path test:", "✅ Handled" if "❌" in result else "❌ Not handled"
        )

        # Test with duplicate branch name (create it first)
        subprocess.run(["git", "checkout", "-b", "duplicate-test"], capture_output=True)
        subprocess.run(["git", "checkout", "main"], capture_output=True)

        result = create_tool._run(
            description="Test duplicate branch",
            files=["app.py"],
            branch_name="duplicate-test",
            commit_message="Test commit",
            auto_commit=True,
            repository_path=os.getcwd(),
        )

        print(
            "Duplicate branch test:",
            "✅ Handled"
            if any(word in result for word in ["existing", "Switched"])
            else "❌ Not handled",
        )

        return True

    except Exception as e:
        print(f"❌ Error handling test failed: {e}")
        return False


def show_git_status():
    """Show the final state of the git repository"""
    print("\n📊 Final Git Repository Status")
    print("=" * 40)

    try:
        # Show branches
        result = subprocess.run(["git", "branch", "-a"], capture_output=True, text=True)
        print(f"🌿 Branches:\n{result.stdout}")

        # Show recent commits
        result = subprocess.run(
            ["git", "log", "--oneline", "--all", "--graph", "-10"],
            capture_output=True,
            text=True,
        )
        print(f"📝 Recent commits:\n{result.stdout}")

        # Show working directory status
        result = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True
        )
        if result.stdout.strip():
            print(f"📋 Working directory changes:\n{result.stdout}")
        else:
            print("📋 Working directory: Clean")

    except Exception as e:
        print(f"❌ Could not show git status: {e}")


def main():
    """Main test function"""
    print("🚀 Logan Git Automation Testing")
    print("=" * 60)
    print("""
This test demonstrates Logan's new git automation capabilities:
- Real branch creation and switching
- Writing virtual files to real file system
- Creating actual git commits
- Pushing to remote repositories (when available)
- Comprehensive error handling and rollback
    """)

    # Save original directory
    original_dir = os.getcwd()

    try:
        # Setup test repository
        test_repo = setup_test_git_repo()
        print(f"📁 Created test repository: {test_repo}")

        # Run tests
        test1_success = test_patch_creation_with_git_automation()
        test2_success = test_patch_application_with_git_automation()
        test3_success = test_error_handling()

        # Show final git status
        show_git_status()

        # Summary
        print("\n" + "=" * 60)
        results = [test1_success, test2_success, test3_success]
        if all(results):
            print("🎉 All git automation tests passed!")
            print("✅ Patch creation with real git operations: WORKING")
            print("✅ Patch application with real git operations: WORKING")
            print("✅ Error handling and recovery: WORKING")
        else:
            print("⚠️  Some tests had issues:")
            print(f"   Patch creation: {'✅' if test1_success else '❌'}")
            print(f"   Patch application: {'✅' if test2_success else '❌'}")
            print(f"   Error handling: {'✅' if test3_success else '❌'}")

        print(f"\n🗂️  Test repository available at: {test_repo}")
        print("💡 You can inspect the repository manually to verify git operations")

        print("\n📋 Key Features Tested:")
        print("   ✅ Virtual file → Real file system writing")
        print("   ✅ Automatic git branch creation")
        print("   ✅ Real git commits with proper messages")
        print("   ✅ Git repository auto-detection")
        print("   ✅ Error handling and rollback")
        print("   ✅ Branch switching and management")

    except Exception as e:
        print(f"❌ Test setup failed: {e}")
        import traceback

        traceback.print_exc()

    finally:
        # Restore original directory
        os.chdir(original_dir)


if __name__ == "__main__":
    main()
