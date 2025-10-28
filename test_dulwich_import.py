#!/usr/bin/env python3
"""
Simple test script to check dulwich import issues
"""

import sys
import io
from contextlib import redirect_stdout, redirect_stderr

print("Testing dulwich import...")

# Test 1: Direct dulwich import
print("1. Testing direct dulwich import...")
try:
    import dulwich

    print("✅ dulwich imported successfully")
except ImportError as e:
    print(f"❌ dulwich import failed: {e}")
    sys.exit(1)

# Test 2: Test dulwich_memory_analyzer import with output suppression
print("2. Testing dulwich_memory_analyzer import...")
try:
    # Suppress all output during import
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        from dulwich_memory_analyzer import InMemoryAnalyzer

    print("✅ dulwich_memory_analyzer imported successfully")

    # Test 3: Try to create an analyzer instance
    print("3. Testing analyzer initialization...")
    analyzer = InMemoryAnalyzer(verbose=False)
    print("✅ InMemoryAnalyzer created successfully")

except ImportError as e:
    print(f"❌ dulwich_memory_analyzer import failed: {e}")
except Exception as e:
    print(f"❌ Analyzer initialization failed: {e}")

print("Test completed.")
