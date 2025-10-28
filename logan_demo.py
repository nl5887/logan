#!/usr/bin/env python3
"""
Logan Demo Script
Demonstrates different usage patterns for the Logan streaming assistant
"""

import asyncio
import subprocess
import sys
import os
import time
from logan import LoganAssistant


def print_banner(title):
    """Print a formatted banner for demo sections"""
    print("\n" + "=" * 60)
    print(f"🎯 {title}")
    print("=" * 60)


def print_command(description, command):
    """Print a formatted command example"""
    print(f"\n📝 {description}")
    print(f"💻 Command: {command}")
    print("-" * 40)


async def demo_basic_usage():
    """Demonstrate basic Logan usage"""
    print_banner("Basic Usage Demo")

    # Create Logan instance
    assistant = LoganAssistant()

    print("Creating Logan assistant with default settings...")
    print(f"Model ID: {assistant.model_id}")
    print(f"System prompt preview: {assistant.system_prompt[:100]}...")

    # Demo questions
    questions = [
        "What is Python?",
        "How do I create a function in Python?",
        "What's the difference between a list and a tuple?",
    ]

    for i, question in enumerate(questions, 1):
        print(f"\n🔍 Demo Question {i}: {question}")
        await assistant.stream_response(question)
        print("\n" + "-" * 40)

        # Add a small delay for readability
        await asyncio.sleep(1)


async def demo_custom_system_prompt():
    """Demonstrate custom system prompt usage"""
    print_banner("Custom System Prompt Demo")

    # Create assistant with custom system prompt
    assistant = LoganAssistant()
    assistant.system_prompt = """You are a Python coding mentor. You provide clear,
    practical code examples with explanations. Always include working code snippets
    when relevant. Focus on best practices and pythonic solutions."""

    print("Using custom system prompt for coding assistance...")

    coding_questions = [
        "Show me how to read a CSV file in Python",
        "How do I handle exceptions properly?",
        "What's a Python decorator and how do I use one?",
    ]

    for question in coding_questions:
        print(f"\n💻 Coding Question: {question}")
        await assistant.stream_response(question)
        print("\n" + "-" * 40)
        await asyncio.sleep(1)


def demo_command_line_examples():
    """Show command line usage examples"""
    print_banner("Command Line Usage Examples")

    examples = [
        ("Simple question", 'echo "What is machine learning?" | python logan.py'),
        ("Interactive mode", "python logan.py -i"),
        (
            "Custom model",
            'echo "Explain recursion" | python logan.py --model anthropic.claude-3-haiku-20240307-v1:0',
        ),
        (
            "Custom system prompt",
            'python logan.py -s "You are a creative writing assistant" -i',
        ),
        ("File input", "cat my_questions.txt | python logan.py"),
        (
            "Redirect to file",
            'echo "Summarize Python basics" | python logan.py > response.txt',
        ),
    ]

    for description, command in examples:
        print_command(description, command)


def demo_integration_patterns():
    """Show integration patterns"""
    print_banner("Integration Patterns")

    patterns = [
        {
            "title": "Shell Script Integration",
            "code": """#!/bin/bash
# ask_logan.sh - Simple wrapper script
echo "$1" | python logan.py
""",
            "usage": "./ask_logan.sh 'What is Docker?'",
        },
        {
            "title": "Python Script Integration",
            "code": '''import subprocess

def ask_logan(question):
    """Ask Logan a question via subprocess"""
    result = subprocess.run(
        ["python", "logan.py"],
        input=question,
        text=True,
        capture_output=True
    )
    return result.stdout

# Usage
response = ask_logan("Explain list comprehensions")
print(response)
''',
            "usage": "python my_script.py",
        },
        {
            "title": "Batch Processing",
            "code": """# batch_questions.txt
What is Python?
How do I install packages?
What are virtual environments?

# Process batch
cat batch_questions.txt | while read -r line; do
    echo "Q: $line"
    echo "$line" | python logan.py
    echo "---"
done
""",
            "usage": "./process_batch.sh",
        },
    ]

    for pattern in patterns:
        print(f"\n🔧 {pattern['title']}:")
        print("Code:")
        print(pattern["code"])
        print(f"Usage: {pattern['usage']}")
        print("-" * 50)


def demo_environment_setup():
    """Show environment setup examples"""
    print_banner("Environment Setup Examples")

    setups = [
        {
            "name": "Local Development",
            "steps": [
                "# Install dependencies",
                "./setup_logan.sh",
                "",
                "# Configure AWS credentials",
                "aws configure",
                "",
                "# Test Logan",
                "echo 'Hello Logan!' | python logan.py",
            ],
        },
        {
            "name": "Docker Container",
            "steps": [
                "# Dockerfile",
                "FROM python:3.9-slim",
                "WORKDIR /app",
                "COPY requirements.txt .",
                "RUN pip install -r requirements.txt",
                "COPY logan.py .",
                "",
                "# Build and run",
                "docker build -t logan-assistant .",
                "docker run -e AWS_ACCESS_KEY_ID=xxx \\",
                "           -e AWS_SECRET_ACCESS_KEY=yyy \\",
                "           -e AWS_REGION=us-east-1 \\",
                "           logan-assistant python logan.py -i",
            ],
        },
        {
            "name": "GitHub Actions CI/CD",
            "steps": [
                "# .github/workflows/logan.yml",
                "name: Logan Assistant",
                "on: [push]",
                "jobs:",
                "  ask-logan:",
                "    runs-on: ubuntu-latest",
                "    steps:",
                "    - uses: actions/checkout@v2",
                "    - uses: actions/setup-python@v2",
                "      with:",
                "        python-version: '3.9'",
                "    - run: pip install -r requirements.txt",
                "    - run: echo 'Review this code' | python logan.py",
                "      env:",
                "        AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}",
                "        AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}",
            ],
        },
    ]

    for setup in setups:
        print(f"\n🛠️ {setup['name']}:")
        for step in setup["steps"]:
            print(f"  {step}")
        print("-" * 50)


