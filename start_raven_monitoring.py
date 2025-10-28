#!/usr/bin/env python3
"""
Quick Start Script for Raven Multi-Brick Log Monitoring

This script provides the easiest way to start monitoring all three Raven brick
log streams for syntax errors and exceptions in real-time.

Usage:
    python start_raven_monitoring.py                    # Monitor all bricks
    python start_raven_monitoring.py --save-to-file     # Save exceptions to file
    python start_raven_monitoring.py --syntax-only      # Focus only on syntax errors
    python start_raven_monitoring.py --brick 3KKPiWPJZ4xiJAl0ZA1vY  # Monitor specific brick
"""

import asyncio
import argparse
import signal
import sys
from datetime import datetime
from pathlib import Path

# Brick configurations
RAVEN_BRICKS = {
    "3KKPiWPJZ4xiJAl0ZA1vY": {
        "name": "Primary Brick",
        "description": "Main processing brick",
        "priority": "HIGH",
    },
    "p29OHpShid8VxErrGxbvv": {
        "name": "Secondary Brick",
        "description": "Data processing brick",
        "priority": "MEDIUM",
    },
    "4h_HCGsl9KCkSScFhGs51": {
        "name": "Analysis Brick",
        "description": "Analysis and reporting brick",
        "priority": "MEDIUM",
    },
}


