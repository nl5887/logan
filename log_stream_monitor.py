#!/usr/bin/env python3
"""
Log Stream Monitor for Real-time Exception Detection

This module monitors streaming logs from HTTP endpoints and detects exceptions
within the log content, yielding them in real-time for immediate handling.
"""

import asyncio
import httpx
import re
import json
import logging
from datetime import datetime
from typing import AsyncGenerator, Optional, Dict, Any, List, Pattern, Callable
from dataclasses import dataclass, field
from collections import deque
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class LogStreamConfig:
    """Configuration for log stream monitoring"""

    brick_id: str
    url: str
    username: Optional[str] = None
    password: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: float = 30.0
    reconnect_delay: float = 5.0
    max_reconnects: int = 10
    context_lines: int = (
        50  # Number of log lines to keep as context (increased for stacktraces)
    )
    buffer_size: int = 8192  # Buffer size for streaming
    line_ending: str = "\n"
    encoding: str = "utf-8"
    stacktrace_context_lines: int = 20  # Additional lines to capture for stacktraces


@dataclass
class LogException:
    """Represents an exception found in logs"""

    timestamp: datetime
    log_line: str
    exception_type: str
    exception_message: str
    context_lines: List[str]
    line_number: int
    pattern_matched: str
    severity: str = "ERROR"
    metadata: Dict[str, Any] = field(default_factory=dict)
    stacktrace: List[str] = field(default_factory=list)  # Full stacktrace lines
    app_info: Dict[str, str] = field(default_factory=dict)  # App name, version, process


