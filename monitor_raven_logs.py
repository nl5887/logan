#!/usr/bin/env python3
"""
Raven Log Stream Monitor

Monitor the Raven application log stream for exceptions and errors in real-time.
This script connects to the streaming log endpoint and processes log entries
to detect and handle exceptions as they occur.

Usage:
    python monitor_raven_logs.py
    python monitor_raven_logs.py --context 20 --output exceptions.json
"""

import asyncio
import argparse
import signal
import sys
import json
from datetime import datetime
from typing import Optional
from pathlib import Path

from log_stream_monitor import (
    LogStreamConfig,
    LogStreamMonitor,
    LogException,
    ConsoleLogHandler,
    FileLogHandler,
)

BASE_URL = "https://cases.apps.raven.dtact.com/_log?brick={brick_id}&streaming"

# Default configuration for Raven log streams
RAVEN_BRICK_IDS = [
    "3KKPiWPJZ4xiJAl0ZA1vY",  # Original brick
    "p29OHpShid8VxErrGxbvv",  # Additional brick 1
    "4h_HCGsl9KCkSScFhGs51",  # Additional brick 2
]

RAVEN_BASE_CONFIG = {
    "username": "remco",
    "password": "remco",
    "context_lines": 50,  # Increased for better stacktrace context
    "timeout": 120.0,
    "reconnect_delay": 5.0,
    "max_reconnects": 10,
    "stacktrace_context_lines": 30,  # Additional lines for stacktrace capture
}


