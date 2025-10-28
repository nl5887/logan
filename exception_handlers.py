#!/usr/bin/env python3
"""
Exception Handlers and Streaming Utilities for HTTP Monitor

This module provides various exception handlers and streaming utilities
to process exceptions yielded by the HTTP monitoring system.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import AsyncGenerator, Callable, Optional, Dict, Any, List
from dataclasses import asdict
from pathlib import Path

from http_monitor import ExceptionEvent

logger = logging.getLogger(__name__)


class ExceptionHandler:
    """Base class for exception handlers"""

    async def handle(self, url: str, exception: ExceptionEvent) -> None:
        """Handle an exception event"""
        raise NotImplementedError

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        pass


class LoggingExceptionHandler(ExceptionHandler):
    """Handler that logs exceptions to console/file"""

    def __init__(self, log_level: int = logging.ERROR, include_context: bool = True):
        self.log_level = log_level
        self.include_context = include_context
        self.logger = logging.getLogger(f"{__name__}.LoggingHandler")

    async def handle(self, url: str, exception: ExceptionEvent) -> None:
        """Log the exception"""
        self.logger.log(
            self.log_level,
            f"🚨 Exception from {url}: {exception.exception_type} - {exception.exception}",
        )

        if self.include_context and exception.context_lines:
            self.logger.log(self.log_level, f"Context for {url}:")
            for line in exception.context_lines[-5:]:  # Last 5 context lines
                self.logger.log(self.log_level, f"  {line}")


class FileExceptionHandler(ExceptionHandler):
    """Handler that writes exceptions to a file"""

    def __init__(self, filename: str, format: str = "json"):
        self.filename = filename
        self.format = format.lower()
        self.file_handle = None
        self.exceptions_written = 0

        if self.format not in ["json", "jsonl", "text"]:
            raise ValueError(f"Unsupported format: {format}")

    async def __aenter__(self):
        """Open file for writing"""
        self.file_handle = open(self.filename, "w")

        if self.format == "json":
            # Start JSON array
            self.file_handle.write("[\n")

        logger.info(f"Opened exception file: {self.filename} (format: {self.format})")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close file"""
        if self.file_handle:
            if self.format == "json":
                # Close JSON array
                self.file_handle.write("\n]")

            self.file_handle.close()
            logger.info(
                f"Closed exception file: {self.filename} ({self.exceptions_written} exceptions written)"
            )

    async def handle(self, url: str, exception: ExceptionEvent) -> None:
        """Write exception to file"""
        if not self.file_handle:
            raise RuntimeError("File handler not properly initialized")

        if self.format == "json":
            # JSON array format
            if self.exceptions_written > 0:
                self.file_handle.write(",\n")

            exception_data = {"url": url, **asdict(exception)}
            # Convert datetime to ISO string
            exception_data["timestamp"] = exception.timestamp.isoformat()

            json.dump(exception_data, self.file_handle, indent=2)

        elif self.format == "jsonl":
            # JSON Lines format
            exception_data = {"url": url, **asdict(exception)}
            exception_data["timestamp"] = exception.timestamp.isoformat()

            json.dump(exception_data, self.file_handle)
            self.file_handle.write("\n")

        elif self.format == "text":
            # Human-readable text format
            self.file_handle.write(f"[{exception.timestamp.isoformat()}] {url}\n")
            self.file_handle.write(
                f"  Exception: {exception.exception_type} - {exception.exception}\n"
            )
            if exception.response_status:
                self.file_handle.write(
                    f"  Response Status: {exception.response_status}\n"
                )
            if exception.context_lines:
                self.file_handle.write("  Context:\n")
                for line in exception.context_lines[-3:]:
                    self.file_handle.write(f"    {line}\n")
            self.file_handle.write("\n")

        self.file_handle.flush()
        self.exceptions_written += 1


class CallbackExceptionHandler(ExceptionHandler):
    """Handler that calls a custom callback function"""

    def __init__(self, callback: Callable[[str, ExceptionEvent], None]):
        self.callback = callback

    async def handle(self, url: str, exception: ExceptionEvent) -> None:
        """Call the callback function"""
        try:
            if asyncio.iscoroutinefunction(self.callback):
                await self.callback(url, exception)
            else:
                self.callback(url, exception)
        except Exception as e:
            logger.error(f"Error in callback handler: {e}")