class ExceptionPatternMatcher:
    """Matches Python exception patterns in log lines"""

    def __init__(self):
        # Python-specific exception patterns only
        self.patterns = {
            "raven_python_traceback_start": re.compile(
                r"(?P<app_name>\w+)<(?P<version>\d+)>\((?P<process>\d+)\)\s+(?P<exception_type>Traceback)\s*\(most recent call last\):",
                re.IGNORECASE,
            ),
            "raven_python_exception": re.compile(
                r"(?P<app_name>\w+)<(?P<version>\d+)>\((?P<process>\d+)\)\s+(?P<exception_type>\w+(?:Exception|Error)):\s*(?P<message>.*?)(?:\n|$)",
                re.IGNORECASE,
            ),
            "raven_python_file": re.compile(
                r"(?P<app_name>\w+)<(?P<version>\d+)>\((?P<process>\d+)\)\s+File\s+\"(?P<filename>.*?\.py)\",\s+line\s+(?P<line_num>\d+),?\s*(?:in\s+(?P<function>.*?))?",
                re.IGNORECASE,
            ),
            "python_traceback_start": re.compile(
                r"(?P<exception_type>Traceback)\s*\(most recent call last\):",
                re.IGNORECASE,
            ),
            "python_file_line": re.compile(
                r"File\s+\"(?P<filename>.*?\.py)\",\s+line\s+(?P<line_num>\d+),?\s*(?:in\s+(?P<function>.*?))?",
                re.IGNORECASE,
            ),
            "python_exception": re.compile(
                r"(?P<exception_type>(?:AttributeError|TypeError|ValueError|NameError|KeyError|IndexError|ImportError|ModuleNotFoundError|SyntaxError|IndentationError|TabError|RuntimeError|RecursionError|MemoryError|OverflowError|ZeroDivisionError|FloatingPointError|ArithmeticError|LookupError|AssertionError|SystemError|SystemExit|KeyboardInterrupt|GeneratorExit|StopIteration|StopAsyncIteration|Exception|BaseException)):\s*(?P<message>.*?)(?:\n|$)",
                re.IGNORECASE,
            ),
        }

        self.custom_patterns = {}
        self.stacktrace_buffer = []  # Buffer to collect stacktrace lines
        self.in_stacktrace = False
        self.current_app_info = {}

    def add_custom_pattern(self, name: str, pattern: Pattern[str]):
        """Add a custom exception pattern"""
        self.custom_patterns[name] = pattern

    def match_exception(
        self, log_line: str
    ) -> Optional[tuple[str, str, str, str, Dict[str, Any]]]:
        """
        Match exception patterns in log line
        Returns: (pattern_name, exception_type, message, severity, extra_data)
        """
        # Try all patterns
        all_patterns = {**self.patterns, **self.custom_patterns}

        # Handle stacktrace collection
        stacktrace_data = None

        # Check for Python traceback start (Raven or standard format)
        if "Traceback (most recent call last)" in log_line:
            self.in_stacktrace = True
            self.stacktrace_buffer = [log_line.strip()]

            # Extract app info from Raven format if present
            raven_match = self.patterns["raven_python_traceback_start"].search(log_line)
            if raven_match:
                self.current_app_info = {
                    "app_name": raven_match.group("app_name"),
                    "version": raven_match.group("version"),
                    "process": raven_match.group("process"),
                }

            return (
                "python_traceback_start",
                "PythonTraceback",
                "Python traceback started",
                "ERROR",
                {
                    "app_info": self.current_app_info,
                    "stacktrace": self.stacktrace_buffer.copy(),
                },
            )

        # If we're in a stacktrace, collect lines
        if self.in_stacktrace:
            self.stacktrace_buffer.append(log_line.strip())

            # Check if this is a Python file reference line
            file_match = self.patterns["raven_python_file"].search(
                log_line
            ) or self.patterns["python_file_line"].search(log_line)
            if file_match:
                return (
                    "python_file_line",
                    "PythonFile",
                    log_line.strip(),
                    "INFO",
                    {
                        "app_info": self.current_app_info,
                        "stacktrace": self.stacktrace_buffer.copy(),
                    },
                )

        # Check for the actual exception line (end of stacktrace)
        for pattern_name, pattern in all_patterns.items():
            match = pattern.search(log_line)
            if match:
                groups = match.groupdict()

                exception_type = groups.get("exception_type", "UnknownException")
                message = groups.get("message", log_line.strip())
                severity = groups.get(
                    "severity", self._infer_severity(pattern_name, exception_type)
                )

                # If this looks like a Python exception and we were collecting stacktrace
                if self.in_stacktrace and pattern_name in [
                    "python_exception",
                    "raven_python_exception",
                ]:
                    self.stacktrace_buffer.append(log_line.strip())
                    stacktrace_data = {
                        "app_info": self.current_app_info,
                        "stacktrace": self.stacktrace_buffer.copy(),
                    }
                    self.in_stacktrace = False
                    self.stacktrace_buffer = []
                    severity = "ERROR"  # Python exceptions are always errors

                extra_data = stacktrace_data or {}
                if "app_name" in groups:
                    extra_data["app_info"] = {
                        "app_name": groups.get("app_name", ""),
                        "version": groups.get("version", ""),
                        "process": groups.get("process", ""),
                    }

                return pattern_name, exception_type, message, severity, extra_data

        return None

    def _infer_severity(self, pattern_name: str, exception_type: str) -> str:
        """Infer severity based on Python exception type"""
        critical_exceptions = [
            "MemoryError",
            "SystemError",
            "SystemExit",
            "KeyboardInterrupt",
            "RecursionError",
            "OverflowError",
        ]

        if exception_type in critical_exceptions:
            return "CRITICAL"
        elif (
            "python" in pattern_name.lower()
            or "exception" in exception_type.lower()
            or "error" in exception_type.lower()
        ):
            return "ERROR"
        else:
            return "INFO"

    def reset_stacktrace(self):
        """Reset stacktrace collection state"""
        self.in_stacktrace = False
        self.stacktrace_buffer = []
        self.current_app_info = {}