class RavenLogMonitor:
    """Specialized monitor for Raven application logs from multiple bricks"""

    def __init__(self, brick_ids=None, config_override=None):
        # Use provided brick IDs or default ones
        self.brick_ids = brick_ids or RAVEN_BRICK_IDS

        # Create configs for all bricks
        self.configs = []
        base_config = RAVEN_BASE_CONFIG.copy()
        if config_override:
            base_config.update(config_override)

        for brick_id in self.brick_ids:
            config_data = base_config.copy()
            config_data["brick_id"] = brick_id
            config_data["url"] = BASE_URL.format(brick_id=brick_id)
            self.configs.append(LogStreamConfig(**config_data))

        self.monitors = []
        self.running = False
        self.stats = {
            "exceptions_found": 0,
            "start_time": None,
            "exceptions_by_type": {},
            "exceptions_by_severity": {},
            "exceptions_by_brick": {},
        }

    def setup_custom_patterns(self, monitor: LogStreamMonitor):
        """Add Python-specific exception patterns for Raven logs"""

        # Python-specific patterns for Raven app format
        monitor.add_exception_pattern(
            "raven_python_syntax_error",
            r"(?P<app_name>\w+)<(?P<version>\d+)>\((?P<process>\d+)\)\s+(?P<exception_type>SyntaxError):\s*(?P<message>.*?)(?:\n|$)",
        )

        monitor.add_exception_pattern(
            "raven_python_indentation_error",
            r"(?P<app_name>\w+)<(?P<version>\d+)>\((?P<process>\d+)\)\s+(?P<exception_type>IndentationError|TabError):\s*(?P<message>.*?)(?:\n|$)",
        )

        monitor.add_exception_pattern(
            "raven_python_import_error",
            r"(?P<app_name>\w+)<(?P<version>\d+)>\((?P<process>\d+)\)\s+(?P<exception_type>ImportError|ModuleNotFoundError):\s*(?P<message>.*?)(?:\n|$)",
        )

        monitor.add_exception_pattern(
            "raven_python_attribute_error",
            r"(?P<app_name>\w+)<(?P<version>\d+)>\((?P<process>\d+)\)\s+(?P<exception_type>AttributeError):\s*(?P<message>.*?)(?:\n|$)",
        )

        monitor.add_exception_pattern(
            "raven_python_type_error",
            r"(?P<app_name>\w+)<(?P<version>\d+)>\((?P<process>\d+)\)\s+(?P<exception_type>TypeError):\s*(?P<message>.*?)(?:\n|$)",
        )

        monitor.add_exception_pattern(
            "raven_python_value_error",
            r"(?P<app_name>\w+)<(?P<version>\d+)>\((?P<process>\d+)\)\s+(?P<exception_type>ValueError):\s*(?P<message>.*?)(?:\n|$)",
        )

        monitor.add_exception_pattern(
            "raven_python_key_error",
            r"(?P<app_name>\w+)<(?P<version>\d+)>\((?P<process>\d+)\)\s+(?P<exception_type>KeyError):\s*(?P<message>.*?)(?:\n|$)",
        )

        monitor.add_exception_pattern(
            "raven_python_index_error",
            r"(?P<app_name>\w+)<(?P<version>\d+)>\((?P<process>\d+)\)\s+(?P<exception_type>IndexError):\s*(?P<message>.*?)(?:\n|$)",
        )

        monitor.add_exception_pattern(
            "raven_python_general_exception",
            r"(?P<app_name>\w+)<(?P<version>\d+)>\((?P<process>\d+)\)\s+(?P<exception_type>Exception):\s*(?P<message>.*?)(?:\n|$)",
        )

    async def handle_raven_exception(
        self, brick_id: str, url: str, exception: LogException
    ):
        """Handle Raven-specific exception with custom logic"""

        # Update statistics
        self.stats["exceptions_found"] += 1

        exc_type = exception.exception_type
        if exc_type not in self.stats["exceptions_by_type"]:
            self.stats["exceptions_by_type"][exc_type] = 0
        self.stats["exceptions_by_type"][exc_type] += 1

        severity = exception.severity
        if severity not in self.stats["exceptions_by_severity"]:
            self.stats["exceptions_by_severity"][severity] = 0
        self.stats["exceptions_by_severity"][severity] += 1

        # Track by brick
        if brick_id not in self.stats["exceptions_by_brick"]:
            self.stats["exceptions_by_brick"][brick_id] = 0
        self.stats["exceptions_by_brick"][brick_id] += 1

        # Raven-specific handling logic
        print(f"\n{'=' * 80}")
        print(f"🐍 PYTHON EXCEPTION #{self.stats['exceptions_found']}")
        print(f"{'=' * 80}")
        print(f"🧱 Brick ID: {brick_id}")
        print(f"⏰ Time: {exception.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📍 Line: {exception.line_number}")
        print(f"🔥 Severity: {exception.severity}")
        print(f"🏷️  Type: {exception.exception_type}")
        print(f"💬 Message: {exception.exception_message}")
        print(f"🎯 Pattern: {exception.pattern_matched}")

        # Show app info if available (cases<1335>(112544))
        if exception.app_info:
            app_info = exception.app_info
            app_name = app_info.get("app_name", "unknown")
            version = app_info.get("version", "unknown")
            process = app_info.get("process", "unknown")
            print(f"🏃 App Process: {app_name}<{version}>({process})")

        print(f"📝 Log Line: {exception.log_line}")

        # Show full stacktrace if available
        if exception.stacktrace and len(exception.stacktrace) > 1:
            print(f"\n📋 FULL STACKTRACE ({len(exception.stacktrace)} lines):")
            print(f"{'─' * 60}")
            for i, stack_line in enumerate(exception.stacktrace, 1):
                # Highlight the actual exception line
                if any(keyword in stack_line for keyword in ["Exception:", "Error:"]):
                    print(f"🔴 {i:2d}. {stack_line}")
                elif 'File "' in stack_line and "line" in stack_line:
                    print(f"📁 {i:2d}. {stack_line}")
                elif "Traceback" in stack_line:
                    print(f"📚 {i:2d}. {stack_line}")
                else:
                    print(f"   {i:2d}. {stack_line}")
            print(f"{'─' * 60}")

        # Show extended context around the exception
        if exception.context_lines:
            print(f"\n📝 Context Around Exception (last 10 lines):")
            print(f"{'─' * 60}")
            for line in exception.context_lines[-10:]:
                # Highlight lines that contain traceback or exception info
                if any(
                    keyword in line.lower()
                    for keyword in ["traceback", "exception", "error"]
                ):
                    print(f"🔍 {line}")
                else:
                    print(f"   {line}")
            print(f"{'─' * 60}")

        # Python Exception Type Analysis
        exc_type = exception.exception_type.lower()

        if "syntaxerror" in exc_type:
            print(f"\n🔴 PYTHON SYNTAX ERROR!")
            print(f"   ❌ Python code has syntax errors in brick {brick_id}")
            print(f"   → Check for missing colons, parentheses, or quotes")
            print(f"   → Verify proper indentation")
            print(f"   → Look at file 'main.py' line references in stacktrace")

        elif "indentationerror" in exc_type or "taberror" in exc_type:
            print(f"\n🔴 PYTHON INDENTATION ERROR!")
            print(f"   ❌ Python indentation is incorrect in brick {brick_id}")
            print(f"   → Check for mixed tabs and spaces")
            print(f"   → Verify consistent indentation levels")

        elif "importerror" in exc_type or "modulenotfounderror" in exc_type:
            print(f"\n🔴 PYTHON IMPORT ERROR!")
            print(f"   ❌ Python module import failed in brick {brick_id}")
            print(f"   → Check if required modules are installed")
            print(f"   → Verify module names and paths")

        elif "attributeerror" in exc_type:
            print(f"\n🟠 PYTHON ATTRIBUTE ERROR!")
            print(f"   ❌ Object attribute access failed in brick {brick_id}")
            print(f"   → Check if object has the expected attribute")
            print(f"   → Verify object is properly initialized")

        elif "typeerror" in exc_type:
            print(f"\n🟠 PYTHON TYPE ERROR!")
            print(f"   ❌ Type mismatch or incorrect usage in brick {brick_id}")
            print(f"   → Check function arguments and types")
            print(f"   → Verify object methods are called correctly")

        elif "valueerror" in exc_type:
            print(f"\n🟠 PYTHON VALUE ERROR!")
            print(f"   ❌ Invalid value passed to function in brick {brick_id}")
            print(f"   → Check input validation")
            print(f"   → Verify data format and ranges")

        elif "keyerror" in exc_type:
            print(f"\n🟠 PYTHON KEY ERROR!")
            print(f"   ❌ Dictionary key not found in brick {brick_id}")
            print(f"   → Check if dictionary contains expected keys")
            print(f"   → Add key existence validation")

        elif "indexerror" in exc_type:
            print(f"\n🟠 PYTHON INDEX ERROR!")
            print(f"   ❌ List/array index out of bounds in brick {brick_id}")
            print(f"   → Check list length before accessing elements")
            print(f"   → Add bounds checking")

        elif "exception" in exc_type:
            print(f"\n🟡 PYTHON GENERAL EXCEPTION!")
            print(f"   ❌ General Python exception in brick {brick_id}")

            # Check for specific common issues
            if "jwt" in exception.exception_message.lower():
                print(f"   🔐 JWT related: Check token validity and team_id")
            elif "team_id" in exception.exception_message.lower():
                print(f"   🔐 Team ID issue: Verify JWT token contains valid team_id")

        else:
            print(f"\n🟡 PYTHON EXCEPTION: {exception.exception_type}")
            print(f"   ❌ Python exception occurred in brick {brick_id}")

        print(f"{'=' * 80}")

        # extract the brick
        """
        severity
        message
        app
        type
        line
        filename
        brick_id
        """

    async def start_monitoring(self, output_file: Optional[str] = None):
        """Start monitoring Raven logs from multiple bricks"""
        from log_stream_monitor import MultiLogStreamMonitor

        self.running = True
        self.stats["start_time"] = datetime.now()

        # Setup handlers
        handlers = [ConsoleLogHandler(include_context=False)]

        if output_file:
            file_handler = FileLogHandler(output_file, format="json")
            handlers.append(file_handler)

        print(f"🌊 Starting Raven Multi-Brick Log Stream Monitor")
        print(f"{'=' * 60}")
        print(f"Monitoring {len(self.brick_ids)} brick streams:")
        for i, brick_id in enumerate(self.brick_ids, 1):
            print(f"  {i}. Brick: {brick_id}")
        print(f"Username: {self.configs[0].username}")
        print(f"Context lines: {self.configs[0].context_lines}")
        print(f"Stacktrace context: {self.configs[0].stacktrace_context_lines}")
        print(f"Timeout: {self.configs[0].timeout}s")
        print(f"Max reconnects: {self.configs[0].max_reconnects}")
        if output_file:
            print(f"Output file: {output_file}")
        print(f"{'=' * 60}")
        print(
            f"🔍 Monitoring for SYNTAX ERRORS and EXCEPTIONS with FULL STACKTRACES..."
        )
        print(f"🔴 Priority: Syntax errors and stacktraces will be highlighted")
        print(f"📋 Full context and stacktraces will be captured and displayed")
        print(f"Press Ctrl+C to stop monitoring")
        print(f"{'=' * 60}")

        # Create multi-stream monitor
        multi_monitor = MultiLogStreamMonitor(self.configs)

        # Setup custom patterns for all monitors
        for monitor in multi_monitor.monitors:
            self.setup_custom_patterns(monitor)

        try:
            # Initialize file handlers
            file_handlers = [h for h in handlers if isinstance(h, FileLogHandler)]
            for handler in file_handlers:
                await handler.__aenter__()

            # Process the exception stream from all bricks
            async for brick_id, url, exception in multi_monitor.monitor_all_streams():
                if not self.running:
                    break

                # Handle with custom Raven logic
                await self.handle_raven_exception(brick_id, url, exception)

                # Handle with all configured handlers
                for handler in handlers:
                    await handler.handle(url, exception)

        except KeyboardInterrupt:
            print(f"\n🛑 Monitoring stopped by user")
        except Exception as e:
            print(f"\n💥 Monitoring error: {e}")
            raise
        finally:
            # Cleanup file handlers
            for handler in file_handlers:
                await handler.__aexit__(None, None, None)

            self.running = False
            multi_monitor.stop_all_monitors()

    def stop_monitoring(self):
        """Stop monitoring"""
        self.running = False
        for monitor in self.monitors:
            monitor.stop_monitoring()

    def print_final_stats(self):
        """Print final monitoring statistics"""
        if not self.stats["start_time"]:
            return

        duration = (datetime.now() - self.stats["start_time"]).total_seconds()

        print(f"\n{'=' * 60}")
        print(f"📊 RAVEN LOG MONITORING SUMMARY")
        print(f"{'=' * 60}")
        print(f"⏱️  Duration: {duration:.1f} seconds")
        print(f"🚨 Total exceptions: {self.stats['exceptions_found']}")

        if duration > 0:
            rate = self.stats["exceptions_found"] / duration * 60
            print(f"📈 Exception rate: {rate:.2f} exceptions/minute")

        if self.stats["exceptions_by_type"]:
            print(f"\n🏷️  Exceptions by type:")
            for exc_type, count in sorted(
                self.stats["exceptions_by_type"].items(),
                key=lambda x: x[1],
                reverse=True,
            ):
                print(f"   {exc_type}: {count}")

        if self.stats["exceptions_by_severity"]:
            print(f"\n🔥 Exceptions by severity:")
            for severity, count in sorted(
                self.stats["exceptions_by_severity"].items(),
                key=lambda x: x[1],
                reverse=True,
            ):
                print(f"   {severity}: {count}")

        if self.stats["exceptions_by_brick"]:
            print(f"\n🧱 Exceptions by brick:")
            for brick_id, count in sorted(
                self.stats["exceptions_by_brick"].items(),
                key=lambda x: x[1],
                reverse=True,
            ):
                print(f"   {brick_id}: {count}")

        print(f"{'=' * 60}")


