#!/usr/bin/env python3
"""
Simple test script to isolate dulwich issues
"""

import sys

print("🔧 Starting test script...")

# Test 1: Basic imports
print("🔧 Testing imports...")
try:
    print("  - Importing dulwich...")
    from dulwich import porcelain
    from dulwich.repo import MemoryRepo
    from dulwich.client import get_transport_and_path

    print("  ✅ Dulwich imports successful")
except ImportError as e:
    print(f"  ❌ Dulwich import failed: {e}")
    sys.exit(1)
except Exception as e:
    print(f"  ❌ Unexpected import error: {e}")
    sys.exit(1)

# Test 2: Check if we can create basic objects
print("🔧 Testing basic dulwich objects...")
try:
    memory_repo = MemoryRepo()
    print("  ✅ MemoryRepo created successfully")
except Exception as e:
    print(f"  ❌ MemoryRepo creation failed: {e}")
    sys.exit(1)

# Test 3: Test URL parsing
print("🔧 Testing URL handling...")
test_url = "https://git.bricks.raven.dtact.com/4h_HCGsl9KCkSScFhGs51"
try:
    from urllib.parse import urlparse, urlunparse

    parsed = urlparse(test_url)
    print(f"  ✅ URL parsed: {parsed.hostname}")

    # Test auth URL modification
    username = "test_user"
    password = "test_pass"
    netloc = f"{username}:{password}@{parsed.hostname}"
    if parsed.port:
        netloc += f":{parsed.port}"
    auth_url = urlunparse(parsed._replace(netloc=netloc))
    print("  ✅ Auth URL created successfully")

except Exception as e:
    print(f"  ❌ URL handling failed: {e}")
    sys.exit(1)

# Test 4: Test transport creation (this is where it might hang)
print("🔧 Testing transport creation...")
try:
    print(f"  - Creating transport for: {test_url}")
    client, path = get_transport_and_path(test_url)
    print(f"  ✅ Transport created successfully, path: {path}")
    print(f"  - Client type: {type(client)}")
except Exception as e:
    print(f"  ❌ Transport creation failed: {e}")
    print(f"  - Error type: {type(e)}")
    sys.exit(1)

print("🎉 All basic tests passed!")
print("🔧 Now testing with authentication...")

# Test 5: Test with auth URL
auth_test_url = f"https://GuJ_SqwUM_d4xu671Qe4u:aJFbEPyQmFBUOBFnktFp8@git.bricks.raven.dtact.com/4h_HCGsl9KCkSScFhGs51"
try:
    print(f"  - Creating transport with auth...")
    auth_client, auth_path = get_transport_and_path(auth_test_url)
    print(f"  ✅ Auth transport created, path: {auth_path}")
    print(f"  - Auth client type: {type(auth_client)}")
except Exception as e:
    print(f"  ❌ Auth transport creation failed: {e}")
    print(f"  - Error type: {type(e)}")
    sys.exit(1)

print("🎉 All tests including auth passed!")
print("🔧 The issue might be in the network fetch operation...")

# Test 6: Try to get remote refs (this will likely hang or fail)
print("🔧 Testing remote refs fetch (this might hang)...")
try:
    print("  - About to call get_refs...")
    import signal

    def timeout_handler(signum, frame):
        raise TimeoutError("Operation timed out")

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(10)  # 10 second timeout

    try:
        refs = auth_client.get_refs(auth_path)
        signal.alarm(0)  # Cancel alarm
        print(f"  ✅ Got {len(refs)} refs from remote")
        for ref_name, ref_sha in list(refs.items())[:5]:
            print(
                f"    - {ref_name.decode('utf-8', errors='replace')}: {ref_sha.decode('utf-8')}"
            )
    except TimeoutError:
        print("  ❌ Operation timed out after 10 seconds")
        print("  💡 This suggests network connectivity or server issues")
    except Exception as inner_e:
        signal.alarm(0)  # Cancel alarm
        print(f"  ❌ get_refs failed: {inner_e}")
        print(f"  - Error type: {type(inner_e)}")

except Exception as e:
    print(f"  ❌ Timeout setup failed: {e}")

print("🏁 Test script completed!")
