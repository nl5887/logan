#!/usr/bin/env python3
"""
Focused test for Logan's unidiff integration
Tests the patch functionality specifically using the unidiff library
"""

import sys
import os


def test_logan_unidiff_integration():
    """Test Logan's patch functionality with unidiff"""
    print("🧪 Testing Logan's Unidiff Integration")
    print("=" * 40)

    try:
        from logan import DulwichCreatePatchTool, DulwichApplyCodeChangesTool

        print("✅ Successfully imported Logan patch tools")

        # Create mock classes for testing
        class MockVirtualFile:
            def __init__(self, content):
                self.content = content

        class MockRepoInfo:
            def __init__(self):
                self.url = "https://github.com/test/repo.git"
                self.branch = "main"
                self.commit_sha = "abc123"

        class MockAnalyzer:
            def __init__(self):
                self.virtual_files = {
                    "test.py": MockVirtualFile("def hello():\n    pass\n"),
                    "main.py": MockVirtualFile(
                        "import sys\n\ndef main():\n    print('Hello World')\n"
                    ),
                }
                self.repo_info = MockRepoInfo()

        class MockAnalyzerRef:
            def __init__(self):
                self.analyzer = MockAnalyzer()

        # Test 1: Create patch tool
        print("\n🔧 Test 1: DulwichCreatePatchTool")
        analyzer_ref = MockAnalyzerRef()
        create_tool = DulwichCreatePatchTool(analyzer_ref)
        print("✅ Created DulwichCreatePatchTool successfully")

        # Test 2: Test patch application with unidiff
        print("\n🔧 Test 2: Apply patch with unidiff")
        apply_tool = DulwichApplyCodeChangesTool(analyzer_ref)
        print("✅ Created DulwichApplyCodeChangesTool successfully")

        # Test 3: Test the _apply_git_patch_to_virtual_files method
        print("\n🔧 Test 3: Apply git patch to virtual files")

        test_patch = """diff --git a/test.py b/test.py
index 1234567..abcdefg 100644
--- a/test.py
+++ b/test.py
@@ -1,2 +1,3 @@
 def hello():
+    print("Hello from unidiff!")
     pass
"""

        # Store original content for verification
        original_content = analyzer_ref.analyzer.virtual_files["test.py"].content
        print(f"📄 Original content: {repr(original_content)}")

        # Apply the patch
        result = create_tool._apply_git_patch_to_virtual_files(
            analyzer_ref.analyzer, ["test.py"], test_patch
        )

        print(f"📋 Patch result: {result}")

        # Check modified content
        modified_content = analyzer_ref.analyzer.virtual_files["test.py"].content
        print(f"📄 Modified content: {repr(modified_content)}")

        # Verify the patch was applied
        if "Hello from unidiff!" in modified_content:
            print("✅ Patch applied successfully - content was modified")
        else:
            print("❌ Patch application failed - content not modified")
            return False

        # Test 4: Test with multi-file patch
        print("\n🔧 Test 4: Multi-file patch")

        multi_file_patch = """diff --git a/test.py b/test.py
index 1111111..2222222 100644
--- a/test.py
+++ b/test.py
@@ -1,1 +1,2 @@
 def hello():
+    print("Modified test.py")
     pass
diff --git a/main.py b/main.py
index 3333333..4444444 100644
--- a/main.py
+++ b/main.py
@@ -1,3 +1,4 @@
 import sys
+import os

 def main():
"""

        # Reset test.py content
        analyzer_ref.analyzer.virtual_files[
            "test.py"
        ].content = "def hello():\n    pass\n"

        result = create_tool._apply_git_patch_to_virtual_files(
            analyzer_ref.analyzer, ["test.py", "main.py"], multi_file_patch
        )

        print(f"📋 Multi-file patch result: {result}")

        # Check both files were modified
        test_content = analyzer_ref.analyzer.virtual_files["test.py"].content
        main_content = analyzer_ref.analyzer.virtual_files["main.py"].content

        test_modified = "Modified test.py" in test_content
        main_modified = "import os" in main_content

        print(f"📄 test.py modified: {test_modified}")
        print(f"📄 main.py modified: {main_modified}")

        if test_modified and main_modified:
            print("✅ Multi-file patch applied successfully")
        else:
            print("❌ Multi-file patch failed")
            return False

        # Test 5: Error handling
        print("\n🔧 Test 5: Error handling")

        # Test with invalid patch
        invalid_patch = "This is not a valid patch"
        result = create_tool._apply_git_patch_to_virtual_files(
            analyzer_ref.analyzer, ["test.py"], invalid_patch
        )

        print(f"📋 Invalid patch result: {result}")
        if "No valid patches found" in result:
            print("✅ Invalid patch handled correctly")
        else:
            print("❌ Invalid patch handling failed")
            return False

        # Test 6: Empty patch
        print("\n🔧 Test 6: Empty patch handling")

        result = create_tool._apply_git_patch_to_virtual_files(
            analyzer_ref.analyzer, ["test.py"], ""
        )

        print(f"📋 Empty patch result: {result}")
        if "No patch content provided" in result:
            print("✅ Empty patch handled correctly")
        else:
            print("❌ Empty patch handling failed")
            return False

        print("\n🎉 All tests passed! Unidiff integration is working correctly.")
        return True

    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure Logan and unidiff are properly installed")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_unidiff_library_directly():
    """Test the unidiff library directly to ensure it's working"""
    print("\n🧪 Testing Unidiff Library Directly")
    print("=" * 35)

    try:
        from unidiff import PatchSet

        # Test basic patch parsing
        patch_text = """diff --git a/example.py b/example.py
index 1234567..abcdefg 100644
--- a/example.py
+++ b/example.py
@@ -1,3 +1,4 @@
 def example():
+    print("Added line")
     pass

"""

        patchset = PatchSet(patch_text)
        print(f"✅ Parsed patch with {len(patchset)} file(s)")

        for patched_file in patchset:
            print(f"📄 File: {patched_file.path}")
            print(f"📊 Hunks: {len(patched_file)}")

            for hunk in patched_file:
                print(
                    f"  📍 Hunk: -{hunk.source_start},{hunk.source_length} +{hunk.target_start},{hunk.target_length}"
                )

                for line in hunk:
                    if line.is_added:
                        print(f"    + {line.value.strip()}")
                    elif line.is_removed:
                        print(f"    - {line.value.strip()}")
                    elif line.is_context:
                        print(f"      {line.value.strip()}")

        print("✅ Unidiff library is working correctly")
        return True

    except ImportError as e:
        print(f"❌ Unidiff library not available: {e}")
        return False
    except Exception as e:
        print(f"❌ Error testing unidiff: {e}")
        return False


def main():
    """Main test runner"""
    print("🚀 Logan Unidiff Integration Test Suite")
    print("=" * 45)

    success_count = 0
    total_tests = 2

    # Test 1: Unidiff library directly
    if test_unidiff_library_directly():
        success_count += 1
        print("✅ Test 1 PASSED")
    else:
        print("❌ Test 1 FAILED")

    # Test 2: Logan integration
    if test_logan_unidiff_integration():
        success_count += 1
        print("✅ Test 2 PASSED")
    else:
        print("❌ Test 2 FAILED")

    print("\n" + "=" * 45)
    print(f"🎯 Results: {success_count}/{total_tests} tests passed")

    if success_count == total_tests:
        print("🎉 All tests passed! Logan unidiff integration is ready.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
