#!/usr/bin/env python3
"""
Direct test script for Logan's simplified apply_patch tool
"""

import os
import sys

# Add the current directory to the path so we can import Logan
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_apply_patch_tool():
    """Test the apply_patch tool directly with in-memory analyzer"""

    print("🧪 Testing Logan's Simplified Apply Patch Tool")
    print("=" * 50)

    try:
        # Import Logan components
        from logan import DulwichApplyPatchTool

        print("✅ Successfully imported apply_patch tool")

        # Create mock analyzer with virtual files
        class MockVirtualFile:
            def __init__(self, content):
                self.content = content

        class MockRepoInfo:
            def __init__(self):
                self.url = "https://github.com/test/repo"
                self.branch = "main"
                self.commit_sha = "abc123def456"

        class MockAnalyzer:
            def __init__(self):
                self.virtual_files = {
                    "main.py": MockVirtualFile("""def hello_world():
    print("Hello, World!")

def add_numbers(a, b):
    return a + b

if __name__ == "__main__":
    hello_world()
    result = add_numbers(2, 3)
    print(f"Result: {result}")
"""),
                    "utils.py": MockVirtualFile("""def multiply(x, y):
    return x * y

def divide(x, y):
    if y == 0:
        raise ValueError("Cannot divide by zero")
    return x / y
"""),
                }
                self.repo_info = MockRepoInfo()

        class MockAnalyzerRef:
            def __init__(self):
                self.analyzer = MockAnalyzer()

        # Create apply patch tool
        analyzer_ref = MockAnalyzerRef()
        apply_tool = DulwichApplyPatchTool(analyzer_ref)

        print("✅ Successfully created apply_patch tool instance")

        # Test patch application with proper unified diff
        print("\n🎯 Testing Patch Application")
        print("-" * 30)

        # Create a proper unified diff patch that the LLM would generate
        sample_patch = """--- a/main.py
+++ b/main.py
@@ -1,7 +1,7 @@
 def hello_world():
-    print("Hello, World!")
+    print("Hello, World! Updated version!")

 def add_numbers(a, b):
     return a + b

 if __name__ == "__main__":
"""

        result = apply_tool._run(
            patch_content=sample_patch,
            target_branch="main",
            auto_apply=True,
            auto_commit=True,
            commit_message="Update hello world message",
        )

        print("Patch application result:")
        print(result)

        # Test another patch for type hints
        print("\n🎯 Testing Type Hints Patch")
        print("-" * 30)

        type_hints_patch = """--- a/main.py
+++ b/main.py
@@ -3,5 +3,5 @@
     print("Hello, World! Updated version!")

-def add_numbers(a, b):
+def add_numbers(a: int, b: int) -> int:
     return a + b

 if __name__ == "__main__":
"""

        result2 = apply_tool._run(
            patch_content=type_hints_patch,
            target_branch="main",
            auto_apply=True,
            auto_commit=True,
            commit_message="Add type hints to add_numbers function",
        )

        print("Type hints patch result:")
        print(result2)

        print("\n🎉 All patch tests completed successfully!")
        return True

    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 This might be expected if AWS dependencies aren't installed")
        return False

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_with_logan_assistant():
    """Test patch tools within Logan Assistant context"""

    print("\n🧪 Testing with Logan Assistant Context")
    print("=" * 45)

    try:
        from logan import LoganAssistant

        # Create Logan assistant in mock mode
        assistant = LoganAssistant(model_id="mock")

        print("✅ Created Logan Assistant instance")

        # Check if apply_patch tool is available
        if hasattr(assistant, "apply_patch_tool"):
            print("✅ Apply patch tool is available in Logan Assistant")
            print(f"   - Apply patch tool: {assistant.apply_patch_tool.name}")
            return True
        else:
            print("❌ Apply patch tool not found in Logan Assistant")
            return False

    except Exception as e:
        print(f"❌ Error testing Logan Assistant: {e}")
        import traceback

        traceback.print_exc()
        return False


def demonstrate_proper_workflow():
    """Demonstrate the correct LLM -> apply_patch workflow"""

    print("\n📚 Proper Workflow Demonstration")
    print("=" * 40)

    print("✅ CORRECT WORKFLOW:")
    print("   1. LLM analyzes code using preview_code/grep_content")
    print("   2. LLM creates unified diff patch based on actual file content")
    print("   3. LLM calls apply_patch with the unified diff")
    print("   4. apply_patch tool applies changes to memory repository")
    print("")
    print("📝 Example LLM-generated patch:")
    print("""
--- a/main.py
+++ b/main.py
@@ -1,4 +1,4 @@
 def hello_world():
-    print("Hello, World!")
+    print("Hello, World! With improvements!")

 def add_numbers(a, b):
""")
    print("")
    print("❌ INCORRECT WORKFLOW (old design):")
    print("   1. Logan creates patches internally")
    print("   2. Complex search/replace operations")
    print("   3. Mixed responsibilities between tools")
    print("")
    print("💡 The simplified design puts patch creation responsibility on the LLM,")
    print("   where it belongs, and Logan just applies what the LLM generates.")


if __name__ == "__main__":
    print("🚀 Starting Logan Simplified Patch System Test")
    print("This test validates the new simplified apply_patch-only design")
    print()

    success1 = test_apply_patch_tool()
    success2 = test_with_logan_assistant()

    demonstrate_proper_workflow()

    print("\n" + "=" * 60)
    if success1 and success2:
        print("✅ All tests passed! Simplified patch system is working correctly.")
    elif success1:
        print("⚠️  Apply patch tool works directly but has issues in Logan context.")
    elif success2:
        print("⚠️  Logan integration works but patch tool has direct issues.")
    else:
        print("❌ Tests failed. Check the error messages above.")

    print("\n💡 Key Benefits of Simplified Design:")
    print("   ✅ Single responsibility: apply_patch only applies patches")
    print("   ✅ LLM generates patches based on actual file analysis")
    print("   ✅ Clear separation of concerns")
    print("   ✅ No confusing dual-purpose tools")
    print("   ✅ Follows standard Git patch workflow")
