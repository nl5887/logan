#!/usr/bin/env python3
"""
Line-Aware Validation Example

This example demonstrates how the validation system only reports errors and warnings
that are related to the lines that were actually changed by patches.
"""

import os
import sys
from validation_system import ValidationEngine


def demonstrate_line_aware_validation():
    """Show how validation filters results based on changed lines"""
    print("🎯 Line-Aware Validation Demonstration")
    print("=" * 50)

    # Example: A file with multiple issues, but we only changed some lines
    example_file_content = '''#!/usr/bin/env python3
"""Example file with various code quality issues"""

import os
import sys
import unused_import  # F401: unused import (line 6)

def good_function():
    """This function is well-written"""
    result = calculate_sum([1, 2, 3])
    return result

def problematic_function( ):  # E201: whitespace after '(' (line 13)
    x=1+2   # E225: missing whitespace around operator (line 14)
    y = 3    # E221: multiple spaces before operator (line 15)
    unused_var = 4  # F841: local variable assigned but never used (line 16)
    return x

def another_bad_function():
    # This function has issues too
    z   =   5   # E221: multiple spaces (line 21)
    return z

def calculate_sum(numbers):
    """Helper function - well written"""
    total = 0
    for num in numbers:
        total += num
    return total

# Main execution
if __name__ == "__main__":
    result1 = good_function()
    result2 = problematic_function()
    print(f"Results: {result1}, {result2}")
'''

    # Simulate different patch scenarios
    scenarios = [
        {
            "name": "Fix only problematic_function",
            "changed_lines": [13, 14, 15, 16],  # Lines we actually modified
            "description": "We fixed the spacing issues in problematic_function",
        },
        {
            "name": "Fix unused import",
            "changed_lines": [6],  # Only line 6 was changed
            "description": "We removed the unused import",
        },
        {
            "name": "Add new function at end",
            "changed_lines": [35, 36, 37],  # New lines added
            "description": "We added a new function at the end",
        },
        {
            "name": "No line filtering (show all)",
            "changed_lines": None,  # Show all issues
            "description": "Traditional validation - shows all issues in file",
        },
    ]

    engine = ValidationEngine()

    for scenario in scenarios:
        print(f"\n📋 Scenario: {scenario['name']}")
        print(f"   Description: {scenario['description']}")
        if scenario["changed_lines"]:
            print(f"   Changed lines: {scenario['changed_lines']}")
        print("-" * 40)

        # Run validation with line filtering
        summary = engine.validate_file(
            "example.py",
            example_file_content,
            required_only=False,  # Include linting to show filtering
            changed_lines=scenario["changed_lines"],
        )

        # Show results
        if summary.total_checks > 0:
            for result in summary.results:
                if result.check_type == "python_flake8":
                    print(f"   🔧 Flake8 Results:")
                    if result.errors:
                        print(f"      ❌ Errors ({len(result.errors)}):")
                        for error in result.errors:
                            print(f"         {error}")
                    if result.warnings:
                        print(f"      ⚠️  Warnings ({len(result.warnings)}):")
                        for warning in result.warnings:
                            print(f"         {warning}")
                    if not result.errors and not result.warnings:
                        print(f"      ✅ No relevant issues found")

                    # Show filtering info
                    if result.changed_lines_only:
                        total_issues = result.details.get("issues_count", 0)
                        filtered_issues = result.details.get("filtered_count", 0)
                        print(
                            f"      📊 Filtered: {filtered_issues}/{total_issues} issues shown (only changed lines)"
                        )
        else:
            print("   ℹ️  No applicable validation checks")


def demonstrate_practical_benefits():
    """Show practical benefits of line-aware validation"""
    print(f"\n💡 Practical Benefits of Line-Aware Validation")
    print("=" * 50)

    benefits = [
        {
            "benefit": "Reduced Noise",
            "description": "Only see errors related to your changes, not pre-existing issues",
        },
        {
            "benefit": "Faster Reviews",
            "description": "Focus on what actually changed instead of entire codebase issues",
        },
        {
            "benefit": "Incremental Improvement",
            "description": "Fix issues as you work on code, rather than overwhelming error lists",
        },
        {
            "benefit": "CI/CD Integration",
            "description": "Only fail builds for new issues, not legacy code problems",
        },
        {
            "benefit": "Developer Productivity",
            "description": "Developers focus on their changes, not unrelated technical debt",
        },
    ]

    for i, benefit in enumerate(benefits, 1):
        print(f"{i}. 🎯 {benefit['benefit']}")
        print(f"   └─ {benefit['description']}")


def show_integration_example():
    """Show how this integrates with Logan patches"""
    print(f"\n🔧 Logan Integration Example")
    print("=" * 40)

    print("""
BEFORE PATCH (with validation issues):
```python
def update_user(name, age):
    log.error("Error occurred")  # NameError: 'log' not defined
    user_data={"name":name,"age":age}  # E225: spacing issues
    return user_data
```

LOGAN PATCH:
{
    "search_replace": [
        {
            "file": "user.py",
            "search": "log.error",
            "replace": "logger.error",
            "start_line": 2,
            "end_line": 2
        }
    ],
    "auto_apply": true,
    "validate_after_patch": true,
    "validation_level": "recommended"
}

VALIDATION RESULTS:
🔍 Validation Results:
   ✅ Validated 1 files: 1 passed, 0 failed
   📄 user.py: ✅
      ✅ Python syntax is valid
      ✅ Python code compiles successfully
      ✅ No relevant linting issues found
      📊 Filtered: 0/1 issues shown (only changed lines)

Notice how the spacing issue on line 3 is NOT reported because:
- We only changed line 2 (log.error → logger.error)
- Line 3 spacing issue is pre-existing and unrelated to our change
- Validation focuses on line 2 ± tolerance (typically 2 lines)

This prevents "patch guilt" - being blamed for pre-existing issues!
    """)


if __name__ == "__main__":
    # Run all demonstrations
    demonstrate_line_aware_validation()
    demonstrate_practical_benefits()
    show_integration_example()

    print(f"\n🎉 Line-aware validation demonstration complete!")
    print(f"This ensures patches only get blamed for issues they actually introduce.")
