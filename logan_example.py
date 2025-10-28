#!/usr/bin/env python3
"""
Logan Usage Examples
This script demonstrates different ways to use the Logan streaming assistant
"""

import asyncio
import subprocess
import sys
import os
from logan import LoganAssistant


async def example_programmatic_usage():
    """Example of using Logan programmatically in Python code"""
    print("=== Programmatic Usage Example ===")

    # Create Logan instance
    assistant = LoganAssistant(model_id="anthropic.claude-3-haiku-20240307-v1:0")

    # Custom system prompt for coding assistance
    assistant.system_prompt = """You are a helpful coding assistant. Provide clear,
    concise code examples and explanations. Focus on Python best practices."""

    # Example questions
    questions = [
        "How do I create a simple web server in Python?",
        "What's the difference between list and tuple in Python?",
        "Show me how to handle exceptions properly in Python",
    ]

    for i, question in enumerate(questions, 1):
        print(f"\n--- Question {i}: {question} ---")
        await assistant.stream_response(question)
        print("\n" + "=" * 60)


def example_command_line_usage():
    """Example of using Logan via command line"""
    print("=== Command Line Usage Examples ===")

    examples = [
        {
            "description": "Simple question via echo",
            "command": 'echo "What is machine learning?" | python logan.py',
        },
        {"description": "Interactive mode", "command": "python logan.py -i"},
        {
            "description": "Custom model with single question",
            "command": 'echo "Explain async/await" | python logan.py --model anthropic.claude-3-haiku-20240307-v1:0',
        },
        {
            "description": "Custom system prompt",
            "command": 'python logan.py -s "You are a creative writing assistant" -i',
        },
    ]

    for example in examples:
        print(f"\n{example['description']}:")
        print(f"Command: {example['command']}")
        print("-" * 50)


def example_file_input():
    """Example of using Logan with file input"""
    print("=== File Input Example ===")

    # Create a sample question file
    sample_file = "sample_question.txt"
    with open(sample_file, "w") as f:
        f.write("""Please explain the following Python concepts:
1. List comprehensions
2. Generators
3. Decorators
4. Context managers

Provide practical examples for each.""")

    print(f"Created sample file: {sample_file}")
    print(f"Usage: cat {sample_file} | python logan.py")
    print(f"Or: python logan.py < {sample_file}")


async def example_batch_questions():
    """Example of processing multiple questions in batch"""
    print("=== Batch Processing Example ===")

    assistant = LoganAssistant()
    assistant.system_prompt = "You are a helpful assistant. Give brief, clear answers."

    questions = [
        "What is Python?",
        "What is JavaScript?",
        "What is the difference between Python and JavaScript?",
        "Which one should I learn first?",
    ]

    print("Processing multiple questions:")
    for i, question in enumerate(questions, 1):
        print(f"\n🔍 Question {i}: {question}")
        await assistant.stream_response(question)
        print("\n" + "-" * 40)


def example_environment_setup():
    """Show examples of environment setup for different scenarios"""
    print("=== Environment Setup Examples ===")

    setups = [
        {
            "name": "Local Development",
            "description": "Using AWS CLI configured credentials",
            "commands": [
                "aws configure",
                "export AWS_REGION=us-east-1",
                "python logan.py -i",
            ],
        },
        {
            "name": "CI/CD Pipeline",
            "description": "Using environment variables",
            "commands": [
                "export AWS_ACCESS_KEY_ID=your_access_key",
                "export AWS_SECRET_ACCESS_KEY=your_secret_key",
                "export AWS_REGION=us-west-2",
                "echo 'Generate unit tests for this function' | python logan.py",
            ],
        },
        {
            "name": "Docker Container",
            "description": "Using IAM roles or mounted credentials",
            "commands": [
                "# Mount AWS credentials",
                "docker run -v ~/.aws:/root/.aws your-image python logan.py -i",
                "# Or use IAM roles in ECS/EKS",
            ],
        },
    ]

    for setup in setups:
        print(f"\n{setup['name']}:")
        print(f"Description: {setup['description']}")
        print("Commands:")
        for cmd in setup["commands"]:
            print(f"  {cmd}")
        print("-" * 50)


def example_integration_patterns():
    """Show examples of integrating Logan into other applications"""
    print("=== Integration Patterns ===")

    patterns = [
        {
            "name": "Web API Integration",
            "code": """
# FastAPI example
from fastapi import FastAPI
from logan import LoganAssistant

app = FastAPI()
assistant = LoganAssistant()

@app.post("/chat")
async def chat_endpoint(message: str):
    response = ""
    # Collect streamed response
    callback = StreamingCallbackHandler()
    await assistant.stream_response(message)
    return {"response": callback.text}
""",
        },
        {
            "name": "Slack Bot Integration",
            "code": """
# Slack bot example
from slack_sdk import WebClient
from logan import LoganAssistant

assistant = LoganAssistant()

async def handle_slack_message(event):
    user_message = event['text']
    response = await assistant.stream_response(user_message)
    # Send response back to Slack
""",
        },
        {
            "name": "CLI Tool Integration",
            "code": '''
# CLI wrapper example
import subprocess

def ask_logan(question):
    """Ask Logan a question and return the response"""
    result = subprocess.run(
        ["python", "logan.py"],
        input=question,
        text=True,
        capture_output=True
    )
    return result.stdout
''',
        },
    ]

    for pattern in patterns:
        print(f"\n{pattern['name']}:")
        print(pattern["code"])
        print("-" * 50)


async def main():
    """Run all examples"""
    print("🚀 Logan Usage Examples")
    print("=" * 60)

    # Check if we can actually run Logan (AWS credentials available)
    try:
        import boto3

        boto3.client("bedrock-runtime", region_name="us-east-1")
        can_run_live = True
    except Exception:
        can_run_live = False
        print("⚠️  AWS credentials not configured - showing examples only")
        print("   Configure AWS credentials to run live examples")

    # Always show these examples
    example_command_line_usage()
    example_file_input()
    example_environment_setup()
    example_integration_patterns()

    # Only run live examples if AWS is configured
    if can_run_live:
        print("\n🔴 Live Examples (requires AWS Bedrock access):")
        try:
            await example_programmatic_usage()
            await example_batch_questions()
        except Exception as e:
            print(f"❌ Could not run live examples: {e}")
            print("   Make sure you have AWS Bedrock access and proper permissions")
    else:
        print("\n💡 To run live examples:")
        print("   1. Configure AWS credentials: aws configure")
        print("   2. Ensure Bedrock access in AWS console")
        print("   3. Run: python logan_example.py")


if __name__ == "__main__":
    asyncio.run(main())