def demo_troubleshooting():
    """Show troubleshooting tips"""
    print_banner("Troubleshooting Guide")

    issues = [
        {
            "issue": "AWS Credentials Not Found",
            "solution": [
                "1. Check AWS credentials:",
                "   aws sts get-caller-identity",
                "",
                "2. Configure credentials:",
                "   aws configure",
                "   # OR set environment variables:",
                "   export AWS_ACCESS_KEY_ID=your_key",
                "   export AWS_SECRET_ACCESS_KEY=your_secret",
                "   export AWS_REGION=us-east-1",
            ],
        },
        {
            "issue": "Model Access Denied",
            "solution": [
                "1. Go to AWS Bedrock console",
                "2. Navigate to 'Model access'",
                "3. Request access to required models",
                "4. Wait for approval (can take time)",
                "5. Verify model availability in your region",
            ],
        },
        {
            "issue": "Dependencies Missing",
            "solution": [
                "1. Run setup script:",
                "   ./setup_logan.sh",
                "",
                "2. Or install manually:",
                "   pip install boto3 langchain langchain-aws",
                "",
                "3. Activate virtual environment:",
                "   source .venv/bin/activate",
            ],
        },
        {
            "issue": "Slow Response Times",
            "solution": [
                "1. Try a faster model (e.g., Claude Haiku):",
                "   --model anthropic.claude-3-haiku-20240307-v1:0",
                "",
                "2. Use a closer AWS region",
                "3. Check your internet connection",
                "4. Verify AWS service status",
            ],
        },
    ]

    for item in issues:
        print(f"\n❌ {item['issue']}:")
        for step in item["solution"]:
            print(f"   {step}")
        print("-" * 50)


async def demo_performance_comparison():
    """Demonstrate different models and performance"""
    print_banner("Model Performance Demo")

    models = [
        ("Claude 3 Haiku (Fast)", "anthropic.claude-3-haiku-20240307-v1:0"),
        ("Claude 3 Sonnet (Balanced)", "anthropic.claude-3-sonnet-20240229-v1:0"),
        ("Claude 3 Opus (Best)", "anthropic.claude-3-opus-20240229-v1:0"),
    ]

    question = "Explain Python list comprehensions in 2 sentences."

    for model_name, model_id in models:
        print(f"\n🧪 Testing {model_name}:")
        print(f"Model ID: {model_id}")

        assistant = LoganAssistant(model_id=model_id)

        start_time = time.time()
        await assistant.stream_response(question)
        end_time = time.time()

        print(f"\n⏱️ Response time: {end_time - start_time:.2f} seconds")
        print("-" * 50)


def create_sample_files():
    """Create sample files for demonstration"""
    print_banner("Creating Sample Files")

    # Sample questions file
    with open("sample_questions.txt", "w") as f:
        f.write("""What is Python and why is it popular?
How do I install Python packages?
What are Python virtual environments?
Explain object-oriented programming in Python
Show me how to handle files in Python
""")

    # Sample batch script
    with open("ask_multiple.sh", "w") as f:
        f.write("""#!/bin/bash
# Batch question processor
while IFS= read -r question; do
    echo "🔍 Question: $question"
    echo "$question" | python logan.py
    echo ""
    echo "---"
    echo ""
done < sample_questions.txt
""")

    # Make script executable
    os.chmod("ask_multiple.sh", 0o755)

    print("✅ Created sample_questions.txt")
    print("✅ Created ask_multiple.sh")
    print("\nUsage:")
    print("  cat sample_questions.txt | python logan.py")
    print("  ./ask_multiple.sh")


async def main():
    """Run all demonstrations"""
    print("🎪 Logan Streaming Assistant - Complete Demo")
    print("=" * 60)
    print("This demo shows various ways to use Logan assistant")
    print("Note: Without AWS credentials, Logan runs in mock mode")

    # Check if we should run live demos
    run_live = (
        input("\n🤔 Do you want to run live demos? (requires AWS setup) [y/N]: ")
        .lower()
        .strip()
        == "y"
    )

    if not run_live:
        print("📚 Running documentation demos only...")
        demo_command_line_examples()
        demo_integration_patterns()
        demo_environment_setup()
        demo_troubleshooting()
        create_sample_files()
    else:
        print("🚀 Running live demos...")
        try:
            await demo_basic_usage()
            await demo_custom_system_prompt()
            await demo_performance_comparison()
        except Exception as e:
            print(f"❌ Live demo failed: {e}")
            print("💡 Make sure AWS credentials are configured")

        # Always show documentation examples
        demo_command_line_examples()
        demo_integration_patterns()
        demo_environment_setup()
        demo_troubleshooting()
        create_sample_files()

    print("\n🎉 Demo complete!")
    print("💡 Try running: python logan.py -i")
    print("📖 See README_LOGAN.md for detailed documentation")


if __name__ == "__main__":
    asyncio.run(main())
