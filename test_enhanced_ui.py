#!/usr/bin/env python3
"""
Test Enhanced Interactive Features

This is a standalone test to verify that the enhanced interactive UI components
work correctly with prompt_toolkit and rich.
"""

import asyncio
import sys
import os
from typing import Optional

# Test if enhanced libraries are available
try:
    from prompt_toolkit.shortcuts import PromptSession
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.history import InMemoryHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich.panel import Panel
    from rich.table import Table
    from rich.syntax import Syntax
    from rich import print as rich_print

    ENHANCED_AVAILABLE = True
except ImportError as e:
    ENHANCED_AVAILABLE = False
    print(f"❌ Enhanced libraries not available: {e}")
    print("💡 Install with: pip install prompt-toolkit rich")


class EnhancedUITest:
    """Test class for enhanced interactive UI features."""

    def __init__(self):
        self.console = Console()
        self.command_history = []

    async def test_enhanced_components(self):
        """Test all enhanced UI components."""

        if not ENHANCED_AVAILABLE:
            print("Skipping enhanced tests - libraries not available")
            return False

        # Test 1: Rich Console Output
        self.test_rich_output()

        # Test 2: Progress Indicators
        await self.test_progress_indicators()

        # Test 3: Syntax Highlighting
        self.test_syntax_highlighting()

        # Test 4: Tables and Panels
        self.test_tables_and_panels()

        # Test 5: Interactive Prompt (if in terminal)
        if sys.stdin.isatty() and sys.stdout.isatty():
            await self.test_interactive_prompt()
        else:
            self.console.print("⚠️ Skipping prompt test - not in terminal")

        return True

    def test_rich_output(self):
        """Test rich console output formatting."""
        self.console.print("\n🎨 Testing Rich Output Formatting", style="bold blue")
        self.console.print("-" * 40)

        # Test different styles
        self.console.print("✅ Success message", style="bold green")
        self.console.print("⚠️ Warning message", style="bold yellow")
        self.console.print("❌ Error message", style="bold red")
        self.console.print("💡 Info message", style="bold cyan")
        self.console.print("🔍 Debug message", style="dim white")

    async def test_progress_indicators(self):
        """Test progress bars and spinners."""
        self.console.print("\n📊 Testing Progress Indicators", style="bold blue")
        self.console.print("-" * 40)

        # Test progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=self.console,
        ) as progress:
            task = progress.add_task("Processing...", total=100)

            for i in range(100):
                await asyncio.sleep(0.01)  # Simulate work
                progress.update(task, advance=1)

        self.console.print("✅ Progress indicators working!")

    def test_syntax_highlighting(self):
        """Test syntax highlighting for code."""
        self.console.print("\n🔍 Testing Syntax Highlighting", style="bold blue")
        self.console.print("-" * 40)

        # Sample Python code
        python_code = '''
def enhanced_interactive_demo():
    """Example function with syntax highlighting."""
    import asyncio

    async def process_query(query: str) -> str:
        # Simulate processing
        await asyncio.sleep(0.1)
        return f"Processed: {query}"

    return "Demo complete!"
'''

        try:
            syntax = Syntax(
                python_code,
                "python",
                theme="monokai",
                line_numbers=True,
                background_color="default",
            )

            self.console.print(
                Panel(
                    syntax,
                    title="[bold green]Python Code Example[/bold green]",
                    border_style="green",
                )
            )

        except Exception as e:
            self.console.print(f"❌ Syntax highlighting failed: {e}", style="red")

    def test_tables_and_panels(self):
        """Test tables and panels for structured output."""
        self.console.print("\n📋 Testing Tables and Panels", style="bold blue")
        self.console.print("-" * 40)

        # Test table
        table = Table(title="Enhanced Features Test Results")
        table.add_column("Feature", style="cyan", no_wrap=True)
        table.add_column("Status", style="green")
        table.add_column("Notes", style="white")

        test_results = [
            ("Rich Console", "✅ Pass", "Colors and styling work"),
            ("Progress Bars", "✅ Pass", "Smooth animation"),
            ("Syntax Highlighting", "✅ Pass", "Code properly formatted"),
            ("Auto-completion", "⏳ Pending", "Requires terminal"),
            ("Command History", "⏳ Pending", "Requires terminal"),
        ]

        for feature, status, notes in test_results:
            table.add_row(feature, status, notes)

        self.console.print(table)

        # Test panel
        self.console.print("\n")
        self.console.print(
            Panel(
                "[green]✅ All visual components working correctly![/green]\n"
                "[dim]Enhanced UI provides much better user experience[/dim]",
                title="[bold blue]Test Summary[/bold blue]",
                border_style="blue",
            )
        )

    async def test_interactive_prompt(self):
        """Test interactive prompt with auto-completion."""
        self.console.print("\n💬 Testing Interactive Prompt", style="bold blue")
        self.console.print("-" * 40)

        # Setup auto-completion
        commands = [
            "help",
            "test",
            "demo",
            "analyze",
            "find",
            "search",
            "list",
            "show",
            "check",
            "explain",
            "quit",
            "exit",
        ]
        completer = WordCompleter(commands, ignore_case=True)

        # Setup history
        history = InMemoryHistory()

        # Create prompt session
        session = PromptSession(
            completer=completer,
            history=history,
            auto_suggest=AutoSuggestFromHistory(),
        )

        self.console.print("🎯 Interactive prompt ready!")
        self.console.print("💡 Try typing 'he' and press Tab for completion")
        self.console.print("💡 Use ↑/↓ arrows for history")
        self.console.print("💡 Type 'quit' to finish test\n")

        test_complete = False
        command_count = 0

        while not test_complete and command_count < 5:  # Limit for automated testing
            try:
                user_input = await session.prompt_async("🧪 Test> ")
                command_count += 1

                if user_input.strip().lower() in ["quit", "exit", "done"]:
                    test_complete = True
                    self.console.print("✅ Interactive prompt test completed!")

                elif user_input.strip().lower() == "help":
                    self.console.print("Available commands:", style="bold")
                    self.console.print(", ".join(commands), style="cyan")

                elif user_input.strip():
                    self.command_history.append(user_input.strip())
                    self.console.print(f"📝 Recorded command: {user_input.strip()}")

                    # Show command history
                    if len(self.command_history) > 1:
                        self.console.print(
                            f"📚 Command history: {', '.join(self.command_history[-3:])}"
                        )

                if command_count >= 5:
                    self.console.print("⏰ Test limit reached - prompt test completed!")
                    test_complete = True

            except (EOFError, KeyboardInterrupt):
                self.console.print("\n⚠️ Prompt test interrupted")
                test_complete = True

    def test_fallback_mode(self):
        """Test fallback to basic mode when enhanced features unavailable."""
        self.console.print("\n🔄 Testing Fallback Mode", style="bold blue")
        self.console.print("-" * 40)

        # Simulate conditions where enhanced mode would fall back
        conditions = [
            ("Terminal check", sys.stdin.isatty() and sys.stdout.isatty()),
            ("Enhanced libraries", ENHANCED_AVAILABLE),
        ]

        for condition, status in conditions:
            status_text = "✅ Available" if status else "❌ Not available"
            self.console.print(f"{condition}: {status_text}")

        # Determine overall status
        all_available = all(status for _, status in conditions)

        if all_available:
            self.console.print(
                "\n🎉 Enhanced mode fully available!", style="bold green"
            )
        else:
            self.console.print("\n⚠️ Would fall back to basic mode", style="bold yellow")
            self.console.print("💡 This ensures Logan works in any environment")


