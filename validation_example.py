#!/usr/bin/env python3
"""
Example demonstrating the post-patch validation system

This file shows how the validation system works with different types of code issues
and how it integrates with Logan's apply_patch tool.
"""

import os
import sys
from validation_system import ValidationEngine, validate_python_file


def example_valid_code():
    """Example of code that passes all validation checks"""

    def calculate_sum(numbers: list) -> int:
        """Calculate the sum of a list of numbers."""
        if not isinstance(numbers, list):
            raise TypeError("Input must be a list")

        total = 0
        for num in numbers:
            if isinstance(num, (int, float)):
                total += num
        return int(total)

    # This code should pass:
    # - Syntax check: ✅ Valid Python syntax
    # - Compile check: ✅ Compiles without errors
    # - Flake8 check: ✅ No style issues
    # - MyPy check: ✅ Type hints are correct

    result = calculate_sum([1, 2, 3, 4, 5])
    print(f"Sum: {result}")


def example_syntax_error():
    """Example of code with syntax errors (for demonstration only)"""
    # This would fail syntax check:
    # def broken_function(
    #     print("Missing closing parenthesis")

    # This would also fail:
    # invalid syntax here @#$%
    pass


def example_linting_issues():
    """Example of code with linting issues"""
    # These would trigger flake8 warnings/errors:

    # E302: expected 2 blank lines, found 1
    def poorly_formatted_function():
        x = 1 + 2 + 3  # E225: missing whitespace around operator
        y = 4  # E221: multiple spaces before operator
        unused_var = 5  # F841: local variable assigned but never used
        return x

    # W391: blank line at end of file (if this was at the end)


def example_type_checking_issues():
    """Example of code with type checking issues"""

    def function_with_type_issues(name: str, age: int) -> str:
        # MyPy would catch these issues:
        result = name + age  # Error: unsupported operand types
        return (
            result.upper().lower()
        )  # This would work, but mypy might complain about chaining


def demonstration_main():
    """Demonstrate the validation system"""
    print("🔍 Validation System Demonstration")
    print("=" * 50)

    # Create example files to validate
    examples = {
        "valid_example.py": '''
def greet(name: str) -> str:
    """Return a greeting message."""
    return f"Hello, {name}!"

if __name__ == "__main__":
    message = greet("World")
    print(message)
''',
        "syntax_error_example.py": """
def broken_function(
    print("This has a syntax error - missing closing parenthesis")
""",
        "linting_issues_example.py": """
def bad_style():
    x=1+2
    y =   3
    unused = 4
    return x
""",
    }

    # Initialize validation engine
    engine = ValidationEngine()

    for filename, content in examples.items():
        print(f"\n📄 Validating: {filename}")
        print("-" * 30)

        # Validate with content (no need to write to disk)
        summary = engine.validate_file(filename, content)

        # Display formatted results
        formatted_results = engine.format_results(summary, verbose=True)
        print(formatted_results)

    print(f"\n✅ Validation demonstration complete!")


def test_integration_with_logan():
    """Show how this integrates with Logan's apply_patch tool"""
    print("\n🔧 Logan Integration Example")
    print("=" * 40)

    print("""
When using Logan's apply_patch tool, validation runs automatically:

EXAMPLE USAGE:
{
    "search_replace": [
        {
            "file": "main.py",
            "search": "log.error(",
            "replace": "logger.error("
        }
    ],
    "auto_apply": true,
    "auto_commit": true,
    "validate_after_patch": true,
    "validation_level": "required"
}

VALIDATION LEVELS:
- "required": Only syntax and compilation checks (fast, essential)
- "recommended": Includes linting with flake8 (catches style issues)
- "all": Includes type checking with mypy and test execution

SAMPLE OUTPUT:
🔍 Validation Results:
   ✅ Validated 1 files: 1 passed, 0 failed
   📄 main.py: ✅
      ✅ Python syntax is valid
      ✅ Python code compiles successfully
      ✅ No linting issues found

This ensures that patches don't break the code!
    """)


if __name__ == "__main__":
    # Run the demonstration
    demonstration_main()
    test_integration_with_logan()

    # Example of direct validation
    print(f"\n🎯 Direct Validation Example")
    print("-" * 30)

    # Validate this very file
    current_file = __file__
    if os.path.exists(current_file):
        summary = validate_python_file(current_file, required_only=False)
        engine = ValidationEngine()
        print(engine.format_results(summary, verbose=False))

    print(f"\n🎉 All examples completed!")