class AlertExceptionHandler(ExceptionHandler):
    """Handler that triggers alerts based on exception patterns"""

    def __init__(
        self,
        alert_threshold: int = 3,
        time_window: int = 300,  # 5 minutes
        alert_callback: Optional[Callable] = None,
    ):
        self.alert_threshold = alert_threshold
        self.time_window = time_window
        self.alert_callback = alert_callback
        self.exception_history: Dict[str, List[datetime]] = {}

    async def handle(self, url: str, exception: ExceptionEvent) -> None:
        """Track exceptions and trigger alerts if threshold exceeded"""
        if url not in self.exception_history:
            self.exception_history[url] = []

        now = datetime.now()

        # Add current exception
        self.exception_history[url].append(now)

        # Clean old exceptions outside time window
        cutoff_time = now.timestamp() - self.time_window
        self.exception_history[url] = [
            exc_time
            for exc_time in self.exception_history[url]
            if exc_time.timestamp() > cutoff_time
        ]

        # Check if threshold exceeded
        if len(self.exception_history[url]) >= self.alert_threshold:
            await self._trigger_alert(url, exception)

    async def _trigger_alert(self, url: str, latest_exception: ExceptionEvent):
        """Trigger alert for URL"""
        alert_msg = (
            f"🚨 ALERT: {url} has {len(self.exception_history[url])} exceptions "
            f"in the last {self.time_window} seconds. "
            f"Latest: {latest_exception.exception_type} - {latest_exception.exception}"
        )

        logger.critical(alert_msg)

        if self.alert_callback:
            try:
                if asyncio.iscoroutinefunction(self.alert_callback):
                    await self.alert_callback(
                        url, self.exception_history[url], latest_exception
                    )
                else:
                    self.alert_callback(
                        url, self.exception_history[url], latest_exception
                    )
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")


