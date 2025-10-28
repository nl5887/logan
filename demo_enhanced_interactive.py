#!/usr/bin/env python3
"""
Enhanced Interactive Logan Demo

This script demonstrates the enhanced interactive features using prompt_toolkit and rich.
Run this in a terminal to see the full enhanced experience with:
- Auto-completion
- Command history
- Rich formatted output
- Progress indicators
- Syntax highlighting
"""

import asyncio
import sys
import os

# Add the current directory to the path so we can import logan_async_notifications
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from logan_async_notifications import AsyncLoganWithNotifications


async def demo_enhanced_interactive():
    """Run a demo of the enhanced interactive mode."""

    print("🚀 Logan Enhanced Interactive Demo")
    print("=" * 50)
    print()
    print("This demo shows Logan's enhanced interactive features:")
    print("✨ Auto-completion (press Tab)")
    print("📝 Command history (use ↑/↓ arrows)")
    print("🎨 Rich formatted output")
    print("📊 Progress indicators")
    print("🔍 Syntax highlighting")
    print()
    print("Try these sample commands:")
    print("  • help - Show available commands")
    print("  • analyze - Analyze code patterns")
    print("  • find functions - Find functions in code")
    print("  • list files - List project files")
    print("  • quit - Exit the demo")
    print()
    print("Starting enhanced interactive mode...")
    print("-" * 50)

    # Create Logan assistant with enhanced interactive mode
    assistant = AsyncLoganWithNotifications(
        model_id="anthropic.claude-3-haiku-20240307-v1:0",  # Use a fast model for demo
        max_iterations=3,  # Limit iterations for demo
        debug_mode=False,
        enable_notifications=False,  # Disable notifications for interactive demo
    )

    # Check if enhanced mode is available
    try:
        from prompt_toolkit.shortcuts import PromptSession
        from rich.console import Console

        if sys.stdin.isatty() and sys.stdout.isatty():
            print("✅ Enhanced interactive mode available!")
            print("🎯 Features: Auto-completion, history, rich output")
        else:
            print("⚠️  Running in non-terminal environment")
            print("💡 For full experience, run directly in terminal:")
            print("   python3 demo_enhanced_interactive.py")

    except ImportError:
        print("❌ Enhanced libraries not available")
        print("💡 Install with: pip install prompt-toolkit rich")
        return

    # Run the enhanced interactive mode
    try:
        await assistant.run_interactive_mode()
    except KeyboardInterrupt:
        print("\n👋 Demo interrupted!")
    except Exception as e:
        print(f"\n❌ Demo error: {e}")
    finally:
        print("\n📝 Demo complete! Check .logan_history for saved commands.")


def show_feature_comparison():
    """Show comparison between basic and enhanced modes."""
    print()
    print("🔄 Basic vs Enhanced Interactive Mode")
    print("=" * 50)
    print()

    comparison = [
        ("Feature", "Basic Mode", "Enhanced Mode"),
        ("─" * 20, "─" * 15, "─" * 20),
        ("Input method", "input()", "prompt_toolkit"),
        ("Auto-completion", "❌ None", "✅ Commands + Tab"),
        ("Command history", "❌ None", "✅ ↑/↓ arrows + file"),
        ("Output formatting", "Plain text", "Rich formatting"),
        ("Progress indicators", "❌ None", "✅ Spinners + bars"),
        ("Syntax highlighting", "❌ None", "✅ Code highlighting"),
        ("Error handling", "Basic", "Formatted panels"),
        ("Help system", "❌ None", "✅ Rich tables"),
        ("Multi-line input", "❌ Limited", "✅ Full support"),
        ("Keyboard shortcuts", "❌ None", "✅ Ctrl+C handling"),
    ]

    for feature, basic, enhanced in comparison:
        print(f"{feature:<20} {basic:<15} {enhanced}")

    print()
    print("🚀 The enhanced mode provides a much better user experience!")


if __name__ == "__main__":
    print("🎭 Logan Enhanced Interactive Demo")
    print()

    # Show feature comparison first
    show_feature_comparison()

    # Check if we should run the demo
    if len(sys.argv) > 1 and sys.argv[1] == "--compare-only":
        print("💡 Run without --compare-only to start interactive demo")
        sys.exit(0)

    # Run the demo
    try:
        asyncio.run(demo_enhanced_interactive())
    except KeyboardInterrupt:
        print("\n👋 Demo cancelled!")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        print("💡 Make sure you have the required dependencies:")
        print("   pip install prompt-toolkit rich boto3 langchain-aws")
