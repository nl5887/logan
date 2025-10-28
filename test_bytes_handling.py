#!/usr/bin/env python3
"""
Test script to verify bytes content handling in Logan's patch tools
This tests the fix for the "data must be str, not bytes" error
"""

import os
import sys
import tempfile
import subprocess
from pathlib import Path

# Add the current directory to the path so we can import Logan
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def setup_test_repository():
    """Create a test git repository"""
    test_dir = tempfile.mkdtemp(prefix="logan_bytes_test_")
    os.chdir(test_dir)

    # Initialize git repo
    subprocess.run(["git", "init"], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "config", "user.name", "Logan Bytes Test"], check=True)

    # Create initial file
    with open("main.py", "w") as f:
        f.write("""#!/usr/bin/env python3
import logging

logger = logging.getLogger(__name__)
error_count = 0

def process_data():
    global error_count
    try:
        # Some processing
        result = "success"
        logger.info("Processing completed")
        return result
    except Exception as e:
        error_count += 1
        logger.error(f"Processing failed: {e}")
        return None

if __name__ == "__main__":
    process_data()
""")

    # Initial commit
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], check=True)

    return test_dir


def test_bytes_content_handling():
    """Test patch tools with bytes content"""
    print("🧪 Testing Bytes Content Handling")
    print("-" * 35)

    try:
        from logan import DulwichCreatePatchTool

        # Create mock analyzer with BYTES content (simulating the real issue)
        class MockVirtualFile:
            def __init__(self, content):
                # Store content as BYTES to simulate the real issue
                if isinstance(content, str):
                    self.content = content.encode("utf-8")
                else:
                    self.content = content

        class MockRepoInfo:
            def __init__(self):
                self.url = "https://test.git"
                self.branch = "main"
                self.commit_sha = "abc123"

        class MockAnalyzer:
            def __init__(self):
                # Create virtual file with BYTES content
                self.virtual_files = {
                    "main.py": MockVirtualFile("""#!/usr/bin/env python3
import logging

logger = logging.getLogger(__name__)
error_count = 0

def process_data():
    global error_count
    try:
        # Some processing with improvements
        result = "success"
        logger.info("Processing completed successfully")
        return result
    except Exception as e:
        error_count += 1
        logger.error(f"Processing failed with error: {e}")
        return None

def validate_input(data):
    \"\"\"New function to validate input data\"\"\"
    if not data:
        logger.warning("Empty data received")
        return False
    return True

if __name__ == "__main__":
    result = process_data()
    print(f"Result: {result}")
""")
                }
                self.repo_info = MockRepoInfo()

        class MockAnalyzerRef:
            def __init__(self):
                self.analyzer = MockAnalyzer()

        # Test 1: Virtual patch creation with bytes content
        print("✅ Test 1: Virtual patch creation with bytes content")
        analyzer_ref = MockAnalyzerRef()
        create_tool = DulwichCreatePatchTool(analyzer_ref)

        # Verify content is actually bytes
        virtual_file = analyzer_ref.analyzer.virtual_files["main.py"]
        print(f"   Content type: {type(virtual_file.content)}")
        print(f"   Is bytes: {isinstance(virtual_file.content, bytes)}")

        result = create_tool._run(
            description="Fix logging and add input validation",
            files=["main.py"],
            branch_name="fix/bytes-handling-test",
            commit_message="Test bytes content handling in patch creation",
            auto_commit=False,  # Just test virtual patch creation first
        )

        if "🎉 Virtual patch created successfully!" in result:
            print("   ✅ Virtual patch creation: SUCCESS")
            # Check if patch content was properly decoded
            if "b'" not in result:  # Should not contain raw bytes representation
                print("   ✅ Bytes properly decoded in patch preview")
            else:
                print("   ❌ Raw bytes found in patch preview")
                return False
        else:
            print("   ❌ Virtual patch creation: FAILED")
            print(f"   Result: {result[:200]}...")
            return False

        # Test 2: Real git operations with bytes content
        print("\n✅ Test 2: Real git operations with bytes content")
        repo_path = os.getcwd()

        result = create_tool._run(
            description="Fix logging and add input validation (real git)",
            files=["main.py"],
            branch_name="fix/bytes-handling-real",
            commit_message="Test bytes content handling with real git operations",
            auto_commit=True,
            repository_path=repo_path,
        )

        if "💾 Committed:" in result and "data must be str, not bytes" not in result:
            print("   ✅ Real git operations: SUCCESS")
            print("   ✅ No bytes-related errors")

            # Verify the file was actually written correctly
            subprocess.run(
                ["git", "checkout", "fix/bytes-handling-real"], capture_output=True
            )
            with open("main.py", "r") as f:
                written_content = f.read()

            if (
                "validate_input" in written_content
                and "logger.error" in written_content
            ):
                print("   ✅ File content written correctly")
            else:
                print("   ❌ File content not written correctly")
                return False

            subprocess.run(["git", "checkout", "main"], capture_output=True)

        elif "data must be str, not bytes" in result:
            print("   ❌ Real git operations: FAILED - Bytes error still present")
            print(f"   Error: {result}")
            return False
        else:
            print("   ❌ Real git operations: FAILED - Other error")
            print(f"   Result: {result[:200]}...")
            return False

        return True

    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback

        traceback.print_exc()
        return False


def show_git_status():
    """Show the final git status"""
    print("\n📊 Final Git Status")
    print("-" * 20)

    try:
        result = subprocess.run(["git", "branch"], capture_output=True, text=True)
        print(f"Branches: {result.stdout.strip()}")

        result = subprocess.run(
            ["git", "log", "--oneline", "-3"], capture_output=True, text=True
        )
        print(f"Recent commits:\n{result.stdout}")

    except Exception as e:
        print(f"Could not show git status: {e}")


def main():
    """Main test function"""
    print("🚀 Logan Bytes Content Handling Test")
    print("=" * 45)
    print("Testing fix for 'data must be str, not bytes' error\n")

    # Save original directory
    original_dir = os.getcwd()

    try:
        # Setup test repository
        test_repo = setup_test_repository()
        print(f"📁 Test repository: {test_repo}")

        # Run tests
        success = test_bytes_content_handling()

        # Show git status
        show_git_status()

        # Summary
        print("\n" + "=" * 50)
        if success:
            print("🎉 All bytes content handling tests passed!")
            print("✅ Virtual patch creation with bytes: WORKING")
            print("✅ Real git operations with bytes: WORKING")
            print("✅ Proper string conversion: WORKING")
        else:
            print("❌ Bytes content handling tests failed!")
            print("   The 'data must be str, not bytes' issue may still exist")

        print(f"\n🗂️  Test repository: {test_repo}")
        print("\n📋 What was tested:")
        print("   ✅ Virtual files with bytes content")
        print("   ✅ Patch preview generation")
        print("   ✅ Real git file writing")
        print("   ✅ String encoding/decoding")

    except Exception as e:
        print(f"❌ Test setup failed: {e}")
        import traceback

        traceback.print_exc()

    finally:
        # Restore original directory
        os.chdir(original_dir)


if __name__ == "__main__":
    main()
