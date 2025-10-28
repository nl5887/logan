#!/usr/bin/env python3
"""
Test script for the combined CLI analyzer

This script tests the functionality of the combined_cli_analyzer.py
by running various analysis scenarios and checking the results.
"""

import os
import sys
import json
import tempfile
import shutil
from pathlib import Path
import subprocess


def test_basic_functionality():
    """Test basic functionality of the combined analyzer"""
    print("🔬 Testing Combined CLI Analyzer")
    print("=" * 50)

    # Test 1: Help command
    print("📋 Test 1: Help command")
    try:
        result = subprocess.run(
            [sys.executable, "combined_cli_analyzer.py", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and "Combined Python Code Analyzer" in result.stdout:
            print("✅ Help command works")
        else:
            print("❌ Help command failed")
            print(f"   stdout: {result.stdout[:200]}...")
            print(f"   stderr: {result.stderr[:200]}...")
    except Exception as e:
        print(f"❌ Help command error: {e}")

    # Test 2: Both analyses (default)
    print("\n📋 Test 2: Both analyses on current directory")
    try:
        result = subprocess.run(
            [sys.executable, "combined_cli_analyzer.py", "--directory", ".", "--quiet"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            print("✅ Both analyses completed successfully")
        else:
            print("❌ Both analyses failed")
            print(f"   stdout: {result.stdout[:300]}...")
            print(f"   stderr: {result.stderr[:300]}...")
    except subprocess.TimeoutExpired:
        print("⚠️ Both analyses timed out (might be working but slow)")
    except Exception as e:
        print(f"❌ Both analyses error: {e}")

    # Test 3: Tree-sitter only
    print("\n📋 Test 3: Tree-sitter analysis only")
    try:
        result = subprocess.run(
            [sys.executable, "combined_cli_analyzer.py", "--treesitter", "--quiet"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            print("✅ Tree-sitter analysis completed successfully")
        else:
            print("❌ Tree-sitter analysis failed")
            print(f"   stdout: {result.stdout[:300]}...")
            print(f"   stderr: {result.stderr[:300]}...")
    except subprocess.TimeoutExpired:
        print("⚠️ Tree-sitter analysis timed out")
    except Exception as e:
        print(f"❌ Tree-sitter analysis error: {e}")

    # Test 4: Call graph only
    print("\n📋 Test 4: Call graph analysis only")
    try:
        result = subprocess.run(
            [sys.executable, "combined_cli_analyzer.py", "--callgraph", "--quiet"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            print("✅ Call graph analysis completed successfully")
        else:
            print("❌ Call graph analysis failed")
            print(f"   stdout: {result.stdout[:300]}...")
            print(f"   stderr: {result.stderr[:300]}...")
    except subprocess.TimeoutExpired:
        print("⚠️ Call graph analysis timed out")
    except Exception as e:
        print(f"❌ Call graph analysis error: {e}")

    # Test 5: Function analysis
    print("\n📋 Test 5: Function analysis for 'main'")
    try:
        result = subprocess.run(
            [sys.executable, "combined_cli_analyzer.py", "--function", "main"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            print("✅ Function analysis completed successfully")
            if "Found" in result.stdout and "function" in result.stdout:
                print("✅ Function search results found")
            else:
                print("⚠️ No function results in output")
        else:
            print("❌ Function analysis failed")
            print(f"   stdout: {result.stdout[:300]}...")
            print(f"   stderr: {result.stderr[:300]}...")
    except subprocess.TimeoutExpired:
        print("⚠️ Function analysis timed out")
    except Exception as e:
        print(f"❌ Function analysis error: {e}")

    # Test 6: Verbose mode
    print("\n📋 Test 6: Verbose mode")
    try:
        result = subprocess.run(
            [
                sys.executable,
                "combined_cli_analyzer.py",
                "--callgraph",
                "--verbose",
                "--quiet",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            print("✅ Verbose mode completed successfully")
            if "Debug:" in result.stdout:
                print("✅ Debug output found in verbose mode")
            else:
                print("⚠️ No debug output found (might be expected)")
        else:
            print("❌ Verbose mode failed")
            print(f"   stdout: {result.stdout[:300]}...")
            print(f"   stderr: {result.stderr[:300]}...")
    except subprocess.TimeoutExpired:
        print("⚠️ Verbose mode timed out")
    except Exception as e:
        print(f"❌ Verbose mode error: {e}")

    # Test 7: Export functionality
    print("\n📋 Test 7: Export functionality")
    try:
        # Clean up any existing files first
        for ext in [".json", ".dot"]:
            if Path(f"test_export{ext}").exists():
                Path(f"test_export{ext}").unlink()

        result = subprocess.run(
            [
                sys.executable,
                "combined_cli_analyzer.py",
                "--callgraph",
                "--export",
                "json,dot",
                "--output-prefix",
                "test_export",
                "--quiet",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        json_exists = Path("test_export.json").exists()
        dot_exists = Path("test_export.dot").exists()

        if result.returncode == 0 and (json_exists or dot_exists):
            print("✅ Export functionality works")
            if json_exists:
                print("✅ JSON export created")
                # Try to validate JSON
                try:
                    with open("test_export.json", "r") as f:
                        json.load(f)
                    print("✅ JSON export is valid")
                except:
                    print("⚠️ JSON export exists but is invalid")
            if dot_exists:
                print("✅ DOT export created")
        else:
            print("❌ Export functionality failed")
            print(f"   JSON exists: {json_exists}")
            print(f"   DOT exists: {dot_exists}")
            print(f"   stdout: {result.stdout[:300]}...")
            print(f"   stderr: {result.stderr[:300]}...")

        # Clean up
        for ext in [".json", ".dot"]:
            if Path(f"test_export{ext}").exists():
                Path(f"test_export{ext}").unlink()

    except subprocess.TimeoutExpired:
        print("⚠️ Export test timed out")
    except Exception as e:
        print(f"❌ Export test error: {e}")


def test_individual_analyzers():
    """Test that the individual analyzers still work"""
    print("\n🔧 Testing Individual Analyzers")
    print("=" * 50)

    # Test call graph analyzer
    print("📋 Testing call_graph_analyzer.py")
    try:
        result = subprocess.run(
            [sys.executable, "call_graph_analyzer.py", "--function", "main"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            print("✅ Call graph analyzer works independently")
        else:
            print("❌ Call graph analyzer failed")
            print(f"   stdout: {result.stdout[:300]}...")
            print(f"   stderr: {result.stderr[:300]}...")
    except Exception as e:
        print(f"❌ Call graph analyzer error: {e}")

    # Test treesitter analyzer
    print("\n📋 Testing treesitter_analyzer.py")
    try:
        result = subprocess.run(
            [sys.executable, "treesitter_analyzer.py"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            print("✅ Tree-sitter analyzer works independently")
        else:
            print("❌ Tree-sitter analyzer failed")
            print(f"   stdout: {result.stdout[:300]}...")
            print(f"   stderr: {result.stderr[:300]}...")
    except Exception as e:
        print(f"❌ Tree-sitter analyzer error: {e}")


def test_edge_cases():
    """Test edge cases and error handling"""
    print("\n⚠️ Testing Edge Cases")
    print("=" * 50)

    # Test with non-existent directory
    print("📋 Testing with non-existent directory")
    try:
        result = subprocess.run(
            [
                sys.executable,
                "combined_cli_analyzer.py",
                "--directory",
                "/non/existent/path",
                "--quiet",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            print("✅ Properly handles non-existent directory")
        else:
            print("⚠️ Did not fail for non-existent directory")
    except Exception as e:
        print(f"❌ Non-existent directory test error: {e}")

    # Test with non-existent function
    print("\n📋 Testing with non-existent function")
    try:
        result = subprocess.run(
            [
                sys.executable,
                "combined_cli_analyzer.py",
                "--function",
                "non_existent_function_12345",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if "not found" in result.stdout.lower():
            print("✅ Properly handles non-existent function")
        else:
            print("⚠️ Did not properly report non-existent function")
            print(f"   stdout: {result.stdout[:300]}...")
    except Exception as e:
        print(f"❌ Non-existent function test error: {e}")


def main():
    """Run all tests"""
    print("🧪 Combined CLI Analyzer Test Suite")
    print("=" * 50)
    print(f"📁 Working directory: {os.getcwd()}")
    print(f"🐍 Python version: {sys.version}")
    print()

    # Check if the required files exist
    required_files = [
        "combined_cli_analyzer.py",
        "call_graph_analyzer.py",
        "treesitter_analyzer.py",
    ]

    missing_files = [f for f in required_files if not Path(f).exists()]
    if missing_files:
        print(f"❌ Missing required files: {missing_files}")
        return 1

    print("✅ All required files found")
    print()

    try:
        test_basic_functionality()
        test_individual_analyzers()
        test_edge_cases()

        print("\n🎉 Test Suite Complete")
        print("=" * 50)
        print("Check the results above for any issues.")
        print("✅ = Pass, ❌ = Fail, ⚠️ = Warning/Timeout")

    except KeyboardInterrupt:
        print("\n⚠️ Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Test suite error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
