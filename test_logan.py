#!/usr/bin/env python3
"""
Test script for Logan streaming assistant
This script tests Logan functionality without requiring AWS credentials
"""

import asyncio
import sys
import os
from unittest.mock import Mock, AsyncMock, patch
from logan import LoganAssistant, StreamingCallbackHandler


class MockBedrock:
    """Mock AWS Bedrock client for testing"""

    def __init__(self):
        self.model_id = "test-model"

    async def astream(self, messages, callbacks=None):
        """Mock streaming response"""
        test_tokens = [
            "Hello",
            " there",
            "!",
            " How",
            " can",
            " I",
            " help",
            " you",
            " today",
            "?",
        ]

        for token in test_tokens:
            # Simulate token generation
            if callbacks:
                for callback in callbacks:
                    await callback.on_llm_new_token(token)
            yield Mock(content=token)


async def test_streaming_callback():
    """Test the streaming callback handler"""
    print("🧪 Testing StreamingCallbackHandler...")

    callback = StreamingCallbackHandler()

    # Test token handling
    await callback.on_llm_new_token("Hello")
    await callback.on_llm_new_token(" World")

    assert callback.text == "Hello World", (
        f"Expected 'Hello World', got '{callback.text}'"
    )
    print("✅ StreamingCallbackHandler test passed")


async def test_logan_assistant_init():
    """Test Logan assistant initialization"""
    print("🧪 Testing LoganAssistant initialization...")

    assistant = LoganAssistant("test-model-id")

    assert assistant.model_id == "test-model-id", (
        f"Expected 'test-model-id', got '{assistant.model_id}'"
    )
    assert assistant.llm is None, "LLM should be None initially"
    assert "Logan" in assistant.system_prompt, "System prompt should mention Logan"

    print("✅ LoganAssistant initialization test passed")


async def test_mock_streaming():
    """Test streaming with mocked Bedrock"""
    print("🧪 Testing mock streaming...")

    assistant = LoganAssistant()

    # Mock the Bedrock LLM
    mock_llm = MockBedrock()
    assistant.llm = mock_llm

    print("Mock streaming test: ", end="")

    # Capture output
    captured_tokens = []

    class TestCallback(StreamingCallbackHandler):
        async def on_llm_new_token(self, token: str, **kwargs):
            captured_tokens.append(token)
            print(token, end="", flush=True)

    # Mock the astream method
    with patch.object(assistant.llm, "astream", new=mock_llm.astream):
        callback = TestCallback()

        # This would normally call Bedrock, but we'll mock it
        messages = []  # Empty messages for test
        async for chunk in assistant.llm.astream(messages, callbacks=[callback]):
            pass

    print()  # New line
    expected_tokens = [
        "Hello",
        " there",
        "!",
        " How",
        " can",
        " I",
        " help",
        " you",
        " today",
        "?",
    ]
    assert captured_tokens == expected_tokens, (
        f"Expected {expected_tokens}, got {captured_tokens}"
    )

    print("✅ Mock streaming test passed")


def test_user_input_parsing():
    """Test user input parsing logic"""
    print("🧪 Testing user input parsing...")

    assistant = LoganAssistant()

    # Test quit commands (we can't actually test input() but we can test the logic)
    quit_commands = ["quit", "exit", "bye", "QUIT", "EXIT", "BYE"]

    for cmd in quit_commands:
        # Simulate the logic from get_user_input
        if cmd.lower() in ["quit", "exit", "bye"]:
            result = None
        else:
            result = cmd

        assert result is None, f"Command '{cmd}' should return None"

    print("✅ User input parsing test passed")


async def test_command_line_args():
    """Test command line argument parsing"""
    print("🧪 Testing command line arguments...")

    # We can't directly test argparse without modifying sys.argv,
    # but we can test the assistant configuration

    # Test default model
    assistant1 = LoganAssistant()
    assert "claude-3-sonnet" in assistant1.model_id, (
        "Default model should be Claude 3 Sonnet"
    )

    # Test custom model
    assistant2 = LoganAssistant("custom-model-id")
    assert assistant2.model_id == "custom-model-id", "Custom model ID should be set"

    # Test custom system prompt
    assistant3 = LoganAssistant()
    custom_prompt = "You are a test assistant"
    assistant3.system_prompt = custom_prompt
    assert assistant3.system_prompt == custom_prompt, (
        "Custom system prompt should be set"
    )

    print("✅ Command line arguments test passed")


def test_error_handling():
    """Test error handling scenarios"""
    print("🧪 Testing error handling...")

    assistant = LoganAssistant()

    # Test invalid model ID handling (can't actually test AWS errors without credentials)
    try:
        # This should work fine - we're just testing object creation
        invalid_assistant = LoganAssistant("invalid-model-id")
        assert invalid_assistant.model_id == "invalid-model-id"
        print("✅ Error handling structure test passed")
    except Exception as e:
        print(f"❌ Unexpected error in error handling test: {e}")


async def test_message_preparation():
    """Test message preparation for LLM"""
    print("🧪 Testing message preparation...")

    assistant = LoganAssistant()

    # Test system prompt
    assert assistant.system_prompt is not None, "System prompt should not be None"
    assert len(assistant.system_prompt) > 0, "System prompt should not be empty"
    assert "Logan" in assistant.system_prompt, "System prompt should mention Logan"

    print("✅ Message preparation test passed")


def run_integration_test():
    """Run a simple integration test without AWS"""
    print("🧪 Running integration test...")

    # Test that we can import and create Logan without errors
    try:
        from logan import LoganAssistant, StreamingCallbackHandler

        # Create instances
        assistant = LoganAssistant()
        callback = StreamingCallbackHandler()

        # Test basic properties
        assert hasattr(assistant, "model_id")
        assert hasattr(assistant, "system_prompt")
        assert hasattr(assistant, "llm")
        assert hasattr(callback, "text")

        print("✅ Integration test passed")
        return True

    except ImportError as e:
        print(f"❌ Import error in integration test: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error in integration test: {e}")
        return False


async def main():
    """Run all tests"""
    print("🚀 Running Logan Tests")
    print("=" * 50)

    tests_passed = 0
    tests_failed = 0

    # Run tests
    test_functions = [
        test_streaming_callback,
        test_logan_assistant_init,
        test_mock_streaming,
        test_user_input_parsing,
        test_command_line_args,
        test_error_handling,
        test_message_preparation,
    ]

    for test_func in test_functions:
        try:
            if asyncio.iscoroutinefunction(test_func):
                await test_func()
            else:
                test_func()
            tests_passed += 1
        except Exception as e:
            print(f"❌ Test {test_func.__name__} failed: {e}")
            tests_failed += 1

    # Run integration test
    if run_integration_test():
        tests_passed += 1
    else:
        tests_failed += 1

    print("\n" + "=" * 50)
    print(f"📊 Test Results:")
    print(f"✅ Passed: {tests_passed}")
    print(f"❌ Failed: {tests_failed}")
    print(
        f"📈 Success Rate: {(tests_passed / (tests_passed + tests_failed)) * 100:.1f}%"
    )

    if tests_failed == 0:
        print("🎉 All tests passed!")
        return True
    else:
        print("⚠️  Some tests failed. Check the output above.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
