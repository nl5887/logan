#!/usr/bin/env python3
"""
Branch Naming Example

This example demonstrates the new timestamp-based branch naming system
that creates unique, sortable branch names for patches.
"""

from datetime import datetime


def demonstrate_branch_naming():
    """Show how the new branch naming system works"""
    print("🌿 Branch Naming System Demonstration")
    print("=" * 50)

    # Show current timestamp format
    timestamp = datetime.now().strftime("%Y%m%d%H%M")
    print(f"Current timestamp: {timestamp}")

    # Example branch names that would be generated
    branch_examples = [
        f"patch_apply_{timestamp}",
        f"fix/error-handling-{timestamp}",
        f"feature/validation-system-{timestamp}",
        f"hotfix/critical-bug-{timestamp}",
    ]

    print(f"\n📋 Example branch names:")
    for branch in branch_examples:
        print(f"   🌿 {branch}")

    # Show the format breakdown
    print(f"\n📊 Timestamp Format: YYYYMMDDHHMM")
    now = datetime.now()
    print(f"   Year:   {now.strftime('%Y')} (4 digits)")
    print(f"   Month:  {now.strftime('%m')} (2 digits)")
    print(f"   Day:    {now.strftime('%d')} (2 digits)")
    print(f"   Hour:   {now.strftime('%H')} (24-hour, 2 digits)")
    print(f"   Minute: {now.strftime('%M')} (2 digits)")
    print(f"   Total:  {now.strftime('%Y%m%d%H%M')} (12 characters)")


def show_practical_benefits():
    """Show benefits of timestamp-based branch naming"""
    print(f"\n💡 Benefits of Timestamp-Based Branch Names")
    print("=" * 50)

    benefits = [
        {
            "benefit": "Unique Names",
            "description": "No conflicts - each patch gets a unique branch name",
            "example": "patch_apply_202410281023 vs patch_apply_202410281024",
        },
        {
            "benefit": "Chronological Sorting",
            "description": "Branches sort naturally by creation time",
            "example": "git branch --sort=-committerdate shows newest first",
        },
        {
            "benefit": "Easy Cleanup",
            "description": "Identify old branches for cleanup based on timestamp",
            "example": "Delete branches older than 202410280000",
        },
        {
            "benefit": "Audit Trail",
            "description": "Know exactly when a patch was applied",
            "example": "202410281023 = October 28, 2024 at 10:23 AM",
        },
        {
            "benefit": "No Manual Naming",
            "description": "Automatic generation - no need to think of names",
            "example": "Logan generates: fix/update-alerts-202410281023",
        },
    ]

    for i, benefit in enumerate(benefits, 1):
        print(f"{i}. 🎯 {benefit['benefit']}")
        print(f"   └─ {benefit['description']}")
        print(f"   📝 Example: {benefit['example']}")
        print()


def show_logan_integration():
    """Show how this integrates with Logan patches"""
    print(f"🔧 Logan Integration Examples")
    print("=" * 40)

    print("""
AUTOMATIC BRANCH NAMING:
When no branch_name is provided, Logan automatically generates one:

{
    "search_replace": [{"file": "main.py", "search": "log.error", "replace": "logger.error"}],
    "auto_apply": true,
    "auto_commit": true
}

Result: Branch "patch_apply_202410281023" created automatically

CUSTOM BRANCH WITH TIMESTAMP:
You can provide a custom prefix, and Logan adds the timestamp:

{
    "search_replace": [...],
    "branch_name": "fix/error-handling-202410281023",
    "auto_apply": true
}

Result: Branch "fix/error-handling-202410281023" created

MULTIPLE PATCHES SAME MINUTE:
If multiple patches are applied in the same minute:
- 10:23:15 → patch_apply_202410281023
- 10:23:47 → patch_apply_202410281023_2 (with suffix)

This prevents conflicts while maintaining readability.
    """)


def show_git_operations():
    """Show common git operations with timestamped branches"""
    print(f"\n📚 Git Operations with Timestamped Branches")
    print("=" * 50)

    operations = [
        {
            "operation": "List recent branches",
            "command": "git branch --sort=-committerdate | head -10",
            "description": "Shows newest branches first based on timestamp",
        },
        {
            "operation": "Find branches from specific day",
            "command": "git branch | grep 20241028",
            "description": "Find all branches created on October 28, 2024",
        },
        {
            "operation": "Clean up old branches",
            "command": "git branch | grep -E 'patch_apply_202410(0[1-9]|1[0-9]|2[0-7])' | xargs git branch -D",
            "description": "Delete patch branches older than October 28",
        },
        {
            "operation": "Create PR with meaningful title",
            "command": "gh pr create --title 'Fix error handling (202410281023)'",
            "description": "Include timestamp in PR for reference",
        },
        {
            "operation": "Find branch by time range",
            "command": "git branch | grep -E 'patch_apply_202410281[0-1][0-9][0-9]'",
            "description": "Find branches created between 10:00-11:59 AM",
        },
    ]

    for op in operations:
        print(f"🔧 {op['operation']}:")
        print(f"   $ {op['command']}")
        print(f"   └─ {op['description']}")
        print()


if __name__ == "__main__":
    # Run all demonstrations
    demonstrate_branch_naming()
    show_practical_benefits()
    show_logan_integration()
    show_git_operations()

    print(f"🎉 Branch naming demonstration complete!")
    print(f"Format: YYYYMMDDHHMM provides unique, sortable, trackable branches.")
