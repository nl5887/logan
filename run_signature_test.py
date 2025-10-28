#!/usr/bin/env python3
"""
Test runner to verify function signature extraction from tree-sitter analysis.
"""

import sys
import os
from dulwich_memory_analyzer import InMemoryAnalyzer


def test_signature_extraction():
    """Test the signature extraction feature"""
    print("🧪 Testing Function Signature Extraction")
    print("=" * 50)

    # Test with the signature test file
    test_file = "test_signature_extraction.py"

    if not os.path.exists(test_file):
        print(f"❌ Test file {test_file} not found")
        return False

    # Create analyzer and analyze the test file
    analyzer = InMemoryAnalyzer()

    # Read test file content
    with open(test_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Add to virtual files
    analyzer.virtual_files[test_file] = type(
        "VirtualFile", (), {"content": content, "text_content": lambda: content}
    )()

    # Analyze the file
    analyzer._analyze_python_files([test_file])

    print(f"📊 Found {len(analyzer.functions)} functions")
    print("\n🔍 Function Signatures:")
    print("-" * 30)

    success_count = 0
    total_count = 0

    for func_name, func_info in analyzer.functions.items():
        total_count += 1
        signature = func_info.signature or "❌ No signature extracted"

        if func_info.signature:
            success_count += 1
            status = "✅"
        else:
            status = "❌"

        print(f"{status} {func_name}")
        print(
            f"   📄 {func_info.file_path}:{func_info.line_start}-{func_info.line_end}"
        )
        print(f"   🔧 {signature}")

        if func_info.is_method:
            print(f"   🏗️  Method in class: {func_info.class_name}")
        if func_info.is_async:
            print(f"   ⚡ Async function")
        print()

    print("=" * 50)
    print(f"📈 Results: {success_count}/{total_count} functions have signatures")
    print(f"🎯 Success Rate: {(success_count / total_count) * 100:.1f}%")

    # Test search functionality with signatures
    print("\n🔍 Testing Search with Signatures:")
    print("-" * 30)

    test_patterns = ["async", "function_with", "method"]

    for pattern in test_patterns:
        results = analyzer.search_combined(pattern, "functions")
        print(f"\n🔎 Pattern: '{pattern}' -> {len(results)} matches")

        for result in results[:3]:  # Show first 3 matches
            signature = result.get("signature", "No signature")
            print(f"   🔧 {result['name']} - {signature}")

    return (
        success_count > total_count * 0.7
    )  # Consider successful if >70% have signatures


def test_with_real_file():
    """Test signature extraction with a real Python file"""
    print("\n🧪 Testing with Real File (logan.py)")
    print("=" * 50)

    analyzer = InMemoryAnalyzer()

    # Test with logan.py
    test_file = "logan.py"
    if os.path.exists(test_file):
        with open(test_file, "r", encoding="utf-8") as f:
            content = f.read()

        analyzer.virtual_files[test_file] = type(
            "VirtualFile", (), {"content": content, "text_content": lambda: content}
        )()

        analyzer._analyze_python_files([test_file])

        print(f"📊 Found {len(analyzer.functions)} functions in logan.py")

        # Show some examples with signatures
        example_count = 0
        for func_name, func_info in analyzer.functions.items():
            if func_info.signature and example_count < 5:
                example_count += 1
                print(f"✅ {func_name}")
                print(f"   🔧 {func_info.signature}")
                print()

        return True
    else:
        print(f"❌ logan.py not found")
        return False


if __name__ == "__main__":
    print("🚀 Starting Function Signature Extraction Tests\n")

    test1_result = test_signature_extraction()
    test2_result = test_with_real_file()

    print("\n" + "=" * 60)
    print("🏁 Final Results:")
    print(f"   Test File Analysis: {'✅ PASS' if test1_result else '❌ FAIL'}")
    print(f"   Real File Analysis: {'✅ PASS' if test2_result else '❌ FAIL'}")

    if test1_result and test2_result:
        print("\n🎉 All tests passed! Signature extraction is working correctly.")
        sys.exit(0)
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")
        sys.exit(1)