class LogStreamMonitor:
    """Monitor streaming logs for exceptions"""

    def __init__(self, config: LogStreamConfig):
        self.config = config
        self.pattern_matcher = ExceptionPatternMatcher()
        self.context_buffer = deque(maxlen=config.context_lines)
        self.line_number = 0
        self.exceptions_found = 0
        self.running = False
        self.client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Async context manager entry"""
        auth = None
        if self.config.username and self.config.password:
            auth = httpx.BasicAuth(self.config.username, self.config.password)

        self.client = httpx.AsyncClient(
            auth=auth,
            timeout=httpx.Timeout(
                self.config.timeout, read=None
            ),  # No read timeout for streaming
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.client:
            await self.client.aclose()

    def add_exception_pattern(
        self, name: str, pattern: str, flags: int = re.IGNORECASE
    ):
        """Add custom exception pattern"""
        compiled_pattern = re.compile(pattern, flags)
        self.pattern_matcher.add_custom_pattern(name, compiled_pattern)

    def _add_context_line(self, line: str):
        """Add line to context buffer"""
        timestamp = datetime.now().isoformat()
        self.line_number += 1
        context_line = f"[{timestamp}] Line {self.line_number}: {line.strip()}"
        self.context_buffer.append(context_line)

    async def _stream_logs(self) -> AsyncGenerator[str, None]:
        """Stream log lines from the endpoint"""
        reconnect_count = 0

        while self.running and reconnect_count < self.config.max_reconnects:
            try:
                logger.info(f"Connecting to log stream: {self.config.url}")

                async with self.client.stream(
                    "GET", self.config.url, headers=self.config.headers
                ) as response:
                    if response.status_code != 200:
                        raise httpx.HTTPStatusError(
                            f"HTTP {response.status_code}",
                            request=response.request,
                            response=response,
                        )

                    logger.info(
                        f"✅ Connected to log stream (HTTP {response.status_code})"
                    )
                    reconnect_count = 0  # Reset on successful connection

                    buffer = ""

                    async for chunk in response.aiter_bytes(
                        chunk_size=self.config.buffer_size
                    ):
                        if not self.running:
                            break

                        try:
                            text_chunk = chunk.decode(
                                self.config.encoding, errors="replace"
                            )
                            buffer += text_chunk

                            # Split buffer into lines
                            while self.config.line_ending in buffer:
                                line, buffer = buffer.split(self.config.line_ending, 1)
                                if line.strip():  # Skip empty lines
                                    yield line

                        except Exception as e:
                            logger.warning(f"Error processing chunk: {e}")
                            continue

                    # Process remaining buffer
                    if buffer.strip():
                        yield buffer

            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                reconnect_count += 1
                logger.error(
                    f"Stream connection failed (attempt {reconnect_count}): {e}"
                )

                if reconnect_count < self.config.max_reconnects:
                    logger.info(
                        f"Reconnecting in {self.config.reconnect_delay} seconds..."
                    )
                    await asyncio.sleep(self.config.reconnect_delay)
                else:
                    logger.error("Max reconnection attempts reached")
                    raise

            except Exception as e:
                logger.error(f"Unexpected error in log streaming: {e}")
                raise

    async def monitor_stream(self) -> AsyncGenerator[LogException, None]:
        """Monitor log stream and yield exceptions as they're found"""
        self.running = True
        logger.info(f"🔍 Starting log stream monitoring for exceptions")

        try:
            async for log_line in self._stream_logs():
                if not self.running:
                    break

                # Add line to context buffer
                self._add_context_line(log_line)

                # Check for exception patterns
                match_result = self.pattern_matcher.match_exception(log_line)

                if match_result:
                    pattern_name, exception_type, message, severity, extra_data = (
                        match_result
                    )

                    # Only count actual exceptions, not stacktrace lines
                    if pattern_name not in ["stacktrace_file_line"]:
                        self.exceptions_found += 1

                    # Extract stacktrace and app info from extra_data
                    stacktrace = extra_data.get("stacktrace", [])
                    app_info = extra_data.get("app_info", {})

                    # Create exception object with enhanced data
                    log_exception = LogException(
                        timestamp=datetime.now(),
                        log_line=log_line.strip(),
                        exception_type=exception_type,
                        exception_message=message,
                        context_lines=list(self.context_buffer),
                        line_number=self.line_number,
                        pattern_matched=pattern_name,
                        severity=severity,
                        stacktrace=stacktrace,
                        app_info=app_info,
                        metadata={
                            "total_exceptions_found": self.exceptions_found,
                            "stream_url": self.config.url,
                            "has_stacktrace": len(stacktrace) > 0,
                            "stacktrace_lines": len(stacktrace),
                        },
                    )

                    # Only yield Python exceptions, not intermediate stacktrace lines
                    if (
                        pattern_name not in ["python_file_line"]
                        and "python" in pattern_name.lower()
                    ):
                        logger.warning(
                            f"Python Exception detected: {exception_type} - {message}"
                        )
                        if stacktrace:
                            logger.info(
                                f"Python stacktrace captured: {len(stacktrace)} lines"
                            )
                        yield log_exception

        except asyncio.CancelledError:
            logger.info("Log stream monitoring cancelled")
        except Exception as e:
            logger.error(f"Error in log stream monitoring: {e}")
            raise
        finally:
            self.running = False

    def stop_monitoring(self):
        """Stop log stream monitoring"""
        self.running = False
        logger.info("🛑 Stopping log stream monitoring")