class RavenQuickMonitor:
    """Quick and easy Raven brick monitoring"""

    def __init__(self):
        self.running = False
        self.stats = {
            "total_exceptions": 0,
            "syntax_errors": 0,
            "by_brick": {},
            "start_time": None,
        }

    async def start_monitoring(
        self, brick_ids=None, save_to_file=False, syntax_only=False
    ):
        """Start monitoring with simple configuration"""

        # Import here to avoid dependency issues at startup
        try:
            from monitor_raven_logs import RavenLogMonitor
        except ImportError:
            print("❌ Error: Required modules not found!")
            print(
                "   Make sure monitor_raven_logs.py and log_stream_monitor.py are in the same directory"
            )
            return False

        # Use all bricks if none specified
        if not brick_ids:
            brick_ids = list(RAVEN_BRICKS.keys())

        # Setup output file if requested
        output_file = None
        if save_to_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"raven_exceptions_{timestamp}.json"

        # Display startup info
        self._print_startup_banner(brick_ids, output_file, syntax_only)

        # Create and configure monitor
        monitor = RavenLogMonitor(
            brick_ids=brick_ids,
            config_override={
                "context_lines": 30,  # More context for stacktraces
                "timeout": 60.0,
                "reconnect_delay": 3.0,
                "stacktrace_context_lines": 25,
            },
        )

        # Setup signal handling
        def signal_handler(signum, frame):
            print(f"\n📡 Received signal {signum}, stopping monitoring...")
            monitor.stop_monitoring()
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        self.running = True
        self.stats["start_time"] = datetime.now()

        # Custom exception handler
        original_handler = monitor.handle_raven_exception
        monitor.handle_raven_exception = self._create_custom_handler(
            original_handler, syntax_only
        )

        try:
            await monitor.start_monitoring(output_file)
        except Exception as e:
            print(f"💥 Monitoring error: {e}")
            return False
        finally:
            self._print_final_summary(brick_ids, output_file)

        return True

    def _create_custom_handler(self, original_handler, syntax_only=False):
        """Create custom exception handler with filtering"""

        async def custom_handler(url, exception):
            # Extract brick ID
            brick_id = "unknown"
            if "brick=" in url:
                brick_id = url.split("brick=")[1].split("&")[0]

            # Update stats
            self.stats["total_exceptions"] += 1
            if brick_id not in self.stats["by_brick"]:
                self.stats["by_brick"][brick_id] = 0
            self.stats["by_brick"][brick_id] += 1

            # Check if it's a syntax error
            is_syntax_error = any(
                keyword in exception.pattern_matched.lower()
                for keyword in ["syntax", "parse", "compilation"]
            )

            if is_syntax_error:
                self.stats["syntax_errors"] += 1

            # Apply filtering
            if syntax_only and not is_syntax_error:
                return  # Skip non-syntax errors if syntax_only mode

            # Call original handler with enhanced formatting
            await self._enhanced_exception_display(
                url, exception, brick_id, is_syntax_error
            )

        return custom_handler

    async def _enhanced_exception_display(
        self, url, exception, brick_id, is_syntax_error
    ):
        """Enhanced exception display with color coding"""

        brick_info = RAVEN_BRICKS.get(brick_id, {"name": "Unknown", "priority": "LOW"})

        # Color coding based on type
        if is_syntax_error:
            header_color = "🔴"
            priority_text = "CRITICAL - SYNTAX ERROR"
        elif exception.severity == "CRITICAL":
            header_color = "🔴"
            priority_text = "CRITICAL"
        elif exception.severity == "ERROR":
            header_color = "🟠"
            priority_text = "ERROR"
        else:
            header_color = "🟡"
            priority_text = "WARNING"

        print(f"\n{'=' * 80}")
        print(
            f"{header_color} RAVEN EXCEPTION #{self.stats['total_exceptions']} - {priority_text}"
        )
        print(f"{'=' * 80}")

        # Brick information
        print(f"🧱 Brick: {brick_info['name']} ({brick_id})")
        print(f"📋 Description: {brick_info['description']}")
        print(f"⭐ Priority: {brick_info['priority']}")

        # Exception details
        print(f"⏰ Time: {exception.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🔢 Line: {exception.line_number}")
        print(f"🏷️  Type: {exception.exception_type}")
        print(f"💬 Message: {exception.exception_message}")

        # Special handling for syntax errors
        if is_syntax_error:
            print(f"\n🔴 SYNTAX ERROR ANALYSIS:")
            print(f"   Pattern: {exception.pattern_matched}")
            print(f"   ❌ Code compilation/parsing failed in brick {brick_id}")

            if "python" in exception.pattern_matched.lower():
                print(f"   🐍 Python syntax issue detected")
                print(f"   → Check for missing colons, parentheses, or indentation")
            elif "json" in exception.pattern_matched.lower():
                print(f"   📄 JSON syntax issue detected")
                print(f"   → Check for missing quotes, commas, or brackets")
            elif "javascript" in exception.pattern_matched.lower():
                print(f"   🟨 JavaScript syntax issue detected")
                print(f"   → Check for missing semicolons or brackets")
            else:
                print(f"   → Check code syntax and structure")

            print(f"   ⚡ IMMEDIATE ACTION REQUIRED!")

        # Show full stacktrace if available
        if exception.stacktrace and len(exception.stacktrace) > 1:
            print(f"\n📋 FULL STACKTRACE ({len(exception.stacktrace)} lines):")
            print(f"{'─' * 60}")
            for i, stack_line in enumerate(exception.stacktrace, 1):
                # Highlight important lines
                if any(keyword in stack_line for keyword in ["Exception:", "Error:"]):
                    print(f"🔴 {i:2d}. {stack_line}")
                elif 'File "' in stack_line and "line" in stack_line:
                    print(f"📁 {i:2d}. {stack_line}")
                elif "Traceback" in stack_line:
                    print(f"📚 {i:2d}. {stack_line}")
                else:
                    print(f"   {i:2d}. {stack_line}")
            print(f"{'─' * 60}")

        # Show app process info if available
        if exception.app_info:
            app_info = exception.app_info
            app_name = app_info.get("app_name", "unknown")
            version = app_info.get("version", "unknown")
            process = app_info.get("process", "unknown")
            print(f"🏃 App Process: {app_name}<{version}>({process})")

        # Extended context around exception
        if exception.context_lines:
            print(f"\n📝 Context Around Exception (last 8 lines):")
            print(f"{'─' * 50}")
            for line in exception.context_lines[-8:]:
                # Highlight exception-related lines
                if any(
                    keyword in line.lower()
                    for keyword in ["traceback", "exception", "error"]
                ):
                    print(f"🔍 {line}")
                else:
                    print(f"   {line}")
            print(f"{'─' * 50}")

        print(f"{'=' * 80}")

    def _print_startup_banner(self, brick_ids, output_file, syntax_only):
        """Print startup banner with configuration info"""

        print(f"🚀 RAVEN MULTI-BRICK LOG MONITOR")
        print(f"{'=' * 80}")
        print(f"📅 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🎯 Mode: {'SYNTAX ERRORS ONLY' if syntax_only else 'ALL EXCEPTIONS'}")
        print(f"🧱 Monitoring {len(brick_ids)} brick(s):")

        for i, brick_id in enumerate(brick_ids, 1):
            brick_info = RAVEN_BRICKS.get(
                brick_id, {"name": "Unknown", "priority": "LOW"}
            )
            print(
                f"   {i}. {brick_info['name']} ({brick_id}) - Priority: {brick_info['priority']}"
            )

        if output_file:
            print(f"💾 Saving to: {output_file}")

        print(
            f"🔍 Focus: Syntax errors, compilation issues, and runtime exceptions with full stacktraces"
        )
        print(f"📋 Enhanced: Complete stacktraces and extended context will be shown")
        print(f"⌨️  Press Ctrl+C to stop monitoring")
        print(f"{'=' * 80}")

    def _print_final_summary(self, brick_ids, output_file):
        """Print final monitoring summary"""

        if not self.stats["start_time"]:
            return

        duration = (datetime.now() - self.stats["start_time"]).total_seconds()

        print(f"\n{'=' * 80}")
        print(f"📊 MONITORING SUMMARY")
        print(f"{'=' * 80}")
        print(f"⏱️  Duration: {duration:.1f} seconds ({duration / 60:.1f} minutes)")
        print(f"🚨 Total Exceptions: {self.stats['total_exceptions']}")
        print(f"🔴 Syntax Errors: {self.stats['syntax_errors']}")

        if duration > 0:
            rate = self.stats["total_exceptions"] / duration * 60
            print(f"📈 Exception Rate: {rate:.2f} exceptions/minute")

        print(f"\n🧱 Exceptions by Brick:")
        for brick_id, count in self.stats["by_brick"].items():
            brick_info = RAVEN_BRICKS.get(brick_id, {"name": "Unknown"})
            print(f"   {brick_info['name']} ({brick_id}): {count}")

        if output_file and Path(output_file).exists():
            file_size = Path(output_file).stat().st_size
            print(f"\n💾 Output File: {output_file} ({file_size:,} bytes)")

        print(f"{'=' * 80}")


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Quick Start Raven Brick Log Monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python start_raven_monitoring.py                    # Monitor all bricks
    python start_raven_monitoring.py --save-to-file     # Save exceptions to file
    python start_raven_monitoring.py --syntax-only      # Only syntax errors
    python start_raven_monitoring.py --brick 3KKPiWPJZ4xiJAl0ZA1vY  # Specific brick

