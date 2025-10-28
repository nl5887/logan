#!/usr/bin/env python3
"""
Test script for the Logan notification system.

This script tests different notification providers and scenarios.
"""

import asyncio
import json
import os
import tempfile
from datetime import datetime
from typing import Dict, Any

from notifications import (
    NotificationManager,
    SlackNotificationProvider,
    DummyNotificationProvider,
    AnalysisSummary,
    NotificationMessage,
    create_notification_manager,
)


async def test_dummy_provider():
    """Test the dummy notification provider."""
    print("🧪 Testing Dummy Provider...")

    # Create dummy provider
    provider = DummyNotificationProvider()

    # Test initial notification
    summary = AnalysisSummary(
        repository_path="/path/to/test/repo",
        commit_hash="abc123def",
        branch="main",
        task_description="Test analysis of authentication system",
        estimated_tasks=[
            "Search for authentication functions",
            "Analyze security patterns",
            "Check for vulnerabilities",
            "Generate security report",
        ],
        analysis_type="security_analysis",
    )

    thread_id = await provider.send_initial_notification(summary)
    print(f"   Initial notification sent, thread_id: {thread_id}")

    # Test progress updates
    await provider.send_progress_update(
        NotificationMessage(
            content="Found 15 authentication functions",
            message_type="info",
            thread_id=thread_id,
        )
    )
    print("   Progress update 1 sent")

    await provider.send_progress_update(
        NotificationMessage(
            content="Analyzing JWT token handling",
            message_type="progress",
            thread_id=thread_id,
        )
    )
    print("   Progress update 2 sent")

    await provider.send_progress_update(
        NotificationMessage(
            content="Warning: Found hardcoded secret in config.py",
            message_type="warning",
            thread_id=thread_id,
        )
    )
    print("   Warning notification sent")

    # Test completion
    await provider.send_completion_notification(
        "Security analysis completed. Found 3 potential vulnerabilities and 12 recommendations.",
        success=True,
    )
    print("   Completion notification sent")

    # Show stored messages
    print(f"   Messages stored: {len(provider.messages)}")
    for i, (msg_type, msg_data) in enumerate(provider.messages, 1):
        print(f"      {i}. {msg_type}: {type(msg_data).__name__}")

    print("✅ Dummy provider test completed\n")


async def test_slack_provider_mock():
    """Test Slack provider with mock configuration (won't actually send)."""
    print("🧪 Testing Slack Provider (Mock)...")

    # Create mock Slack config
    config = {
        "enabled": False,  # Disabled to avoid actual sending
        "webhook_url": "https://hooks.slack.com/services/MOCK/WEBHOOK/URL",
        "channel": "#code-analysis",
        "username": "Logan Test Bot",
    }

    provider = SlackNotificationProvider(config)
    print(f"   Provider enabled: {provider.enabled}")

    # Test with real data but disabled sending
    summary = AnalysisSummary(
        repository_path="https://github.com/example/my-app",
        commit_hash="a1b2c3d4e5f6",
        branch="feature/auth-improvements",
        task_description="Refactor authentication system for better security",
        estimated_tasks=[
            "Audit current authentication flow",
            "Identify security vulnerabilities",
            "Design improved architecture",
            "Implement password hashing improvements",
            "Add multi-factor authentication support",
            "Update session management",
            "Create security documentation",
        ],
    )

    # This won't actually send since provider is disabled
    thread_id = await provider.send_initial_notification(summary)
    print(f"   Mock initial notification, thread_id: {thread_id}")

    # Test different message types
    message_types = [
        ("Starting authentication audit...", "info"),
        ("Found 5 security issues", "warning"),
        ("Password hashing implemented", "success"),
        ("Session management updated", "success"),
        ("Documentation complete", "info"),
    ]

    for content, msg_type in message_types:
        await provider.send_progress_update(
            NotificationMessage(
                content=content, message_type=msg_type, thread_id=thread_id
            )
        )
        print(f"   Mock progress update: {msg_type}")

    await provider.send_completion_notification(
        "Authentication system refactoring completed successfully!\n\n"
        + "**Summary:**\n"
        + "• Fixed 5 security vulnerabilities\n"
        + "• Implemented bcrypt password hashing\n"
        + "• Added MFA support\n"
        + "• Updated session management\n"
        + "• Created comprehensive documentation\n\n"
        + "**Impact:** Security score improved from C+ to A-",
        success=True,
    )
    print("   Mock completion notification sent")

    print("✅ Slack provider mock test completed\n")


