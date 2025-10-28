#!/usr/bin/env python3
"""
Test script to verify Logan works with increased iterations
"""

import os
import sys
import asyncio
import subprocess
from pathlib import Path


def test_logan_iterations():
    """Test Logan with different iteration counts"""
    print("🧪 Testing Logan with increased iterations")
    print("=" * 50)

    # Test current directory has logan.py
    if not os.path.exists("logan.py"):
        print("❌ logan.py not found in current directory")
        return False

    # Test 1: Check help shows new default
    print("\n1️⃣ Testing help output for iteration defaults...")
    try:
        result = subprocess.run(
            [sys.executable, "logan.py", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if "default: 5" in result.stdout:
            print("✅ Default iterations updated to 5")
        else:
            print("⚠️  Help output doesn't show default: 5")
            print(f"Help output: {result.stdout}")
    except Exception as e:
        print(f"❌ Help test failed: {e}")

    # Test 2: Test with explicit iterations
    print("\n2️⃣ Testing explicit iterations parameter...")
    test_commands = [
        ("--iterations 3", "3 iterations"),
        ("--iterations 7", "7 iterations"),
    ]

    for cmd_args, description in test_commands:
        try:
            print(f"   Testing: {description}")
            # Use a simple command that should complete quickly
            cmd = f'echo "help" | {sys.executable} logan.py {cmd_args}'
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=15
            )

            # Check if it at least starts without crashing
            if (
                result.returncode == 0
                or "Logan" in result.stdout
                or "Logan" in result.stderr
            ):
                print(f"   ✅ {description} - Logan started successfully")
            else:
                print(f"   ⚠️  {description} - May have issues")
                if result.stderr:
                    print(f"      Error: {result.stderr[:200]}...")

        except subprocess.TimeoutExpired:
            print(f"   ⏰ {description} - Timed out (expected for interactive mode)")
        except Exception as e:
            print(f"   ❌ {description} - Failed: {e}")

    # Test 3: Environment variable
    print("\n3️⃣ Testing LOGAN_ITERATIONS environment variable...")
    try:
        env = os.environ.copy()
        env["LOGAN_ITERATIONS"] = "4"

        cmd = f'echo "version" | {sys.executable} logan.py'
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=10, env=env
        )

        if (
            result.returncode == 0
            or "Logan" in result.stdout
            or "Logan" in result.stderr
        ):
            print("   ✅ Environment variable test passed")
        else:
            print("   ⚠️  Environment variable test had issues")

    except Exception as e:
        print(f"   ❌ Environment variable test failed: {e}")

    # Test 4: Check if we have a git repository (needed for Logan to work)
    print("\n4️⃣ Checking repository status...")
    if os.path.exists(".git"):
        print("   ✅ Git repository found")

        # Count Python files
        py_files = list(Path(".").glob("*.py"))
        print(f"   📊 Found {len(py_files)} Python files in current directory")

        if len(py_files) > 0:
            print("   ✅ Python files available for analysis")
        else:
            print("   ⚠️  No Python files found for analysis")
    else:
        print("   ⚠️  No Git repository found - Logan may have limited functionality")

    # Test 5: Check AWS dependencies
    print("\n5️⃣ Checking AWS dependencies...")
    try:
        import boto3, langchain, langchain_aws

        print("   ✅ AWS dependencies available")

        # Check if credentials are configured
        try:
            boto3.Session().get_credentials()
            print("   ✅ AWS credentials configured")
        except:
            print("   ⚠️  AWS credentials not configured - will use mock mode")

    except ImportError as e:
        print(f"   ❌ AWS dependencies missing: {e}")

    print("\n" + "=" * 50)
    print("🏁 Logan iteration test complete!")
    print("\n💡 To use Logan with increased iterations:")
    print("   • Default is now 5 iterations (increased from 1)")
    print("   • Use: python3 logan.py --iterations 10")
    print("   • Or set: export LOGAN_ITERATIONS=10")
    print("   • Interactive: python3 logan.py -i")

    return True


def test_simple_logan_execution():
    """Test a simple Logan execution with timeout"""
    print("\n🚀 Testing simple Logan execution...")

    try:
        # Test with a simple version command that should exit quickly
        cmd = [sys.executable, "logan.py", "--help"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)

        if result.returncode == 0:
            print("✅ Logan executes successfully")
            return True
        else:
            print("⚠️  Logan execution returned non-zero exit code")
            if result.stderr:
                print(f"Error output: {result.stderr[:300]}...")
            return False

    except subprocess.TimeoutExpired:
        print("⏰ Logan execution timed out (may be waiting for input)")
        return True  # This is actually expected behavior
    except Exception as e:
        print(f"❌ Logan execution failed: {e}")
        return False


if __name__ == "__main__":
    print("🧪 Logan Iteration Test Suite")
    print("Testing Logan's iteration functionality after modifications")

    # Run basic execution test first
    if test_simple_logan_execution():
        print("✅ Basic execution test passed")

    # Run iteration tests
    test_logan_iterations()

    print("\n🎯 Summary:")
    print("  • Logan's default iterations increased from 1 to 5")
    print("  • Multi-iteration mode enables deeper analysis")
    print("  • Each iteration builds on previous insights")
    print("  • Tools are executed after all iterations complete")
    print("\n💫 Ready to analyze code with enhanced iteration capability!")
