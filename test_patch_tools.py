#!/usr/bin/env python3
"""
Test script for Logan's patch creation and application tools
"""

import os
import sys
import tempfile
import shutil
import subprocess
from pathlib import Path


def setup_test_repo():
    """Create a temporary git repository for testing"""
    test_dir = tempfile.mkdtemp(prefix="logan_patch_test_")
    os.chdir(test_dir)

    # Initialize git repo
    subprocess.run(["git", "init"], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], check=True)

    # Create initial files
    with open("main.py", "w") as f:
        f.write("""#!/usr/bin/env python3
def hello_world():
    print("Hello, World!")

def add_numbers(a, b):
    return a + b

if __name__ == "__main__":
    hello_world()
    result = add_numbers(2, 3)
    print(f"2 + 3 = {result}")
""")

    with open("utils.py", "w") as f:
        f.write("""def multiply(x, y):
    return x * y

def divide(x, y):
    if y == 0:
        raise ValueError("Cannot divide by zero")
    return x / y
""")

    with open("README.md", "w") as f:
        f.write("""# Test Project

This is a test project for Logan patch tools.

## Features
- Basic math operations
- Hello world functionality
""")

    # Initial commit
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], check=True)

    return test_dir


def modify_files():
    """Make some modifications to test patch creation"""
    # Modify main.py
    with open("main.py", "w") as f:
        f.write("""#!/usr/bin/env python3
def hello_world():
    print("Hello, World!")
    print("This is a modified version!")

def add_numbers(a, b):
    # Added input validation
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        raise TypeError("Arguments must be numbers")
    return a + b

def subtract_numbers(a, b):
    # New function added
    return a - b

if __name__ == "__main__":
    hello_world()
    result = add_numbers(2, 3)
    print(f"2 + 3 = {result}")

    diff = subtract_numbers(5, 2)
    print(f"5 - 2 = {diff}")
""")

    # Modify utils.py
    with open("utils.py", "w") as f:
        f.write("""def multiply(x, y):
    # Added input validation
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        raise TypeError("Arguments must be numbers")
    return x * y

def divide(x, y):
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        raise TypeError("Arguments must be numbers")
    if y == 0:
        raise ValueError("Cannot divide by zero")
    return x / y

def power(x, y):
    # New function
    return x ** y
""")

    # Create a new file
    with open("constants.py", "w") as f:
        f.write("""# Mathematical constants
PI = 3.14159265359
E = 2.71828182846
GOLDEN_RATIO = 1.61803398875
""")


def test_patch_creation():
    """Test the create_patch functionality"""
    print("🧪 Testing patch creation...")

    # Import Logan with our test environment
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    try:
        from logan import LoganAssistant, DulwichCreatePatchTool

        # Create a mock analyzer reference
        class MockAnalyzerRef:
            def __init__(self, repo_path):
                self.analyzer = MockAnalyzer(repo_path)

        class MockAnalyzer:
            def __init__(self, repo_path):
                self.repo_path = repo_path

        # Create the tool
        analyzer_ref = MockAnalyzerRef(os.getcwd())
        create_tool = DulwichCreatePatchTool(analyzer_ref)

        # Test patch creation
        result = create_tool._run(
            description="Add input validation and new functions",
            files=["main.py", "utils.py", "constants.py"],
            branch_name="feature/validation-and-new-functions",
            commit_message="Add input validation and new mathematical functions",
        )

        print("✅ Patch creation result:")
        print(result)

        return "feature/validation-and-new-functions"

    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Note: This test requires Logan's dependencies to be installed")
        return None


def test_patch_application():
    """Test applying a patch from a file"""
    print("\n🧪 Testing patch application...")

    # Create a simple patch file
    patch_content = """diff --git a/README.md b/README.md
index 1234567..abcdefg 100644
--- a/README.md
+++ b/README.md
@@ -4,3 +4,6 @@ This is a test project for Logan patch tools.

 ## Features
 - Basic math operations
-- Hello world functionality
+- Hello world functionality (enhanced)
+
+## Recent Changes
+- Added input validation
"""

    try:
        from logan import DulwichApplyPatchTool

        # Create a mock analyzer reference
        class MockAnalyzerRef:
            def __init__(self, repo_path):
                self.analyzer = MockAnalyzer(repo_path)

        class MockAnalyzer:
            def __init__(self, repo_path):
                self.repo_path = repo_path

        # Create the tool
        analyzer_ref = MockAnalyzerRef(os.getcwd())
        apply_tool = DulwichApplyPatchTool(analyzer_ref)

        # Test patch application
        result = apply_tool._run(
            patch_content=patch_content,
            target_branch="main",
            create_branch=True,
            branch_name="patch/readme-update",
        )

        print("✅ Patch application result:")
        print(result)

    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Note: This test requires Logan's dependencies to be installed")


def test_git_operations():
    """Test basic git operations work in our setup"""
    print("\n🧪 Testing git operations...")

    # Check current status
    result = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True
    )
    print(f"Git status: {result.stdout}")

    # Check branches
    result = subprocess.run(["git", "branch"], capture_output=True, text=True)
    print(f"Branches: {result.stdout}")

    # Check recent commits
    result = subprocess.run(
        ["git", "log", "--oneline", "-5"], capture_output=True, text=True
    )
    print(f"Recent commits:\n{result.stdout}")


def main():
    """Main test function"""
    print("🚀 Starting Logan patch tools test")

    # Save original directory
    original_dir = os.getcwd()

    try:
        # Setup test repository
        test_dir = setup_test_repo()
        print(f"📁 Created test repository at: {test_dir}")

        # Make modifications
        modify_files()
        print("📝 Modified files for testing")

        # Test git operations
        test_git_operations()

        # Test patch creation
        patch_branch = test_patch_creation()

        # Reset to main branch for patch application test
        subprocess.run(["git", "checkout", "main"], capture_output=True)

        # Test patch application
        test_patch_application()

        print("\n🎉 All tests completed!")
        print(f"🗂️  Test repository available at: {test_dir}")
        print(
            "💡 You can manually inspect the repository to verify the patches work correctly"
        )

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()

    finally:
        # Restore original directory
        os.chdir(original_dir)


if __name__ == "__main__":
    main()
