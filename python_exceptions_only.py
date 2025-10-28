#!/usr/bin/env python3
"""
Python Exceptions Only Monitor for Raven Log Streams

This script monitors the three Raven brick log streams specifically for Python
exceptions, tracebacks, and errors. It filters out all non-Python related logs
and focuses exclusively on Python runtime issues.

Usage:
    python python_exceptions_only.py                    # Monitor all bricks for Python exceptions
    python python_exceptions_only.py --save-to-file     # Save Python exceptions to file
    python python_exceptions_only.py --brick 3KKPiWPJZ4xiJAl0ZA1vY  # Monitor specific brick
"""

import asyncio
import argparse
import signal
import sys
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

# Raven brick configurations
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


class PythonExceptionDetector:
    """Detects Python exceptions in log streams"""

    def __init__(self):
        # Python exception patterns only
        self.python_patterns = {
            "traceback_start": re.compile(
                r"(?P<app_name>\w+)<(?P<version>\d+)>\((?P<process>\d+)\)\s+Traceback\s*\(most recent call last\):",
                re.IGNORECASE,
            ),
            "python_file": re.compile(
                r"(?P<app_name>\w+)<(?P<version>\d+)>\((?P<process>\d+)\)\s+File\s+\"(?P<filename>.*?\.py)\",\s+line\s+(?P<line_num>\d+)",
                re.IGNORECASE,
            ),
            "syntax_error": re.compile(
                r"(?P<app_name>\w+)<(?P<version>\d+)>\((?P<process>\d+)\)\s+(?P<exception_type>SyntaxError):\s*(?P<message>.*?)$",
                re.IGNORECASE,
            ),
            "indentation_error": re.compile(
                r"(?P<app_name>\w+)<(?P<version>\d+)>\((?P<process>\d+)\)\s+(?P<exception_type>IndentationError|TabError):\s*(?P<message>.*?)$",
                re.IGNORECASE,
            ),
            "import_error": re.compile(
                r"(?P<app_name>\w+)<(?P<version>\d+)>\((?P<process>\d+)\)\s+(?P<exception_type>ImportError|ModuleNotFoundError):\s*(?P<message>.*?)$",
                re.IGNORECASE,
            ),
            "attribute_error": re.compile(
                r"(?P<app_name>\w+)<(?P<version>\d+)>\((?P<process>\d+)\)\s+(?P<exception_type>AttributeError):\s*(?P<message>.*?)$",
                re.IGNORECASE,
            ),
            "type_error": re.compile(
                r"(?P<app_name>\w+)<(?P<version>\d+)>\((?P<process>\d+)\)\s+(?P<exception_type>TypeError):\s*(?P<message>.*?)$",
                re.IGNORECASE,
            ),
            "value_error": re.compile(
                r"(?P<app_name>\w+)<(?P<version>\d+)>\((?P<process>\d+)\)\s+(?P<exception_type>ValueError):\s*(?P<message>.*?)$",
                re.IGNORECASE,
            ),
            "key_error": re.compile(
                r"(?P<app_name>\w+)<(?P<version>\d+)>\((?P<process>\d+)\)\s+(?P<exception_type>KeyError):\s*(?P<message>.*?)$",
                re.IGNORECASE,
            ),
            "index_error": re.compile(
                r"(?P<app_name>\w+)<(?P<version>\d+)>\((?P<process>\d+)\)\s+(?P<exception_type>IndexError):\s*(?P<message>.*?)$",
                re.IGNORECASE,
            ),
            "name_error": re.compile(
                r"(?P<app_name>\w+)<(?P<version>\d+)>\((?P<process>\d+)\)\s+(?P<exception_type>NameError):\s*(?P<message>.*?)$",
                re.IGNORECASE,
            ),
            "runtime_error": re.compile(
                r"(?P<app_name>\w+)<(?P<version>\d+)>\((?P<process>\d+)\)\s+(?P<exception_type>RuntimeError|RecursionError|MemoryError):\s*(?P<message>.*?)$",
                re.IGNORECASE,
            ),
            "general_exception": re.compile(
                r"(?P<app_name>\w+)<(?P<version>\d+)>\((?P<process>\d+)\)\s+(?P<exception_type>Exception):\s*(?P<message>.*?)$",
                re.IGNORECASE,
            ),
        }

        self.in_python_traceback = False
        self.current_stacktrace = []
        self.current_app_info = {}

    def is_python_related(self, log_line: str) -> bool:
        """Check if log line is Python-related"""
        python_indicators = [
            "Traceback (most recent call last)",
            'File "',
            '.py", line',
            "Exception:",
            "Error:",
            "SyntaxError:",
            "ImportError:",
            "AttributeError:",
            "TypeError:",
            "ValueError:",
            "KeyError:",
            "IndexError:",
            "NameError:",
        ]

        return any(indicator in log_line for indicator in python_indicators)

    def detect_python_exception(self, log_line: str) -> Optional[Dict[str, Any]]:
        """Detect Python exception in log line"""

        # Skip if not Python related
        if not self.is_python_related(log_line):
            return None

        # Check for traceback start
        if "Traceback (most recent call last)" in log_line:
            self.in_python_traceback = True
            self.current_stacktrace = [log_line.strip()]

            match = self.python_patterns["traceback_start"].search(log_line)
            if match:
                self.current_app_info = {
                    "app_name": match.group("app_name"),
                    "version": match.group("version"),
                    "process": match.group("process"),
                }

            return {
                "type": "traceback_start",
                "app_info": self.current_app_info,
                "stacktrace": self.current_stacktrace.copy(),
                "log_line": log_line.strip(),
            }

        # If in traceback, collect lines
        if self.in_python_traceback:
            self.current_stacktrace.append(log_line.strip())

            # Check for file reference
            file_match = self.python_patterns["python_file"].search(log_line)
            if file_match:
                return {
                    "type": "python_file",
                    "app_info": self.current_app_info,
                    "stacktrace": self.current_stacktrace.copy(),
                    "filename": file_match.group("filename"),
                    "line_number": file_match.group("line_num"),
                    "log_line": log_line.strip(),
                }

        # Check for actual Python exceptions
        for pattern_name, pattern in self.python_patterns.items():
            if pattern_name in ["traceback_start", "python_file"]:
                continue

            match = pattern.search(log_line)
            if match:
                if self.in_python_traceback:
                    self.current_stacktrace.append(log_line.strip())

                exception_data = {
                    "type": "python_exception",
                    "pattern": pattern_name,
                    "exception_type": match.group("exception_type"),
                    "message": match.group("message"),
                    "app_info": self.current_app_info
                    if self.in_python_traceback
                    else {
                        "app_name": match.group("app_name")
                        if "app_name" in match.groupdict()
                        else "unknown",
                        "version": match.group("version")
                        if "version" in match.groupdict()
                        else "unknown",
                        "process": match.group("process")
                        if "process" in match.groupdict()
                        else "unknown",
                    },
                    "stacktrace": self.current_stacktrace.copy()
                    if self.in_python_traceback
                    else [log_line.strip()],
                    "log_line": log_line.strip(),
                    "timestamp": datetime.now(),
                }

                # Reset traceback state after capturing exception
                if self.in_python_traceback:
                    self.in_python_traceback = False
                    self.current_stacktrace = []
                    self.current_app_info = {}

                return exception_data

        return None


