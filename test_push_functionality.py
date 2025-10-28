#!/usr/bin/env python3
"""
Test script to verify Logan's push functionality is working correctly
Tests both create_patch and apply_patch tools with real push operations
"""

import os
import sys
import asyncio
import tempfile
import subprocess
from datetime import datetime


def setup_test_environment():
    """Set up test environment with repository configuration"""
    print("🔧 Setting up test environment...")

    # Set required environment variables for Logan
    test_repo_url = os.getenv("TEST_REPOSITORY_URL", "")
    if not test_repo_url:
        print("⚠️  TEST_REPOSITORY_URL not set. Using current directory.")
        test_repo_url = "."

    os.environ["REPOSITORY_URL"] = test_repo_url
    os.environ["REPOSITORY_BRANCH"] = "main"

    # Set authentication if available
    auth_token = os.getenv("TEST_REPOSITORY_AUTH", "")
    if auth_token:
        os.environ["REPOSITORY_AUTH"] = auth_token
        print("✅ Authentication configured")
    else:
        print("⚠️  No authentication configured (TEST_REPOSITORY_AUTH)")

    print(f"📂 Repository URL: {test_repo_url}")
    return test_repo_url


def create_test_file():
    """Create a simple test file to be patched"""
    test_content = f"""#!/usr/bin/env python3
# Test file created at {datetime.now()}
# This file is used to test Logan's push functionality

def test_function():
    print("This is a test function")
    return "success"

def another_function():
    print("Another test function")
    return "also success"

if __name__ == "__main__":
    print("Running test file...")
    result1 = test_function()
    result2 = another_function()
    print(f"Results: {{result1}}, {{result2}}")
"""

    filename = "test_push_file.py"
    with open(filename, "w") as f:
        f.write(test_content)

    print(f"📄 Created test file: {filename}")
    return filename


async def test_create_patch_with_push():
    """Test create_patch tool with real push"""
    print("\n🧪 Testing create_patch with push...")

    try:
        from logan import LoganAssistant

        # Create Logan instance
        logan = LoganAssistant(max_iterations=1)

        # Create test file
        test_file = create_test_file()

        # Test create_patch with push
        branch_name = f"test-push-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        result = logan.create_patch_tool._run(
            description="Test push functionality",
            files=[test_file],
            branch_name=branch_name,
            commit_message="Test commit for push functionality verification",
            auto_commit=True,
            auto_push=True,
            real_push=True,
        )

        print("📋 Create Patch Result:")
        print(result)

        # Check if push was mentioned in the result
        if "Successfully pushed to:" in result:
            print("✅ Push appears to have succeeded!")
            return True
        elif "Real push failed:" in result:
            print("❌ Push failed - check logs above")
            return False
        elif "Ready to push to:" in result and "real_push=True" not in result:
            print("⚠️  Push was simulated, not real")
            return False
        else:
            print("❓ Push status unclear from result")
            return False

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_apply_patch_with_push():
    """Test apply_patch tool with real push"""
    print("\n🧪 Testing apply_patch with push...")

    # Create a simple patch content
    patch_content = """diff --git a/test_apply_file.py b/test_apply_file.py
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/test_apply_file.py
@@ -0,0 +1,5 @@
+#!/usr/bin/env python3
+# Applied patch test file
+
+def applied_function():
+    return "This function was added via patch"
"""

    try:
        from logan import LoganAssistant

        # Create Logan instance
        logan = LoganAssistant(max_iterations=1)

        branch_name = f"apply-test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        result = logan.apply_patch_tool._run(
            patch_content=patch_content,
            create_branch=True,
            branch_name=branch_name,
            auto_apply=True,
            auto_push=True,
            commit_message="Test patch application with push",
            real_push=True,
        )

        print("📋 Apply Patch Result:")
        print(result)

        # Check if push was mentioned in the result
        if "Successfully pushed patch to:" in result:
            print("✅ Patch push appears to have succeeded!")
            return True
        elif "Real push failed:" in result:
            print("❌ Patch push failed - check logs above")
            return False
        else:
            print("❓ Patch push status unclear from result")
            return False

    except Exception as e:
        print(f"❌ Patch test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False


def check_git_status():
    """Check if we're in a git repository"""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            print("✅ Git repository detected")
            return True
        else:
            print("❌ Not in a git repository")
            return False
    except Exception as e:
        print(f"❌ Git check failed: {e}")
        return False


async def run_push_tests():
    """Run all push functionality tests"""
    print("🚀 Logan Push Functionality Test Suite")
    print("=" * 50)

    # Setup
    repo_url = setup_test_environment()

    # Check git status
    if not check_git_status():
        print("⚠️  Not in a git repository - push tests may not work")

    # Check dependencies
    try:
        from logan import LoganAssistant

        print("✅ Logan imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import Logan: {e}")
        return False

    try:
        import dulwich

        print("✅ Dulwich available for git operations")
    except ImportError:
        print("❌ Dulwich not available - push functionality won't work")
        return False

    # Run tests
    results = []

    print("\n" + "=" * 30)
    print("TEST 1: Create Patch with Push")
    print("=" * 30)
    create_result = await test_create_patch_with_push()
    results.append(("Create Patch with Push", create_result))

    print("\n" + "=" * 30)
    print("TEST 2: Apply Patch with Push")
    print("=" * 30)
    apply_result = await test_apply_patch_with_push()
    results.append(("Apply Patch with Push", apply_result))

    # Summary
    print("\n" + "=" * 50)
    print("🎯 TEST RESULTS SUMMARY")
    print("=" * 50)

    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
        if result:
            passed += 1

    print(f"\n📊 Overall: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All push functionality tests PASSED!")
        print("\n💡 Logan's push functionality is working correctly!")
        print("   • Commits are created in memory")
        print("   • Branches are created automatically")
        print("   • Real pushes to remote repository work")
        return True
    else:
        print("⚠️  Some tests failed - push functionality needs attention")
        print("\n🔧 Troubleshooting tips:")
        print("   • Check repository authentication (TEST_REPOSITORY_AUTH)")
        print("   • Verify repository URL (TEST_REPOSITORY_URL)")
        print("   • Ensure git push permissions")
        print("   • Check network connectivity")
        return False


def main():
    """Main entry point"""
    try:
        result = asyncio.run(run_push_tests())
        exit_code = 0 if result else 1
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