class MultiLogStreamMonitor:
    """Monitor multiple log streams concurrently"""

    def __init__(self, configs: List[LogStreamConfig]):
        self.configs = configs
        self.monitors: List[LogStreamMonitor] = []
        self.running = False

    async def monitor_all_streams(
        self,
    ) -> AsyncGenerator[tuple[str, LogException], None]:
        """Monitor all log streams and yield exceptions with source URL"""
        self.running = True
        logger.info(f"🌊 Starting monitoring for {len(self.configs)} log streams")

        # Create queue for exceptions from all monitors
        exception_queue = asyncio.Queue()
        monitor_tasks = []

        async def monitor_single_stream(config: LogStreamConfig):
            """Monitor single stream and put exceptions in queue"""
            monitor = LogStreamMonitor(config)
            self.monitors.append(monitor)

            async with monitor:
                async for exception in monitor.monitor_stream():
                    if not self.running:
                        break
                    await exception_queue.put((config.brick_id, config.url, exception))

        # Start all monitor tasks
        for config in self.configs:
            task = asyncio.create_task(monitor_single_stream(config))
            monitor_tasks.append(task)

        try:
            while self.running:
                try:
                    # Wait for exceptions with timeout
                    brick_id, url, exception = await asyncio.wait_for(
                        exception_queue.get(), timeout=1.0
                    )
                    yield brick_id, url, exception

                except asyncio.TimeoutError:
                    # Check if all tasks are done
                    if all(task.done() for task in monitor_tasks):
                        break
                    continue

        except asyncio.CancelledError:
            logger.info("Multi-stream monitoring cancelled")
        finally:
            # Stop all monitors
            self.running = False
            for monitor in self.monitors:
                monitor.stop_monitoring()

            # Cancel tasks
            for task in monitor_tasks:
                if not task.done():
                    task.cancel()

    def stop_all_monitors(self):
        """Stop all stream monitors"""
        self.running = False
        for monitor in self.monitors:
            monitor.stop_monitoring()


# Exception handlers for log exceptions
class LogExceptionHandler:
    """Base handler for log exceptions"""

    async def handle(self, url: str, exception: LogException) -> None:
        """Handle a log exception"""
        raise NotImplementedError

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class ConsoleLogHandler(LogExceptionHandler):
    """Handler that prints log exceptions to console"""

    def __init__(self, include_context: bool = True, max_context_lines: int = 5):
        self.include_context = include_context
        self.max_context_lines = max_context_lines

    async def handle(self, url: str, exception: LogException) -> None:
        print(f"\n🐍 PYTHON EXCEPTION DETECTED")
        print(f"   Stream: {url}")
        print(f"   Time: {exception.timestamp}")
        print(f"   Line: {exception.line_number}")
        print(f"   Severity: {exception.severity}")
        print(f"   Type: {exception.exception_type}")
        print(f"   Message: {exception.exception_message}")
        print(f"   Pattern: {exception.pattern_matched}")

        # Show app info if available
        if exception.app_info:
            app_info = exception.app_info
            print(
                f"   App: {app_info.get('app_name', 'unknown')}<{app_info.get('version', 'unknown')}>({app_info.get('process', 'unknown')})"
            )

        print(f"   Log Line: {exception.log_line}")

        # Show full Python stacktrace if available
        if exception.stacktrace:
            print(f"   📋 PYTHON STACKTRACE ({len(exception.stacktrace)} lines):")
            for i, stack_line in enumerate(exception.stacktrace, 1):
                print(f"      {i:2d}. {stack_line}")

        # Show context around the exception
        if self.include_context and exception.context_lines:
            print(
                f"   📝 Context (last {self.max_context_lines} lines before exception):"
            )
            for line in exception.context_lines[-self.max_context_lines :]:
                print(f"     {line}")