class PythonOnlyMonitor:
    """Monitor specifically for Python exceptions only"""

    def __init__(self, brick_ids=None):
        self.brick_ids = brick_ids or list(RAVEN_BRICKS.keys())
        self.running = False
        self.stats = {
            "python_exceptions": 0,
            "by_type": {},
            "by_brick": {},
            "by_app_version": {},
            "by_app_name": {},
            "start_time": None,
        }

    async def monitor_brick_stream(self, brick_id: str):
        """Monitor single brick stream for Python exceptions"""
        import httpx

        url = f"https://cases.apps.raven.dtact.com/_log?brick={brick_id}&streaming"
        detector = PythonExceptionDetector()

        auth = httpx.BasicAuth("remco", "remco")
        timeout = httpx.Timeout(60.0, read=None)

        async with httpx.AsyncClient(auth=auth, timeout=timeout) as client:
            try:
                async with client.stream("GET", url) as response:
                    if response.status_code != 200:
                        print(
                            f"❌ Failed to connect to brick {brick_id}: HTTP {response.status_code}"
                        )
                        return

                    print(f"✅ Connected to brick {brick_id}")
                    buffer = ""

                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        if not self.running:
                            break

                        text_chunk = chunk.decode("utf-8", errors="replace")
                        buffer += text_chunk

                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            if line.strip():
                                exception_data = detector.detect_python_exception(line)
                                if (
                                    exception_data
                                    and exception_data["type"] == "python_exception"
                                ):
                                    await self.handle_python_exception(
                                        brick_id, exception_data
                                    )

            except Exception as e:
                print(f"❌ Error monitoring brick {brick_id}: {e}")

    async def handle_python_exception(
        self, brick_id: str, exception_data: Dict[str, Any]
    ):
        """Handle detected Python exception"""
        self.stats["python_exceptions"] += 1

        # Update stats by type
        exc_type = exception_data["exception_type"]
        if exc_type not in self.stats["by_type"]:
            self.stats["by_type"][exc_type] = 0
        self.stats["by_type"][exc_type] += 1

        # Update stats by brick
        if brick_id not in self.stats["by_brick"]:
            self.stats["by_brick"][brick_id] = 0
        self.stats["by_brick"][brick_id] += 1

        # Update stats by app version
        app_version = exception_data["app_info"].get("version", "unknown")
        if app_version not in self.stats["by_app_version"]:
            self.stats["by_app_version"][app_version] = 0
        self.stats["by_app_version"][app_version] += 1

        # Update stats by app name
        app_name = exception_data["app_info"].get("app_name", "unknown")
        if app_name not in self.stats["by_app_name"]:
            self.stats["by_app_name"][app_name] = 0
        self.stats["by_app_name"][app_name] += 1

        # Display exception
        brick_info = RAVEN_BRICKS.get(brick_id, {"name": "Unknown", "priority": "LOW"})

        print(f"\n{'=' * 80}")
        print(f"🐍 PYTHON EXCEPTION #{self.stats['python_exceptions']}")
        print(f"{'=' * 80}")
        print(f"🧱 Brick: {brick_info['name']} ({brick_id})")
        print(f"⭐ Priority: {brick_info['priority']}")
        print(f"⏰ Time: {exception_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")

        # App info with enhanced display
        app_info = exception_data["app_info"]
        app_name = app_info.get("app_name", "unknown")
        version = app_info.get("version", "unknown")
        process = app_info.get("process", "unknown")

        print(f"📱 Application: {app_name}")
        print(f"📊 Version: {version}")
        print(f"🏃 Process ID: {process}")
        print(f"🔗 Full Process: {app_name}<{version}>({process})")

        # Exception details
        print(f"🔥 Exception Type: {exception_data['exception_type']}")
        print(f"💬 Exception Message: {exception_data['message']}")
        print(f"🎯 Detection Pattern: {exception_data['pattern']}")

        # Enhanced version info display
        print(f"\n📋 APPLICATION DETAILS:")
        print(f"   🏷️  Name: {app_name}")
        print(f"   🔢 Version: {version}")
        print(f"   ⚙️  Process: {process}")

        # Version-specific analysis if available
        if version != "unknown":
            try:
                version_num = int(version)
                if version_num < 1000:
                    print(f"   ⚠️  Low version number - consider updating")
                elif version_num > 2000:
                    print(f"   ✅ Recent version detected")
            except ValueError:
                print(f"   ❓ Version format: {version}")

        # Python-specific analysis
        self.analyze_python_exception(exception_data)

        # Show stacktrace
        if exception_data["stacktrace"] and len(exception_data["stacktrace"]) > 1:
            print(
                f"\n📋 PYTHON STACKTRACE ({len(exception_data['stacktrace'])} lines):"
            )
            print(f"{'─' * 60}")
            for i, line in enumerate(exception_data["stacktrace"], 1):
                if "Traceback" in line:
                    print(f"📚 {i:2d}. {line}")
                elif 'File "' in line:
                    print(f"📁 {i:2d}. {line}")
                elif any(err in line for err in ["Exception:", "Error:"]):
                    print(f"🔴 {i:2d}. {line}")
                else:
                    print(f"   {i:2d}. {line}")
            print(f"{'─' * 60}")

        print(f"{'=' * 80}")

        # Save to file if configured
        if hasattr(self, "output_file") and self.output_file:
            await self.save_exception(exception_data, brick_id)

    def analyze_python_exception(self, exception_data: Dict[str, Any]):
        """Provide Python-specific analysis"""
        exc_type = exception_data["exception_type"].lower()
        message = exception_data["message"].lower()

        if "syntaxerror" in exc_type:
            print(f"\n🔴 PYTHON SYNTAX ERROR ANALYSIS:")
            print(f"   ❌ Python code has syntax errors")
            print(f"   → Check for missing colons, parentheses, or quotes")
            print(f"   → Verify proper indentation")
            print(f"   → Review the file and line number in stacktrace")

        elif "indentationerror" in exc_type or "taberror" in exc_type:
            print(f"\n🔴 PYTHON INDENTATION ERROR ANALYSIS:")
            print(f"   ❌ Indentation is incorrect")
            print(f"   → Check for mixed tabs and spaces")
            print(f"   → Ensure consistent indentation levels")

        elif "importerror" in exc_type or "modulenotfounderror" in exc_type:
            print(f"\n🟠 PYTHON IMPORT ERROR ANALYSIS:")
            print(f"   ❌ Module import failed")
            print(f"   → Check if module is installed")
            print(f"   → Verify module name spelling")
            print(f"   → Check Python path")

        elif "attributeerror" in exc_type:
            print(f"\n🟠 PYTHON ATTRIBUTE ERROR ANALYSIS:")
            print(f"   ❌ Object attribute access failed")
            print(f"   → Check if object has the attribute")
            print(f"   → Verify object initialization")
            print(f"   → Check for typos in attribute name")

        elif "typeerror" in exc_type:
            print(f"\n🟠 PYTHON TYPE ERROR ANALYSIS:")
            print(f"   ❌ Type mismatch or incorrect usage")
            print(f"   → Check function arguments")
            print(f"   → Verify data types")
            print(f"   → Review method calls")

        elif "valueerror" in exc_type:
            print(f"\n🟠 PYTHON VALUE ERROR ANALYSIS:")
            print(f"   ❌ Invalid value passed")
            print(f"   → Validate input data")
            print(f"   → Check data ranges and formats")

        elif "keyerror" in exc_type:
            print(f"\n🟠 PYTHON KEY ERROR ANALYSIS:")
            print(f"   ❌ Dictionary key not found")
            print(f"   → Check if key exists before access")
            print(f"   → Use .get() method for safe access")
            print(f"   → Verify key spelling and type")

        elif "indexerror" in exc_type:
            print(f"\n🟠 PYTHON INDEX ERROR ANALYSIS:")
            print(f"   ❌ List index out of bounds")
            print(f"   → Check list length before access")
            print(f"   → Add bounds validation")

        elif "nameerror" in exc_type:
            print(f"\n🟠 PYTHON NAME ERROR ANALYSIS:")
            print(f"   ❌ Variable or function not defined")
            print(f"   → Check variable spelling")
            print(f"   → Verify variable is in scope")
            print(f"   → Check for import statements")

        elif "exception" in exc_type:
            print(f"\n🟡 PYTHON GENERAL EXCEPTION ANALYSIS:")

            # Check for common patterns in message
            if "jwt" in message:
                print(f"   🔐 JWT Token Issue:")
                print(f"   → Check JWT token validity")
                print(f"   → Verify team_id in token")
                print(f"   → Check token expiration")
            elif "team_id" in message:
                print(f"   🔐 Team ID Issue:")
                print(f"   → Verify team_id parameter")
                print(f"   → Check user permissions")
            else:
                print(f"   ❌ General Python exception occurred")

    async def save_exception(self, exception_data: Dict[str, Any], brick_id: str):
        """Save exception to file"""
        # Enhanced output data with extracted app info
        app_info = exception_data["app_info"]
        output_data = {
            "brick_id": brick_id,
            "brick_name": RAVEN_BRICKS.get(brick_id, {}).get("name", "Unknown"),
            "timestamp": exception_data["timestamp"].isoformat(),
            "exception_type": exception_data["exception_type"],
            "message": exception_data["message"],
            "app_name": app_info.get("app_name", "unknown"),
            "app_version": app_info.get("version", "unknown"),
            "process_id": app_info.get("process", "unknown"),
            "full_app_info": f"{app_info.get('app_name', 'unknown')}<{app_info.get('version', 'unknown')}>({app_info.get('process', 'unknown')})",
            "app_info": exception_data["app_info"],
            "stacktrace": exception_data["stacktrace"],
            "pattern": exception_data["pattern"],
        }

        # Append to file
        with open(self.output_file, "a") as f:
            f.write(json.dumps(output_data) + "\n")

    async def start_monitoring(self, save_to_file=False):
        """Start monitoring all bricks for Python exceptions"""
        self.running = True
        self.stats["start_time"] = datetime.now()

        if save_to_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.output_file = f"python_exceptions_{timestamp}.jsonl"
            print(f"💾 Saving Python exceptions to: {self.output_file}")

        print(f"🐍 PYTHON EXCEPTIONS ONLY MONITOR")
        print(f"{'=' * 80}")
        print(f"📅 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🧱 Monitoring {len(self.brick_ids)} brick(s) for Python exceptions:")

        for i, brick_id in enumerate(self.brick_ids, 1):
            brick_info = RAVEN_BRICKS.get(
                brick_id, {"name": "Unknown", "priority": "LOW"}
            )
            print(
                f"   {i}. {brick_info['name']} ({brick_id}) - Priority: {brick_info['priority']}"
            )

        print(f"🔍 Focus: Python tracebacks, exceptions, and errors ONLY")
        print(f"🚫 Filtering out: Non-Python logs, HTTP errors, general logs")
        print(f"⌨️  Press Ctrl+C to stop monitoring")
        print(f"{'=' * 80}")

        # Start monitoring tasks for each brick
        tasks = []
        for brick_id in self.brick_ids:
            task = asyncio.create_task(self.monitor_brick_stream(brick_id))
            tasks.append(task)

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            print(f"\n🛑 Monitoring cancelled")
        finally:
            self.running = False
            self.print_final_stats()

    def print_final_stats(self):
        """Print final monitoring statistics"""
        if not self.stats["start_time"]:
            return

        duration = (datetime.now() - self.stats["start_time"]).total_seconds()

        print(f"\n{'=' * 80}")
        print(f"📊 PYTHON EXCEPTIONS MONITORING SUMMARY")
        print(f"{'=' * 80}")
        print(f"⏱️  Duration: {duration:.1f} seconds ({duration / 60:.1f} minutes)")
        print(f"🐍 Python Exceptions: {self.stats['python_exceptions']}")

        if duration > 0:
            rate = self.stats["python_exceptions"] / duration * 60
            print(f"📈 Exception Rate: {rate:.2f} Python exceptions/minute")

        if self.stats["by_type"]:
            print(f"\n🏷️  Python Exceptions by Type:")
            for exc_type, count in sorted(
                self.stats["by_type"].items(), key=lambda x: x[1], reverse=True
            ):
                print(f"   {exc_type}: {count}")

        if self.stats["by_brick"]:
            print(f"\n🧱 Python Exceptions by Brick:")
            for brick_id, count in sorted(
                self.stats["by_brick"].items(), key=lambda x: x[1], reverse=True
            ):
                brick_info = RAVEN_BRICKS.get(brick_id, {"name": "Unknown"})
                print(f"   {brick_info['name']} ({brick_id}): {count}")

        if self.stats["by_app_version"]:
            print(f"\n📊 Python Exceptions by App Version:")
            for version, count in sorted(
                self.stats["by_app_version"].items(), key=lambda x: x[1], reverse=True
            ):
                print(f"   Version {version}: {count}")

        if self.stats["by_app_name"]:
            print(f"\n📱 Python Exceptions by App Name:")
            for app_name, count in sorted(
                self.stats["by_app_name"].items(), key=lambda x: x[1], reverse=True
            ):
                print(f"   {app_name}: {count}")

        if hasattr(self, "output_file") and Path(self.output_file).exists():
            file_size = Path(self.output_file).stat().st_size
            print(f"\n💾 Output File: {self.output_file} ({file_size:,} bytes)")

        print(f"{'=' * 80}")

    def stop_monitoring(self):
        """Stop monitoring"""
        self.running = False


