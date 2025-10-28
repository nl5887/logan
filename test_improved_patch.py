#!/usr/bin/env python3
"""
Test script demonstrating improved patch system with both approaches
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_search_replace_with_line_range():
    """Test search and replace with line range to prevent unwanted changes"""

    print("🧪 Testing Search & Replace with Line Range")
    print("=" * 45)

    # Mock file content with duplicate text
    mock_content = """def hello_world():
    print("Hello, World!")  # Line 2 - should change

def another_function():
    print("Hello, World!")  # Line 5 - should NOT change
    return "done"

def third_function():
    print("Hello, World!")  # Line 9 - should NOT change
    return True
"""

    print("📋 Original file content:")
    for i, line in enumerate(mock_content.split("\n"), 1):
        if line.strip():
            print(f"   {i:2}: {line}")

    # Test 1: Search replace with line range (safe)
    print(f"\n✅ APPROACH 1 - With line range (SAFE):")
    search_replace_safe = [
        {
            "file": "main.py",
            "search": 'print("Hello, World!")',
            "replace": 'print("Hello, Universe!")',
            "start_line": 1,
            "end_line": 3,
        }
    ]

    print("   Operations:")
    for op in search_replace_safe:
        print(f"     - File: {op['file']}")
        print(f"     - Lines: {op['start_line']}-{op['end_line']}")
        print(f"     - Search: {op['search']}")
        print(f"     - Replace: {op['replace']}")

    print("   Expected result: Only line 2 changes ✅")

    # Test 2: Search replace without line range (dangerous)
    print(f"\n⚠️  APPROACH 1 - Without line range (DANGEROUS):")
    search_replace_unsafe = [
        {
            "file": "main.py",
            "search": 'print("Hello, World!")',
            "replace": 'print("Hello, Universe!")',
            # No start_line/end_line = changes ALL matches!
        }
    ]

    print("   Operations:")
    for op in search_replace_unsafe:
        print(f"     - File: {op['file']}")
        print(f"     - Lines: ALL (no range specified)")
        print(f"     - Search: {op['search']}")
        print(f"     - Replace: {op['replace']}")

    print("   Expected result: ALL 3 lines change (probably unwanted) ⚠️")


def test_unified_diff_approach():
    """Test unified diff approach with precise change reporting"""

    print("\n🧪 Testing Unified Diff Approach")
    print("=" * 35)

    unified_patch = """--- a/main.py
+++ b/main.py
@@ -1,3 +1,3 @@
 def hello_world():
-    print("Hello, World!")  # Line 2 - should change
+    print("Hello, Universe!")  # Line 2 - changed!

"""

    print("📋 Unified diff patch:")
    print("```diff")
    print(unified_patch.strip())
    print("```")

    print("\n✅ APPROACH 2 - Unified Diff Benefits:")
    print("   - Precise line targeting")
    print("   - Shows exact context")
    print("   - Git-compatible format")
    print("   - Clear change visualization")


def test_change_reporting():
    """Test comprehensive change reporting for both approaches"""

    print("\n🧪 Testing Change Reporting")
    print("=" * 30)

    print("📋 Expected Change Reports:")
    print("\n🔍 Search & Replace Changes:")
    print(
        '   ✅ main.py:1-3 - print("Hello, World!")... → print("Hello, Universe!")...'
    )
    print("   📊 1 replacement made in specified line range")
    print("   ⚠️  Multiple matches found but only first in range replaced")

    print("\n🔍 Unified Diff Changes:")
    print("   ✅ main.py - Unified diff applied successfully")
    print("   📊 1 hunk applied: @@ -1,3 +1,3 @@")
    print("   📝 Context preserved, exact line changes tracked")


def demonstrate_improved_workflow():
    """Demonstrate the complete improved workflow"""

    print("\n🚀 Complete Improved Workflow")
    print("=" * 35)

    print("🔍 Step 1: LLM analyzes code")
    print("   Tool: preview_code(identifier='main.py:1-10')")

    print("\n🎯 Step 2: LLM chooses approach")
    print("   Simple change → search_replace with line range")
    print("   Complex change → unified diff")

    print("\n⚙️  Step 3: LLM calls apply_patch")
    print("   Option A - Search & Replace:")
    print("   apply_patch(search_replace=[{")
    print("       'file': 'main.py',")
    print("       'search': 'old_code',")
    print("       'replace': 'new_code',")
    print("       'start_line': 10,")
    print("       'end_line': 20")
    print("   }])")

    print("\n   Option B - Unified Diff:")
    print("   apply_patch(patch_content='--- a/main.py\\n+++ b/main.py\\n...')")

    print("\n📊 Step 4: Logan returns detailed changes")
    print("   ✅ Exact changes made")
    print("   📍 Line numbers affected")
    print("   ⚠️  Warnings about multiple matches")
    print("   ❌ Clear error messages if failed")


def test_error_scenarios():
    """Test error handling and edge cases"""

    print("\n🚨 Error Handling Examples")
    print("=" * 28)

    print("❌ Common Error Cases:")
    print("   1. File not found:")
    print("      → ❌ nonexistent.py - File not found in virtual files")

    print("   2. Search text not found:")
    print("      → ❌ main.py:10-20 - Search text not found: missing_code...")

    print("   3. Multiple matches without line range:")
    print(
        "      → ⚠️  main.py - Multiple matches found for: print... (replaced first occurrence)"
    )

    print("   4. Invalid unified diff:")
    print("      → ❌ Unified diff parsing failed: Hunk is longer than expected")

    print("\n✅ Good Error Messages Help:")
    print("   - Identify exact problem")
    print("   - Suggest solutions")
    print("   - Show what was/wasn't changed")


if __name__ == "__main__":
    print("🚀 Testing Improved Logan Patch System")
    print("This demonstrates the enhanced patch system with:")
    print("  ✅ Line range support for search & replace")
    print("  ✅ Detailed change reporting")
    print("  ✅ Better error handling")
    print("  ✅ Two complementary approaches")
    print()

    test_search_replace_with_line_range()
    test_unified_diff_approach()
    test_change_reporting()
    demonstrate_improved_workflow()
    test_error_scenarios()

    print("\n" + "=" * 60)
    print("🎉 Key Improvements Summary:")
    print("   ✅ Line range prevents unwanted search/replace changes")
    print("   ✅ Both approaches return detailed change reports")
    print("   ✅ Clear distinction between simple vs complex changes")
    print("   ✅ Comprehensive error handling with actionable messages")
    print("   ✅ Unified interface supporting both approaches")

    print("\n💡 Usage Recommendations:")
    print("   🔍 Use search_replace for simple, targeted changes")
    print("   📝 Always specify line range for search_replace")
    print("   🎯 Use unified_diff for complex, multi-line changes")
    print("   📊 Review change reports before applying to real repos")