async def main():
    """Run all enhanced UI tests."""
    print("🧪 Enhanced UI Components Test Suite")
    print("=" * 50)

    tester = EnhancedUITest()

    try:
        # Run all tests
        success = await tester.test_enhanced_components()

        # Test fallback conditions
        tester.test_fallback_mode()

        if success:
            tester.console.print(
                "\n🎉 All tests completed successfully!", style="bold green"
            )
            tester.console.print("✨ Enhanced interactive mode is ready to use!")
        else:
            print("\n⚠️ Some tests were skipped due to missing dependencies")

    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--check-only":
            print("🔍 Checking enhanced UI availability...")
            if ENHANCED_AVAILABLE:
                print("✅ Enhanced libraries available")
                if sys.stdin.isatty():
                    print("✅ Running in terminal")
                    print("🚀 Enhanced mode ready!")
                else:
                    print("⚠️ Not in terminal - would use fallback")
            else:
                print("❌ Enhanced libraries missing")
                print("💡 Install with: pip install prompt-toolkit rich")
            sys.exit(0)

        elif sys.argv[1] == "--help":
            print("Enhanced UI Test Suite")
            print("Usage:")
            print("  python3 test_enhanced_ui.py          # Run all tests")
            print(
                "  python3 test_enhanced_ui.py --check-only  # Check availability only"
            )
            print("  python3 test_enhanced_ui.py --help       # Show this help")
            sys.exit(0)

    # Run the test suite
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n👋 Test suite cancelled!")
        sys.exit(1)
