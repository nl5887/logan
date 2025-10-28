#!/usr/bin/env python3
"""
Simple script to test exclusion patterns for the combined CLI analyzer
"""

from pathlib import Path
import fnmatch
from typing import List


def test_exclusion_pattern(file_path: Path, pattern: str, verbose: bool = True) -> bool:
    """Test if a file path matches an exclusion pattern"""
    file_path_str = str(file_path)
    file_path_posix = file_path.as_posix()

    if verbose:
        print(f"\n🔍 Testing: '{file_path_posix}' against pattern '{pattern}'")

    # Strategy 1: Direct glob pattern matching on full path
    if fnmatch.fnmatch(file_path_posix, pattern) or fnmatch.fnmatch(
        file_path_str, pattern
    ):
        if verbose:
            print(f"   ✅ Match: Direct path match")
        return True

    # Strategy 2: Check if any directory in path matches pattern exactly
    path_parts = file_path.parts
    for part in path_parts:
        if fnmatch.fnmatch(part, pattern):
            if verbose:
                print(f"   ✅ Match: Directory part '{part}' matches pattern")
            return True

    # Strategy 3: Pattern with wildcards - check if path contains matching directory
    if fnmatch.fnmatch(file_path_posix, f"*/{pattern}/*") or fnmatch.fnmatch(
        file_path_posix, f"*/{pattern}"
    ):
        if verbose:
            print(f"   ✅ Match: Wildcard directory match")
        return True

    # Strategy 4: Check if file is inside a directory matching pattern
    for i, part in enumerate(path_parts[:-1]):  # Exclude filename
        if fnmatch.fnmatch(part, pattern):
            if verbose:
                print(f"   ✅ Match: Inside directory '{part}' that matches pattern")
            return True
        # Also check if the pattern matches the path up to this point
        partial_path = "/".join(path_parts[: i + 1])
        if fnmatch.fnmatch(partial_path, pattern):
            if verbose:
                print(f"   ✅ Match: Partial path '{partial_path}' matches pattern")
            return True

    # Strategy 5: Directory with contents (pattern ending with /*)
    if pattern.endswith("/*"):
        dir_pattern = pattern[:-2]  # Remove /*
        for part in path_parts[:-1]:  # Exclude filename
            if fnmatch.fnmatch(part, dir_pattern):
                if verbose:
                    print(f"   ✅ Match: Directory contents pattern matches '{part}'")
                return True

    # Strategy 6: Relative path matching from root
    try:
        if len(path_parts) > 0:
            for i in range(len(path_parts)):
                relative_path = "/".join(path_parts[i:])
                if fnmatch.fnmatch(relative_path, pattern):
                    if verbose:
                        print(
                            f"   ✅ Match: Relative path '{relative_path}' matches pattern"
                        )
                    return True
    except:
        pass

    if verbose:
        print(f"   ❌ No match")
    return False


def test_sample_paths():
    """Test exclusion patterns against sample file paths"""

    # Sample file paths that might exist
    test_paths = [
        Path(".venv/lib/python3.13/site-packages/anyio/_backends/_asyncio.py"),
        Path(".git/config"),
        Path("src/main.py"),
        Path("tests/test_main.py"),
        Path("project/tests/unit/test_auth.py"),
        Path("build/lib/package.py"),
        Path("docs/readme.md"),
        Path("__pycache__/main.cpython-39.pyc"),
        Path("node_modules/express/lib/express.js"),
        Path("examples/simple.py"),
        Path("scripts/deploy.py"),
    ]

    # Test patterns
    test_patterns = [
        ".venv",
        ".git",
        "test*",
        "*test*",
        "__pycache__",
        "build",
        "*/build/*",
        ".*",
        "*.pyc",
        "node_modules",
    ]

    print("🧪 Testing Exclusion Patterns")
    print("=" * 60)

    for pattern in test_patterns:
        print(f"\n🎯 Testing pattern: '{pattern}'")
        print("-" * 40)

        matches = []
        for path in test_paths:
            if test_exclusion_pattern(path, pattern, verbose=False):
                matches.append(path)

        if matches:
            print(f"✅ Matches ({len(matches)}):")
            for match in matches:
                print(f"   - {match}")
        else:
            print("❌ No matches")


def test_specific_pattern(pattern: str, paths: List[str] = None):
    """Test a specific pattern against provided paths or defaults"""
    if not paths:
        paths = [
            ".venv/lib/python3.13/site-packages/anyio/_backends/_asyncio.py",
            ".git/config",
            "src/main.py",
            "tests/test_main.py",
        ]

    print(f"\n🎯 Testing specific pattern: '{pattern}'")
    print("=" * 60)

    for path_str in paths:
        path = Path(path_str)
        result = test_exclusion_pattern(path, pattern, verbose=True)
        print(f"Result: {'EXCLUDED' if result else 'INCLUDED'}")


def main():
    """Main test function"""
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "--pattern" and len(sys.argv) > 2:
            # Test specific pattern
            pattern = sys.argv[2]
            paths = sys.argv[3:] if len(sys.argv) > 3 else None
            test_specific_pattern(pattern, paths)
        else:
            print("Usage:")
            print("  python test_exclusions.py                    # Run all tests")
            print(
                "  python test_exclusions.py --pattern '.venv'  # Test specific pattern"
            )
            print(
                "  python test_exclusions.py --pattern '.venv' 'path1' 'path2'  # Test pattern with specific paths"
            )
    else:
        test_sample_paths()


if __name__ == "__main__":
    main()
