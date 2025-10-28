#!/usr/bin/env python3
"""
Demonstration script for Logan's patch creation and application tools

This script shows how to use Logan's patching functionality to:
1. Create patches on separate branches for later cherry-picking
2. Apply patches to target branches
3. Handle typical patch management workflows

Usage:
    python3 patch_demo.py [--demo-type TYPE]

Demo types:
    - create: Demonstrate patch creation
    - apply: Demonstrate patch application
    - workflow: Show complete workflow
    - all: Run all demonstrations (default)
"""

import os
import sys
import argparse
import tempfile
import subprocess
from pathlib import Path


class PatchDemo:
    """Demonstrates Logan's patch tools functionality"""

    def __init__(self):
        self.original_dir = os.getcwd()
        self.test_repo = None

    def setup_demo_repo(self):
        """Create a demo repository with sample files"""
        print("🏗️  Setting up demonstration repository...")

        self.test_repo = tempfile.mkdtemp(prefix="logan_patch_demo_")
        os.chdir(self.test_repo)

        # Initialize git repo
        subprocess.run(["git", "init"], check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "demo@example.com"], check=True)
        subprocess.run(["git", "config", "user.name", "Logan Demo"], check=True)

        # Create sample project files
        self.create_sample_files()

        # Initial commit
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", "Initial project setup"], check=True)

        print(f"📁 Demo repository created at: {self.test_repo}")

    def create_sample_files(self):
        """Create sample files for demonstration"""

        # Main application file
        with open("app.py", "w") as f:
            f.write("""#!/usr/bin/env python3
\"\"\"
Sample application for patch demonstration
\"\"\"

def calculate(operation, a, b):
    if operation == "add":
        return a + b
    elif operation == "subtract":
        return a - b
    elif operation == "multiply":
        return a * b
    elif operation == "divide":
        return a / b
    else:
        raise ValueError("Unsupported operation")

def main():
    print("Calculator App")
    result = calculate("add", 10, 5)
    print(f"10 + 5 = {result}")

if __name__ == "__main__":
    main()
""")

        # Utility functions
        with open("utils.py", "w") as f:
            f.write("""\"\"\"
Utility functions for the sample application
\"\"\"

def validate_input(value):
    if not isinstance(value, (int, float)):
        return False
    return True

def format_result(result):
    if isinstance(result, float):
        return f"{result:.2f}"
    return str(result)
""")

        # Configuration file
        with open("config.py", "w") as f:
            f.write("""# Configuration settings
DEBUG = False
VERSION = "1.0.0"
SUPPORTED_OPERATIONS = ["add", "subtract", "multiply", "divide"]
""")

        # README file
        with open("README.md", "w") as f:
            f.write("""# Sample Calculator App

A simple calculator application for demonstrating Logan's patch tools.

## Features
- Basic arithmetic operations
- Input validation
- Configurable settings

## Usage
```bash
python3 app.py
```

## Version
1.0.0
""")

    def demonstrate_patch_creation(self):
        """Demonstrate creating patches on separate branches"""
        print("\n🎯 === PATCH CREATION DEMONSTRATION ===")

        # Make some improvements to the code
        print("📝 Making improvements to demonstrate patch creation...")

        # Improve the main app with better error handling
        with open("app.py", "w") as f:
            f.write("""#!/usr/bin/env python3
\"\"\"
Sample application for patch demonstration - Enhanced version
\"\"\"
import sys
from utils import validate_input, format_result

def calculate(operation, a, b):
    # Enhanced with input validation
    if not validate_input(a) or not validate_input(b):
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

def safe_calculate(operation, a, b):
    \"\"\"Wrapper for safe calculation with error handling\"\"\"
    try:
        result = calculate(operation, a, b)
        return format_result(result), None
    except Exception as e:
        return None, str(e)

def main():
    print("Enhanced Calculator App v1.1")

    # Demonstrate various operations
    operations = [
        ("add", 10, 5),
        ("subtract", 20, 8),
        ("multiply", 7, 6),
        ("divide", 15, 3)
    ]

    for op, a, b in operations:
        result, error = safe_calculate(op, a, b)
        if error:
            print(f"{a} {op} {b} = Error: {error}")
        else:
            print(f"{a} {op} {b} = {result}")

if __name__ == "__main__":
    main()
""")

        # Add new utility functions
        with open("utils.py", "w") as f:
            f.write("""\"\"\"
Enhanced utility functions for the sample application
\"\"\"
import re

def validate_input(value):
    \"\"\"Validate that input is a number\"\"\"
    if not isinstance(value, (int, float)):
        return False
    # Check for NaN and infinity
    if isinstance(value, float):
        import math
        if math.isnan(value) or math.isinf(value):
            return False
    return True

def format_result(result):
    \"\"\"Format numerical results for display\"\"\"
    if isinstance(result, float):
        if result.is_integer():
            return str(int(result))
        return f"{result:.6g}"  # Smart formatting
    return str(result)

def parse_expression(expression):
    \"\"\"Parse a mathematical expression string\"\"\"
    # Simple regex for basic operations
    pattern = r'^(\d+(?:\.\d+)?)\s*([+\-*/])\s*(\d+(?:\.\d+)?)$'
    match = re.match(pattern, expression.strip())

    if not match:
        raise ValueError("Invalid expression format")

    a = float(match.group(1))
    operation_map = {'+': 'add', '-': 'subtract', '*': 'multiply', '/': 'divide'}
    operation = operation_map[match.group(2)]
    b = float(match.group(3))

    return operation, a, b

def log_operation(operation, a, b, result):
    \"\"\"Log calculation operations\"\"\"
    with open("calculation.log", "a") as f:
        f.write(f"{operation}({a}, {b}) = {result}\\n")
""")

        # Update configuration
        with open("config.py", "w") as f:
            f.write("""# Enhanced configuration settings
DEBUG = False
VERSION = "1.1.0"
SUPPORTED_OPERATIONS = ["add", "subtract", "multiply", "divide"]

# New configuration options
LOG_CALCULATIONS = True
MAX_PRECISION = 6
ALLOW_INFINITY = False

# Error messages
ERROR_MESSAGES = {
    "invalid_operation": "Operation not supported",
    "type_error": "Invalid input type - numbers only",
    "division_by_zero": "Cannot divide by zero",
    "invalid_expression": "Invalid mathematical expression"
}
""")

        # Add a new test file
        with open("test_calculator.py", "w") as f:
            f.write("""#!/usr/bin/env python3
\"\"\"
Test suite for the calculator application
\"\"\"
import unittest
from app import calculate, safe_calculate
from utils import validate_input, format_result, parse_expression

class TestCalculator(unittest.TestCase):

    def test_basic_operations(self):
        self.assertEqual(calculate("add", 2, 3), 5)
        self.assertEqual(calculate("subtract", 10, 4), 6)
        self.assertEqual(calculate("multiply", 3, 7), 21)
        self.assertEqual(calculate("divide", 15, 3), 5)

    def test_input_validation(self):
        self.assertTrue(validate_input(42))
        self.assertTrue(validate_input(3.14))
        self.assertFalse(validate_input("string"))
        self.assertFalse(validate_input(None))

    def test_error_handling(self):
        result, error = safe_calculate("divide", 10, 0)
        self.assertIsNone(result)
        self.assertIn("zero", error.lower())

    def test_expression_parsing(self):
        op, a, b = parse_expression("10 + 5")
        self.assertEqual(op, "add")
        self.assertEqual(a, 10)
        self.assertEqual(b, 5)

if __name__ == "__main__":
    unittest.main()
""")

        print("✅ Enhanced application files created")

        # Now demonstrate using Logan's create_patch tool
        self.simulate_logan_patch_creation()

    def simulate_logan_patch_creation(self):
        """Simulate how Logan would create a patch"""
        print("\n🧠 Logan would now create a patch like this:")
        print("=" * 60)

        # Show what the tool call would look like
        print("""
Logan Tool Call:
create_patch(
    description="Enhanced calculator with validation and error handling",
    files=["app.py", "utils.py", "config.py", "test_calculator.py"],
    branch_name="feature/enhanced-calculator",
    commit_message="Add input validation, error handling, and comprehensive testing

- Enhanced calculate() function with type validation
- Added safe_calculate() wrapper for error handling
- Improved utility functions with better formatting
- Added expression parsing capabilities
- Comprehensive test suite with unit tests
- Updated configuration with new options
- Better error messages and logging support"
)
        """)

        # Actually create the patch using git commands directly
        try:
            # Add all modified files
            subprocess.run(
                ["git", "add", "app.py", "utils.py", "config.py", "test_calculator.py"],
                check=True,
                capture_output=True,
            )

            # Create new branch
            result = subprocess.run(
                ["git", "checkout", "-b", "feature/enhanced-calculator"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                print(f"⚠️  Branch might already exist: {result.stderr}")

            # Commit changes
            commit_result = subprocess.run(
                [
                    "git",
                    "commit",
                    "-m",
                    """Add input validation, error handling, and comprehensive testing

- Enhanced calculate() function with type validation
- Added safe_calculate() wrapper for error handling
- Improved utility functions with better formatting
- Added expression parsing capabilities
- Comprehensive test suite with unit tests
- Updated configuration with new options
- Better error messages and logging support""",
                ],
                capture_output=True,
                text=True,
            )

            if commit_result.returncode == 0:
                # Get commit hash
                hash_result = subprocess.run(
                    ["git", "rev-parse", "HEAD"], capture_output=True, text=True
                )
                commit_hash = (
                    hash_result.stdout.strip()[:8]
                    if hash_result.returncode == 0
                    else "unknown"
                )

                print(f"""
✅ Patch Creation Result:

🎉 Patch created successfully!
📝 Description: Enhanced calculator with validation and error handling
🌿 Branch: feature/enhanced-calculator
💾 Commit: {commit_hash}
📂 Original branch: main

📋 Files included:
   ✅ app.py - Enhanced with validation and error handling
   ✅ utils.py - Added parsing and logging functions
   ✅ config.py - Updated with new configuration options
   ✅ test_calculator.py - Comprehensive test suite

🍒 To cherry-pick later: git cherry-pick {commit_hash}
🔀 To merge: git merge feature/enhanced-calculator
                """)
            else:
                print(f"❌ Commit failed: {commit_result.stderr}")

            # Switch back to main
            subprocess.run(["git", "checkout", "main"], capture_output=True)

        except subprocess.CalledProcessError as e:
            print(f"❌ Git operation failed: {e}")

    def demonstrate_patch_application(self):
        """Demonstrate applying patches to branches"""
        print("\n🎯 === PATCH APPLICATION DEMONSTRATION ===")

        # Create a simple patch content
        patch_content = """diff --git a/README.md b/README.md
index 1234567..abcdefg 100644
--- a/README.md
+++ b/README.md
@@ -7,7 +7,14 @@ A simple calculator application for demonstrating Logan's patch tools.
 - Input validation
 - Configurable settings

+## Recent Enhancements
+- Added comprehensive error handling
+- Implemented input validation
+- Added expression parsing
+- Comprehensive test coverage
+
 ## Usage
 ```bash
 python3 app.py
 ```
+For testing: `python3 test_calculator.py`

@@ -15,4 +22,4 @@ python3 app.py
 ```

 ## Version
-1.0.0
+1.1.0"""

        print("📝 Applying documentation update patch...")
        print("Logan Tool Call:")
        print("""
apply_patch(
    patch_content="<patch content shown above>",
    target_branch="main",
    create_branch=True,
    branch_name="docs/update-readme-v11"
)
        """)

        # Simulate patch application
        self.simulate_logan_patch_application(patch_content)

    def simulate_logan_patch_application(self, patch_content):
        """Simulate Logan's patch application"""
        import tempfile

        try:
            # Create temporary patch file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".patch", delete=False
            ) as f:
                f.write(patch_content)
                patch_file = f.name

            # Create new branch
            subprocess.run(
                ["git", "checkout", "-b", "docs/update-readme-v11"], capture_output=True
            )

            # Apply patch
            result = subprocess.run(
                ["git", "apply", patch_file], capture_output=True, text=True
            )

            if result.returncode == 0:
                # Check status
                status_result = subprocess.run(
                    ["git", "status", "--porcelain"], capture_output=True, text=True
                )

                print(f"""
✅ Patch Application Result:

🎉 Patch applied successfully!
🌿 Applied to branch: docs/update-readme-v11
📂 Original branch: main

📝 Modified files:
   M  README.md

💡 Next steps:
   1. Review changes with: git diff
   2. Stage changes with: git add .
   3. Commit changes with: git commit -m 'Update README with v1.1 enhancements'
                """)

                # Show the actual changes
                diff_result = subprocess.run(
                    ["git", "diff", "README.md"], capture_output=True, text=True
                )
                if diff_result.returncode == 0:
                    print("\n📋 Applied changes:")
                    print("```diff")
                    print(diff_result.stdout)
                    print("```")

            else:
                print(f"❌ Patch application failed: {result.stderr}")

            # Cleanup
            os.unlink(patch_file)

        except Exception as e:
            print(f"❌ Error during patch application: {e}")

    def demonstrate_complete_workflow(self):
        """Demonstrate a complete patch management workflow"""
        print("\n🎯 === COMPLETE WORKFLOW DEMONSTRATION ===")

        print("""
🔄 Complete Patch Workflow Example:

1. Developer identifies need for security improvements
2. Creates patches for different aspects of security
3. Tests patches on separate branches
4. Cherry-picks successful patches to release branches
5. Applies hotfixes to production branches
        """)

        # Step 1: Create security improvement patch
        print("\n📋 Step 1: Create security patch")

        # Add security improvements
        with open("security.py", "w") as f:
            f.write("""#!/usr/bin/env python3
\"\"\"
Security utilities for the calculator application
\"\"\"
import hashlib
import hmac
import secrets

def hash_password(password, salt=None):
    \"\"\"Hash password with salt\"\"\"
    if salt is None:
        salt = secrets.token_hex(32)

    pwdhash = hashlib.pbkdf2_hmac('sha256',
                                  password.encode('utf-8'),
                                  salt.encode('utf-8'),
                                  100000)
    return pwdhash.hex(), salt

def verify_password(password, hash_value, salt):
    \"\"\"Verify password against hash\"\"\"
    return hmac.compare_digest(
        hash_password(password, salt)[0],
        hash_value
    )

def sanitize_input(user_input):
    \"\"\"Basic input sanitization\"\"\"
    if not isinstance(user_input, str):
        return str(user_input)

    # Remove potentially dangerous characters
    dangerous_chars = ['<', '>', '&', '"', "'", ';', '|', '`']
    sanitized = user_input
    for char in dangerous_chars:
        sanitized = sanitized.replace(char, '')

    return sanitized.strip()

def rate_limit_check(user_id, max_requests=10, window=60):
    \"\"\"Simple rate limiting check\"\"\"
    # In real implementation, this would use Redis or similar
    # For demo, we'll just return True
    return True
""")

        # Create the security patch
        subprocess.run(["git", "add", "security.py"], capture_output=True)
        subprocess.run(
            ["git", "checkout", "-b", "security/add-utils"], capture_output=True
        )
        subprocess.run(
            [
                "git",
                "commit",
                "-m",
                "Add security utilities for input sanitization and password handling",
            ],
            capture_output=True,
        )

        # Step 2: Create logging patch
        print("📋 Step 2: Create logging patch")
        subprocess.run(["git", "checkout", "main"], capture_output=True)

        with open("logging_config.py", "w") as f:
            f.write("""#!/usr/bin/env python3
\"\"\"
Logging configuration for the calculator application
\"\"\"
import logging
import logging.handlers
from datetime import datetime

def setup_logging(log_level=logging.INFO, log_file='app.log'):
    \"\"\"Configure application logging\"\"\"

    # Create logger
    logger = logging.getLogger('calculator')
    logger.setLevel(log_level)

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=1024*1024, backupCount=5
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

def log_security_event(event_type, details, user_id=None):
    \"\"\"Log security-related events\"\"\"
    logger = logging.getLogger('calculator.security')
    logger.warning(f"Security Event: {event_type} - {details} - User: {user_id}")

def log_calculation(operation, inputs, result, user_id=None):
    \"\"\"Log calculation operations\"\"\"
    logger = logging.getLogger('calculator.operations')
    logger.info(f"Calculation: {operation}({inputs}) = {result} - User: {user_id}")
""")

        subprocess.run(["git", "add", "logging_config.py"], capture_output=True)
        subprocess.run(
            ["git", "checkout", "-b", "feature/logging-system"], capture_output=True
        )
        subprocess.run(
            [
                "git",
                "commit",
                "-m",
                "Add comprehensive logging system with rotation and security event logging",
            ],
            capture_output=True,
        )

        # Step 3: Show cherry-picking workflow
        print("📋 Step 3: Cherry-picking to release branch")
        subprocess.run(["git", "checkout", "main"], capture_output=True)
        subprocess.run(["git", "checkout", "-b", "release/v1.2"], capture_output=True)

        print("""
🍒 Cherry-picking workflow:

# Get commit hashes from feature branches
git log --oneline feature/logging-system -1
git log --oneline security/add-utils -1

# Cherry-pick specific commits to release branch
git cherry-pick <security-commit-hash>
git cherry-pick <logging-commit-hash>

# Result: Clean release branch with only desired features
        """)

        # Switch back to main for cleanup
        subprocess.run(["git", "checkout", "main"], capture_output=True)

        print("\n✅ Complete workflow demonstration finished!")

    def show_git_status(self):
        """Show final repository status"""
        print("\n📊 === FINAL REPOSITORY STATUS ===")

        # Show branches
        result = subprocess.run(["git", "branch", "-a"], capture_output=True, text=True)
        print(f"🌿 Branches created:\n{result.stdout}")

        # Show recent commits
        result = subprocess.run(
            ["git", "log", "--oneline", "--all", "--graph", "-10"],
            capture_output=True,
            text=True,
        )
        print(f"📝 Recent commits:\n{result.stdout}")

        print(f"\n🗂️  Demo repository location: {self.test_repo}")
        print(
            "💡 You can explore the repository manually to see all the patches and branches"
        )

    def cleanup(self):
        """Cleanup and return to original directory"""
        os.chdir(self.original_dir)

    def run_demo(self, demo_type="all"):
        """Run the specified demonstration"""
        try:
            self.setup_demo_repo()

            if demo_type in ["create", "all"]:
                self.demonstrate_patch_creation()

            if demo_type in ["apply", "all"]:
                self.demonstrate_patch_application()

            if demo_type in ["workflow", "all"]:
                self.demonstrate_complete_workflow()

            self.show_git_status()

        finally:
            self.cleanup()


def main():
    """Main demonstration function"""
    parser = argparse.ArgumentParser(
        description="Demonstrate Logan's patch creation and application tools"
    )
    parser.add_argument(
        "--demo-type",
        choices=["create", "apply", "workflow", "all"],
        default="all",
        help="Type of demonstration to run",
    )

    args = parser.parse_args()

    print("🚀 Logan Patch Tools Demonstration")
    print("=" * 50)
    print("""
This demonstration shows how Logan's patch tools can be used for:
- Creating patches on separate branches
- Applying patches to target branches
- Managing complex patch workflows
- Cherry-picking specific changes
- Maintaining clean git history
    """)

    demo = PatchDemo()
    demo.run_demo(args.demo_type)

    print("\n🎉 Demonstration complete!")
    print("📚 For more information, see PATCH_TOOLS_GUIDE.md")


if __name__ == "__main__":
    main()