def setup_signal_handlers(monitor):
    """Setup signal handlers for graceful shutdown"""

    def signal_handler(signum, frame):
        print(f"\n📡 Received signal {signum}, stopping Python exception monitoring...")
        monitor.stop_monitoring()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Python Exceptions Only Monitor for Raven Bricks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python python_exceptions_only.py                    # Monitor all bricks for Python exceptions
    python python_exceptions_only.py --save-to-file     # Save Python exceptions to file
    python python_exceptions_only.py --brick 3KKPiWPJZ4xiJAl0ZA1vY  # Monitor specific brick

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
        "--save-to-file",
        action="store_true",
        help="Save Python exceptions to JSONL file",
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
    monitor = PythonOnlyMonitor(brick_ids=brick_ids)

    # Setup signal handling
    setup_signal_handlers(monitor)

    try:
        await monitor.start_monitoring(save_to_file=args.save_to_file)
        return 0
    except KeyboardInterrupt:
        print(f"\n👋 Python exception monitoring stopped")
        return 0
    except Exception as e:
        print(f"\n💥 Fatal error: {e}")
        return 1


if __name__ == "__main__":
    print("🐍 Python Exceptions Only Monitor")
    print("Monitor Raven log streams for Python exceptions exclusively")
    print("Filters out all non-Python related logs and errors")
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