async def test_notification_manager():
    """Test the notification manager with multiple providers."""
    print("🧪 Testing Notification Manager...")

    # Create config with multiple providers
    config = {
        "providers": {
            "slack": {
                "enabled": False,  # Mock only
                "webhook_url": "https://hooks.slack.com/mock",
                "channel": "#test-notifications",
            }
        }
    }

    manager = NotificationManager(config)

    # Add dummy provider for testing
    manager.add_provider(DummyNotificationProvider())

    print(f"   Manager has {len(manager.providers)} providers")
    print(f"   Manager enabled: {manager.is_enabled()}")

    # Test full workflow
    summary = AnalysisSummary(
        repository_path="./my-project",
        task_description="Comprehensive code quality analysis",
        estimated_tasks=[
            "Analyze code complexity",
            "Check test coverage",
            "Review documentation",
            "Identify technical debt",
            "Generate quality report",
        ],
    )

    # Send initial notification
    await manager.send_initial_notification(summary)
    print("   Initial notification sent to all providers")

    # Send several progress updates
    updates = [
        ("Analyzing code complexity metrics...", "info"),
        ("Found 23 functions with high complexity", "warning"),
        ("Test coverage analysis in progress...", "info"),
        ("Current test coverage: 67%", "info"),
        ("Reviewing documentation completeness...", "info"),
        ("Generated technical debt report", "success"),
    ]

    for content, msg_type in updates:
        await manager.send_progress_update(content, msg_type)
        print(f"   Progress update sent: {msg_type}")

    # Send completion
    completion_summary = (
        "Code quality analysis completed!\n\n"
        "**Findings:**\n"
        "• Code complexity: 12 functions need refactoring\n"
        "• Test coverage: 67% (target: 80%)\n"
        "• Documentation: 89% complete\n"
        "• Technical debt: 23 items identified\n\n"
        "**Recommendations:**\n"
        "1. Refactor high-complexity functions\n"
        "2. Add tests to reach 80% coverage\n"
        "3. Complete API documentation\n"
        "4. Address high-priority technical debt"
    )

    await manager.send_completion_notification(completion_summary, success=True)
    print("   Completion notification sent to all providers")

    print("✅ Notification manager test completed\n")


async def test_error_scenarios():
    """Test error handling scenarios."""
    print("🧪 Testing Error Scenarios...")

    manager = NotificationManager()  # Will use dummy provider

    # Test error notification
    await manager.send_error_notification(
        "Failed to parse configuration file",
        "Error occurred while loading config.json: Invalid JSON syntax",
    )
    print("   Error notification sent")

    # Test with invalid Slack config (should gracefully fallback)
    slack_config = {
        "enabled": True,
        "webhook_url": "invalid-url",  # Invalid URL
        "channel": "#test",
    }

    provider = SlackNotificationProvider(slack_config)
    print(f"   Slack provider with invalid URL enabled: {provider.enabled}")

    # This should handle the error gracefully
    result = await provider.send_progress_update(
        NotificationMessage(content="Test message", message_type="info")
    )
    print(f"   Send with invalid URL result: {result}")

    print("✅ Error scenarios test completed\n")


async def test_config_loading():
    """Test configuration loading from file and environment."""
    print("🧪 Testing Configuration Loading...")

    # Create temporary config file
    config_data = {
        "providers": {
            "slack": {
                "enabled": True,
                "webhook_url": "https://hooks.slack.com/test",
                "channel": "#logan-analysis",
                "username": "Logan Code Analyzer",
            }
        },
        "settings": {"max_retries": 3, "timeout": 30},
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config_data, f)
        config_path = f.name

    try:
        # Test loading from file
        manager = create_notification_manager(config_path)
        print(f"   Loaded config from file: {len(manager.providers)} providers")

        # Test environment variable override
        os.environ["SLACK_WEBHOOK_URL"] = "https://hooks.slack.com/env-override"
        os.environ["SLACK_CHANNEL"] = "#env-channel"

        manager_env = create_notification_manager()
        print(f"   Loaded config from env: {len(manager_env.providers)} providers")

        # Check if Slack provider exists
        slack_providers = [
            p for p in manager_env.providers if isinstance(p, SlackNotificationProvider)
        ]
        if slack_providers:
            slack_provider = slack_providers[0]
            print(
                f"   Slack webhook from env: {slack_provider.webhook_url.endswith('env-override')}"
            )
            print(f"   Slack channel from env: {slack_provider.channel}")

    finally:
        # Cleanup
        os.unlink(config_path)
        os.environ.pop("SLACK_WEBHOOK_URL", None)
        os.environ.pop("SLACK_CHANNEL", None)

    print("✅ Configuration loading test completed\n")


async def main():
    """Run all tests."""
    print("🚀 Logan Notification System Tests")
    print("=" * 50)

    try:
        await test_dummy_provider()
        await test_slack_provider_mock()
        await test_notification_manager()
        await test_error_scenarios()
        await test_config_loading()

        print("🎉 All tests completed successfully!")

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