def setup_signal_handlers(monitor: RavenLogMonitor):
    """Setup signal handlers for graceful shutdown"""

    def signal_handler(signum, frame):
        print(f"\n📡 Received signal {signum}, shutting down gracefully...")
        monitor.stop_monitoring()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Monitor Raven application logs for exceptions"
    )

    parser.add_argument(
        "--output", "-o", help="Output file for exceptions (JSON format)"
    )

    parser.add_argument(
        "--context",
        "-c",
        type=int,
        default=50,
        help="Number of context lines to keep (default: 50)",
    )

    parser.add_argument(
        "--timeout",
        "-t",
        type=float,
        default=120.0,
        help="Connection timeout in seconds (default: 120.0)",
    )

    parser.add_argument(
        "--username",
        "-u",
        default="remco",
        help="Username for authentication (default: remco)",
    )

    parser.add_argument(
        "--password",
        "-p",
        default="remco",
        help="Password for authentication (default: remco)",
    )

    parser.add_argument(
        "--reconnect-delay",
        type=float,
        default=5.0,
        help="Delay between reconnection attempts (default: 5.0)",
    )

    parser.add_argument(
        "--max-reconnects",
        type=int,
        default=10,
        help="Maximum reconnection attempts (default: 10)",
    )

    parser.add_argument(
        "--bricks",
        nargs="+",
        help="Specific brick IDs to monitor (default: all configured bricks)",
    )

    args = parser.parse_args()

    # Override configuration with command line arguments
    config_override = {
        "context_lines": args.context,
        "timeout": args.timeout,
        "username": args.username,
        "password": args.password,
        "reconnect_delay": args.reconnect_delay,
        "max_reconnects": args.max_reconnects,
    }

    # Use specific bricks if provided
    brick_ids = args.bricks if args.bricks else None

    # Create monitor
    monitor = RavenLogMonitor(brick_ids=brick_ids, config_override=config_override)

    # Setup signal handling
    setup_signal_handlers(monitor)

    try:
        await monitor.start_monitoring(args.output)
    except KeyboardInterrupt:
        print("\n👋 Monitoring stopped")
    except Exception as e:
        print(f"\n💥 Fatal error: {e}")
        return 1
    finally:
        monitor.print_final_stats()

    return 0


if __name__ == "__main__":
    print("🏠 Raven Multi-Brick Log Stream Monitor")
    print(
        "Monitor real-time log streams from multiple bricks for syntax errors and exceptions"
    )
    print("🔴 Special focus on syntax errors and compilation issues")
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