Brick IDs:
    3KKPiWPJZ4xiJAl0ZA1vY  - Primary Brick (Main processing)
    p29OHpShid8VxErrGxbvv  - Secondary Brick (Data processing)
    4h_HCGsl9KCkSScFhGs51  - Analysis Brick (Analysis & reporting)
        """,
    )

    parser.add_argument(
        "--brick",
        action="append",
        help="Monitor specific brick ID (can be used multiple times)",
    )

    parser.add_argument(
        "--save-to-file", action="store_true", help="Save exceptions to JSON file"
    )

    parser.add_argument(
        "--syntax-only",
        action="store_true",
        help="Only show syntax errors and compilation issues",
    )

    parser.add_argument(
        "--list-bricks", action="store_true", help="List available brick IDs and exit"
    )

    args = parser.parse_args()

    # List bricks and exit
    if args.list_bricks:
        print("Available Raven Bricks:")
        print("=" * 50)
        for brick_id, info in RAVEN_BRICKS.items():
            print(f"🧱 {info['name']}")
            print(f"   ID: {brick_id}")
            print(f"   Description: {info['description']}")
            print(f"   Priority: {info['priority']}")
            print()
        return 0

    # Validate brick IDs if specified
    brick_ids = args.brick
    if brick_ids:
        invalid_bricks = [bid for bid in brick_ids if bid not in RAVEN_BRICKS]
        if invalid_bricks:
            print(f"❌ Invalid brick IDs: {', '.join(invalid_bricks)}")
            print(f"Use --list-bricks to see available brick IDs")
            return 1

    # Create and start monitor
    monitor = RavenQuickMonitor()

    try:
        success = await monitor.start_monitoring(
            brick_ids=brick_ids,
            save_to_file=args.save_to_file,
            syntax_only=args.syntax_only,
        )
        return 0 if success else 1

    except KeyboardInterrupt:
        print(f"\n👋 Monitoring stopped by user")
        return 0
    except Exception as e:
        print(f"\n💥 Fatal error: {e}")
        return 1


if __name__ == "__main__":
    print("🌊 Raven Quick Start Log Monitor")
    print("Real-time monitoring for syntax errors and exceptions")
    print()

    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 Startup error: {e}")
        sys.exit(1)
