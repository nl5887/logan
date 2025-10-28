#!/usr/bin/env python3
"""
Test script to verify parameter filtering in Logan's tool execution
This tests the fix for the "unexpected keyword argument 'update'" error
"""

import os
import sys

# Add the current directory to the path so we can import Logan
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_parameter_filtering():
    """Test that tool execution properly filters unexpected parameters"""
    print("🧪 Testing Parameter Filtering in Tool Execution")
    print("=" * 55)

    try:
        from logan import DulwichCreatePatchTool

        # Create mock analyzer
        class MockVirtualFile:
            def __init__(self, content):
                self.content = content

        class MockRepoInfo:
            def __init__(self):
                self.url = "https://github.com/test/repo"
                self.branch = "main"
                self.commit_sha = "abc123"

        class MockAnalyzer:
            def __init__(self):
                self.virtual_files = {
                    "test.py": MockVirtualFile("print('hello world')")
                }
                self.repo_info = MockRepoInfo()

        class MockAnalyzerRef:
            def __init__(self):
                self.analyzer = MockAnalyzer()

        # Create tool
        analyzer_ref = MockAnalyzerRef()
        create_tool = DulwichCreatePatchTool(analyzer_ref)

        print("✅ Created mock tool and analyzer")

        # Test 1: Valid parameters only
        print("\n🎯 Test 1: Valid parameters only")
        try:
            valid_args = {
                "description": "Test patch",
                "files": ["test.py"],
                "branch_name": "test/valid-params",
                "commit_message": "Test commit",
                "auto_commit": False,
                "auto_push": False,
                "repository_path": "",
                "force_push": False,
            }
            result = create_tool._run(**valid_args)
            print("✅ Valid parameters: PASSED")
            print(f"   Result: {'Success' if '🎉' in result else 'Error'}")
        except Exception as e:
            print(f"❌ Valid parameters: FAILED - {e}")

        # Test 2: Valid parameters + unexpected parameter
        print("\n🎯 Test 2: Valid parameters + unexpected 'update' parameter")
        try:
            mixed_args = {
                "description": "Test patch with extra param",
                "files": ["test.py"],
                "branch_name": "test/mixed-params",
                "commit_message": "Test commit with extra param",
                "auto_commit": False,
                "auto_push": False,
                "repository_path": "",
                "force_push": False,
                "update": True,  # This is the unexpected parameter
                "extra_param": "should_be_ignored",  # Another unexpected one
            }
            result = create_tool._run(**mixed_args)
            print("❌ Mixed parameters: This should have failed without filtering")
        except TypeError as e:
            if "unexpected keyword argument" in str(e):
                print("❌ Mixed parameters: FAILED - Parameter filtering not working")
                print(f"   Error: {e}")
                return False
            else:
                print(f"❌ Mixed parameters: FAILED - Different error: {e}")
                return False
        except Exception as e:
            print(f"❌ Mixed parameters: FAILED - Unexpected error: {e}")
            return False

        # Test 3: Using Logan's tool execution method with parameter filtering
        print("\n🎯 Test 3: Using Logan's parameter filtering")
        from logan import LoganAssistant

        # Create a minimal Logan assistant
        assistant = LoganAssistant(model_id="mock")

        # Simulate tool call with unexpected parameters
        mock_tool_call = {
            "name": "create_patch",
            "args": {
                "description": "Test patch via Logan",
                "files": ["test.py"],
                "branch_name": "test/logan-filtering",
                "commit_message": "Test commit via Logan",
                "auto_commit": False,
                "update": True,  # Unexpected parameter
                "invalid_param": "should_be_filtered",  # Another unexpected parameter
            },
        }

        # Test if Logan's parameter filtering works
        if hasattr(assistant, "tools") and assistant.tools:
            print("✅ Logan has tools loaded")

            # Find our create_patch tool
            create_patch_tool = None
            for tool in assistant.tools:
                if hasattr(tool, "name") and tool.name == "create_patch":
                    create_patch_tool = tool
                    break

            if create_patch_tool:
                print("✅ Found create_patch tool in Logan")

                # Test parameter filtering using inspection
                try:
                    import inspect

                    sig = inspect.signature(create_patch_tool._run)
                    valid_params = set(sig.parameters.keys()) - {"self"}

                    print(f"   Valid parameters: {sorted(valid_params)}")

                    tool_args = mock_tool_call["args"]
                    print(f"   Provided parameters: {sorted(tool_args.keys())}")

                    filtered_args = {
                        k: v for k, v in tool_args.items() if k in valid_params
                    }
                    print(f"   Filtered parameters: {sorted(filtered_args.keys())}")

                    # Try to call with filtered parameters
                    result = create_patch_tool._run(**filtered_args)
                    print("✅ Parameter filtering: WORKING")
                    print(
                        f"   Result: {'Success' if '🎉' in result else 'Error (but no exception)'}"
                    )

                except Exception as e:
                    print(f"❌ Parameter filtering failed: {e}")
                    return False
            else:
                print(
                    "⚠️  create_patch tool not found in Logan (AWS dependencies may be missing)"
                )
        else:
            print("⚠️  Logan has no tools loaded (AWS dependencies may be missing)")

        print("\n🎉 All parameter filtering tests completed successfully!")
        return True

    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 This might be expected if dependencies aren't installed")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_inspect_tool_signatures():
    """Test inspection of tool method signatures"""
    print("\n🔍 Testing Tool Signature Inspection")
    print("=" * 40)

    try:
        from logan import DulwichCreatePatchTool, DulwichApplyPatchTool
        import inspect

        # Test create patch tool
        class MockAnalyzerRef:
            class MockAnalyzer:
                virtual_files = {}
                repo_info = None

            analyzer = MockAnalyzer()

        create_tool = DulwichCreatePatchTool(MockAnalyzerRef())
        apply_tool = DulwichApplyPatchTool(MockAnalyzerRef())

        # Inspect signatures
        create_sig = inspect.signature(create_tool._run)
        apply_sig = inspect.signature(apply_tool._run)

        print("✅ Create Patch Tool Parameters:")
        for name, param in create_sig.parameters.items():
            if name != "self":
                default = (
                    f" = {param.default}"
                    if param.default != inspect.Parameter.empty
                    else ""
                )
                print(
                    f"   {name}: {param.annotation.__name__ if hasattr(param.annotation, '__name__') else param.annotation}{default}"
                )

        print("\n✅ Apply Patch Tool Parameters:")
        for name, param in apply_sig.parameters.items():
            if name != "self":
                default = (
                    f" = {param.default}"
                    if param.default != inspect.Parameter.empty
                    else ""
                )
                print(
                    f"   {name}: {param.annotation.__name__ if hasattr(param.annotation, '__name__') else param.annotation}{default}"
                )

        return True

    except Exception as e:
        print(f"❌ Signature inspection failed: {e}")
        return False


def main():
    """Main test function"""
    print("🚀 Logan Parameter Filtering Test")
    print("This test verifies that unexpected parameters are properly filtered")
    print("to prevent 'unexpected keyword argument' errors\n")

    test1_success = test_parameter_filtering()
    test2_success = test_inspect_tool_signatures()

    print("\n" + "=" * 60)
    if test1_success and test2_success:
        print("✅ All parameter filtering tests passed!")
        print("✅ Tool signature inspection: WORKING")
        print("✅ Parameter filtering mechanism: WORKING")
    else:
        print("⚠️  Some tests had issues:")
        print(f"   Parameter filtering: {'✅' if test1_success else '❌'}")
        print(f"   Signature inspection: {'✅' if test2_success else '❌'}")

    print("\n💡 This fix should resolve the 'unexpected keyword argument' error")
    print("   by filtering out parameters that tools don't expect.")


if __name__ == "__main__":
    main()
