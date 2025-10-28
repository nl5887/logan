#!/usr/bin/env python3
"""
Simple test for Logan notification system.
Tests the basic flow: initial message -> LLM response -> completion.
"""

import asyncio
import os
from notifications import (
    NotificationManager,
    AnalysisSummary,
    SlackNotificationProvider,
    DummyNotificationProvider,
)


async def test_basic_flow():
    """Test the basic notification flow."""
    print("🧪 Testing Basic Notification Flow...")

    # Create notification manager
    config = {
        "providers": {
            "slack": {
                "enabled": bool(os.getenv("SLACK_BOT_TOKEN")),
                "bot_token": os.getenv("SLACK_BOT_TOKEN"),
                "channel": os.getenv("SLACK_CHANNEL", "#general"),
            }
        }
    }

    manager = NotificationManager(config)

    # Add dummy provider if no Slack
    if not os.getenv("SLACK_BOT_TOKEN"):
        manager.add_provider(DummyNotificationProvider())
        print("   Using dummy provider (set SLACK_BOT_TOKEN for real Slack)")
    else:
        print("   Using Slack notifications")

    # Test 1: Initial notification
    summary = AnalysisSummary(
        repository_path="https://github.com/example/test-repo",
        commit_hash="abc123def456",
        branch="main",
        task_description="Find all async functions and analyze their usage patterns",
        analysis_type="code_analysis",
    )

    print("\n📤 Sending initial notification...")
    await manager.send_initial_notification(summary)

    # Simulate some processing time
    await asyncio.sleep(1)

    # Test 2: LLM Response (simulate what Logan would send)
    llm_response = """I'll help you find and analyze async functions in the repository.

Let me start by searching for async function definitions:

🔍 Searching for async functions...

I found 23 async functions across 8 files:

**Key findings:**
- Most async functions are in `src/api/` directory (15 functions)
- 3 functions in `src/database/` for DB operations
- 5 utility functions in `src/utils/`

**Common patterns:**
1. HTTP request handlers using FastAPI
2. Database query functions using asyncpg
3. Background task processors

**Recommendations:**
- Consider adding timeout handling to HTTP requests
- Some functions could benefit from connection pooling
- Add proper error handling for async database operations"""

    print("📤 Sending LLM response...")
    await manager.send_progress_update(llm_response, "info")

    await asyncio.sleep(1)

    # Test 3: Tool execution update
    tool_update = "🔧 Running code search tool to find async/await patterns..."
    print("📤 Sending tool update...")
    await manager.send_progress_update(tool_update, "progress")

    await asyncio.sleep(1)

    # Test 4: Results
    results = """📊 **Analysis Results:**

Found 23 async functions with the following breakdown:
- API endpoints: 15 functions
- Database operations: 3 functions
- Utility functions: 5 functions

**Files analyzed:**
- `src/api/users.py` - 8 async endpoints
- `src/api/orders.py` - 7 async endpoints
- `src/database/queries.py` - 3 async functions
- `src/utils/http_client.py` - 5 async utilities

**Potential issues identified:**
⚠️ Missing timeout in `fetch_user_data()`
⚠️ No connection pooling in database functions
✅ Proper error handling in most functions"""

    print("📤 Sending analysis results...")
    await manager.send_progress_update(results, "success")

    await asyncio.sleep(1)

    # Test 5: Completion
    completion_summary = """✅ **Analysis Complete**

Successfully analyzed async function patterns in the repository.

**Summary:**
- Analyzed 23 async functions across 8 files
- Identified 2 potential improvements
- Generated recommendations for better async patterns

**Repository:** https://github.com/example/test-repo
**Commit:** abc123def456
**Branch:** main"""

    print("📤 Sending completion notification...")
    await manager.send_completion_notification(completion_summary, success=True)

    print("✅ Basic notification flow test completed!")


async def test_error_scenario():
    """Test error notification."""
    print("\n🧪 Testing Error Scenario...")

    manager = NotificationManager()  # Will use dummy

    await manager.send_error_notification(
        "Failed to parse file: syntax error in main.py line 42",
        "Error occurred while analyzing Python files",
    )

    print("✅ Error scenario test completed!")


async def main():
    """Run all tests."""
    print("🚀 Simple Logan Notification Tests")
    print("=" * 50)

    print(f"Environment:")
    print(
        f"  SLACK_BOT_TOKEN: {'✅ Set' if os.getenv('SLACK_BOT_TOKEN') else '❌ Not set'}"
    )
    print(f"  SLACK_CHANNEL: {os.getenv('SLACK_CHANNEL', '#general')}")
    print()

    try:
        await test_basic_flow()
        await test_error_scenario()

        print("\n🎉 All tests completed!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