class FileLogHandler(LogExceptionHandler):
    """Handler that saves log exceptions to file"""

    def __init__(self, filename: str, format: str = "json"):
        self.filename = filename
        self.format = format.lower()
        self.file_handle = None
        self.exceptions_written = 0

    async def __aenter__(self):
        self.file_handle = open(self.filename, "w")
        if self.format == "json":
            self.file_handle.write("[\n")
        logger.info(f"Opened log exception file: {self.filename}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.file_handle:
            if self.format == "json":
                self.file_handle.write("\n]")
            self.file_handle.close()
            logger.info(
                f"Closed log exception file: {self.filename} ({self.exceptions_written} exceptions)"
            )

    async def handle(self, url: str, exception: LogException) -> None:
        if not self.file_handle:
            return

        exception_data = {
            "url": url,
            "timestamp": exception.timestamp.isoformat(),
            "line_number": exception.line_number,
            "severity": exception.severity,
            "exception_type": exception.exception_type,
            "exception_message": exception.exception_message,
            "pattern_matched": exception.pattern_matched,
            "log_line": exception.log_line,
            "stacktrace": exception.stacktrace,  # Include full stacktrace
            "app_info": exception.app_info,  # Include app information
            "context_lines": exception.context_lines[
                -15:
            ],  # Last 15 context lines (increased)
            "metadata": exception.metadata,
        }

        if self.format == "json":
            if self.exceptions_written > 0:
                self.file_handle.write(",\n")
            json.dump(exception_data, self.file_handle, indent=2)
        elif self.format == "jsonl":
            json.dump(exception_data, self.file_handle)
            self.file_handle.write("\n")

        self.file_handle.flush()
        self.exceptions_written += 1


# Example usage and main function
async def main():
    """Example usage of log stream monitoring"""

    # Configuration for the streaming log endpoint
    config = LogStreamConfig(
        url="https://cases.apps.raven.dtact.com/_log?brick=3KKPiWPJZ4xiJAl0ZA1vY&streaming",
        username="remco",
        password="remco",
        context_lines=30,  # More context for stacktraces
        timeout=60.0,
        reconnect_delay=3.0,
        max_reconnects=5,
        stacktrace_context_lines=25,  # Extra lines for stacktrace context
    )

    # Create handlers
    console_handler = ConsoleLogHandler(
        include_context=True, max_context_lines=8
    )  # More context lines
    file_handler = FileLogHandler(
        f"log_exceptions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )

    print("🌊 Starting Log Stream Monitor")
    print("=" * 50)
    print(f"Stream URL: {config.url}")
    print(f"Username: {config.username}")
    print(f"Context lines: {config.context_lines}")
    print("Press Ctrl+C to stop monitoring")
    print("=" * 50)

    async with LogStreamMonitor(config) as monitor:
        # Add some custom patterns specific to your logs
        monitor.add_exception_pattern(
            "api_error", r"(?P<exception_type>API\s*Error).*?(?P<message>.*?)(?:\n|$)"
        )
        monitor.add_exception_pattern(
            "database_error",
            r"(?P<exception_type>Database.*?Error).*?(?P<message>.*?)(?:\n|$)",
        )

        try:
            async with console_handler, file_handler:
                async for exception in monitor.monitor_stream():
                    # Handle with both handlers
                    await console_handler.handle(config.url, exception)
                    await file_handler.handle(config.url, exception)

                    # Custom logic based on exception type or severity
                    if exception.severity == "CRITICAL":
                        logger.critical(
                            f"CRITICAL exception detected: {exception.exception_type}"
                        )
                        # Here you could send alerts, notifications, etc.

        except KeyboardInterrupt:
            print("\n🛑 Monitoring stopped by user")
            monitor.stop_monitoring()
        except Exception as e:
            logger.error(f"Monitoring failed: {e}")
        finally:
            print(f"\n📊 Monitoring Summary:")
            print(f"   Total exceptions found: {monitor.exceptions_found}")
            print(f"   Total lines processed: {monitor.line_number}")


if __name__ == "__main__":
    asyncio.run(main())