class CompositeExceptionHandler(ExceptionHandler):
    """Handler that combines multiple handlers"""

    def __init__(self, handlers: List[ExceptionHandler]):
        self.handlers = handlers

    async def __aenter__(self):
        """Initialize all handlers"""
        for handler in self.handlers:
            await handler.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close all handlers"""
        for handler in self.handlers:
            await handler.__aexit__(exc_type, exc_val, exc_tb)

    async def handle(self, url: str, exception: ExceptionEvent) -> None:
        """Handle exception with all handlers"""
        for handler in self.handlers:
            try:
                await handler.handle(url, exception)
            except Exception as e:
                logger.error(
                    f"Error in composite handler {type(handler).__name__}: {e}"
                )


class ExceptionProcessor:
    """Processor that consumes exceptions from monitors and routes them to handlers"""

    def __init__(self, handler: ExceptionHandler):
        self.handler = handler
        self.processed_count = 0
        self.running = False

    async def process_exceptions(
        self, exception_stream: AsyncGenerator[tuple[str, ExceptionEvent], None]
    ):
        """Process exceptions from the stream"""
        self.running = True

        async with self.handler:
            async for url, exception in exception_stream:
                if not self.running:
                    break

                try:
                    await self.handler.handle(url, exception)
                    self.processed_count += 1
                except Exception as e:
                    logger.error(f"Error processing exception from {url}: {e}")

    def stop(self):
        """Stop processing"""
        self.running = False


class ExceptionFilter:
    """Filter exceptions based on various criteria"""

    def __init__(
        self,
        exception_types: Optional[List[str]] = None,
        url_patterns: Optional[List[str]] = None,
        min_severity: Optional[str] = None,
    ):
        self.exception_types = exception_types
        self.url_patterns = url_patterns
        self.min_severity = min_severity

    def should_process(self, url: str, exception: ExceptionEvent) -> bool:
        """Check if exception should be processed"""

        # Filter by exception type
        if self.exception_types:
            if exception.exception_type not in self.exception_types:
                return False

        # Filter by URL pattern
        if self.url_patterns:
            import re

            url_matches = any(re.search(pattern, url) for pattern in self.url_patterns)
            if not url_matches:
                return False

        # Filter by severity (based on HTTP status codes)
        if self.min_severity and exception.response_status:
            severity_map = {"low": 400, "medium": 500, "high": 503}
            min_code = severity_map.get(self.min_severity, 400)
            if exception.response_status < min_code:
                return False

        return True

    async def filter_stream(
        self, exception_stream: AsyncGenerator[tuple[str, ExceptionEvent], None]
    ) -> AsyncGenerator[tuple[str, ExceptionEvent], None]:
        """Filter exception stream"""
        async for url, exception in exception_stream:
            if self.should_process(url, exception):
                yield url, exception


# Utility functions for common patterns


async def log_exceptions(
    exception_stream: AsyncGenerator[tuple[str, ExceptionEvent], None],
    log_level: int = logging.ERROR,
):
    """Simple utility to log all exceptions from a stream"""
    handler = LoggingExceptionHandler(log_level=log_level)
    processor = ExceptionProcessor(handler)
    await processor.process_exceptions(exception_stream)


async def save_exceptions_to_file(
    exception_stream: AsyncGenerator[tuple[str, ExceptionEvent], None],
    filename: str,
    format: str = "json",
):
    """Simple utility to save all exceptions to a file"""
    handler = FileExceptionHandler(filename, format)
    processor = ExceptionProcessor(handler)
    await processor.process_exceptions(exception_stream)


async def alert_on_exceptions(
    exception_stream: AsyncGenerator[tuple[str, ExceptionEvent], None],
    threshold: int = 3,
    time_window: int = 300,
):
    """Simple utility to set up alerting on exception patterns"""
    handler = AlertExceptionHandler(alert_threshold=threshold, time_window=time_window)
    processor = ExceptionProcessor(handler)
    await processor.process_exceptions(exception_stream)


# Example composite handlers


def create_production_handler(
    log_file: str = "exceptions.jsonl", alert_threshold: int = 5
) -> CompositeExceptionHandler:
    """Create a production-ready composite handler"""
    return CompositeExceptionHandler(
        [
            LoggingExceptionHandler(log_level=logging.ERROR),
            FileExceptionHandler(log_file, format="jsonl"),
            AlertExceptionHandler(alert_threshold=alert_threshold),
        ]
    )


def create_debug_handler(
    debug_file: str = "debug_exceptions.json",
) -> CompositeExceptionHandler:
    """Create a debug handler with verbose logging"""
    return CompositeExceptionHandler(
        [
            LoggingExceptionHandler(log_level=logging.DEBUG, include_context=True),
            FileExceptionHandler(debug_file, format="json"),
        ]
    )


# Custom exception handlers for specific use cases


class SlackAlertHandler(ExceptionHandler):
    """Handler that sends alerts to Slack (example implementation)"""

    def __init__(self, webhook_url: str, threshold: int = 3):
        self.webhook_url = webhook_url
        self.threshold = threshold
        self.exception_counts: Dict[str, int] = {}

    async def handle(self, url: str, exception: ExceptionEvent) -> None:
        """Send Slack alert if threshold exceeded"""
        self.exception_counts[url] = self.exception_counts.get(url, 0) + 1

        if self.exception_counts[url] >= self.threshold:
            message = {
                "text": f"🚨 HTTP Monitor Alert",
                "attachments": [
                    {
                        "color": "danger",
                        "fields": [
                            {"title": "URL", "value": url, "short": True},
                            {
                                "title": "Exception",
                                "value": f"{exception.exception_type}: {exception.exception}",
                                "short": False,
                            },
                            {
                                "title": "Count",
                                "value": str(self.exception_counts[url]),
                                "short": True,
                            },
                            {
                                "title": "Time",
                                "value": exception.timestamp.isoformat(),
                                "short": True,
                            },
                        ],
                    }
                ],
            }

            # In a real implementation, you would send this to Slack
            logger.info(f"Would send Slack alert: {message}")

            # Reset counter after alert
            self.exception_counts[url] = 0


class EmailAlertHandler(ExceptionHandler):
    """Handler that sends email alerts (example implementation)"""

    def __init__(self, email_config: Dict[str, Any], threshold: int = 5):
        self.email_config = email_config
        self.threshold = threshold
        self.exception_counts: Dict[str, int] = {}

    async def handle(self, url: str, exception: ExceptionEvent) -> None:
        """Send email alert if threshold exceeded"""
        self.exception_counts[url] = self.exception_counts.get(url, 0) + 1

        if self.exception_counts[url] >= self.threshold:
            subject = f"HTTP Monitor Alert: {url}"
            body = f"""
            HTTP Monitor has detected {self.exception_counts[url]} exceptions for {url}

            Latest Exception:
            Type: {exception.exception_type}
            Message: {exception.exception}
            Time: {exception.timestamp.isoformat()}

            Context:
            {chr(10).join(exception.context_lines[-5:]) if exception.context_lines else "No context available"}
            """

            # In a real implementation, you would send this email
            logger.info(
                f"Would send email alert to {self.email_config.get('recipients', [])}"
            )
            logger.info(f"Subject: {subject}")

            # Reset counter after alert
            self.exception_counts[url] = 0
