#!/usr/bin/env python3
"""
Async HTTP Monitor with Exception Tracking

This module provides functionality to monitor multiple HTTP endpoints asynchronously
using httpx, capturing output lines and maintaining context around exceptions.
"""

import asyncio
import httpx
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple, AsyncGenerator
from dataclasses import dataclass, field
from collections import deque
import traceback


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("http_monitor.log")],
)
logger = logging.getLogger(__name__)


@dataclass
class MonitorConfig:
    """Configuration for HTTP monitoring"""

    url: str
    interval: float = 30.0  # seconds between requests
    timeout: float = 10.0  # request timeout
    max_retries: int = 3
    context_lines: int = 10  # lines to keep before exception
    headers: Dict[str, str] = field(default_factory=dict)
    method: str = "GET"
    payload: Optional[Dict] = None


@dataclass
class ExceptionEvent:
    """Represents an exception event with context"""

    timestamp: datetime
    url: str
    exception: str
    exception_type: str
    context_lines: List[str]
    response_status: Optional[int] = None
    response_body: Optional[str] = None


class HTTPMonitor:
    """Async HTTP endpoint monitor with exception tracking"""

    def __init__(self, config: MonitorConfig):
        self.config = config
        self.context_buffer = deque(maxlen=config.context_lines)
        self.exceptions: List[ExceptionEvent] = []
        self.is_running = False
        self.client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Async context manager entry"""
        self.client = httpx.AsyncClient(timeout=self.config.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.client:
            await self.client.aclose()

    def _add_context_line(self, line: str):
        """Add a line to the context buffer"""
        timestamp = datetime.now().isoformat()
        context_line = f"[{timestamp}] {line}"
        self.context_buffer.append(context_line)

    def _capture_exception(
        self, exception: Exception, response: Optional[httpx.Response] = None
    ) -> ExceptionEvent:
        """Capture exception with context and return the event"""
        exc_event = ExceptionEvent(
            timestamp=datetime.now(),
            url=self.config.url,
            exception=str(exception),
            exception_type=type(exception).__name__,
            context_lines=list(self.context_buffer),
            response_status=response.status_code if response else None,
            response_body=response.text[:1000]
            if response
            else None,  # First 1000 chars
        )

        self.exceptions.append(exc_event)
        logger.error(
            f"Exception captured for {self.config.url}: {exc_event.exception_type} - {exc_event.exception}"
        )

        # Log context lines
        logger.info(f"Context lines for {self.config.url}:")
        for line in exc_event.context_lines:
            logger.info(f"  {line}")

        return exc_event

    async def _make_request(
        self,
    ) -> Tuple[bool, Optional[httpx.Response], Optional[ExceptionEvent]]:
        """Make HTTP request with retry logic"""
        for attempt in range(self.config.max_retries + 1):
            try:
                self._add_context_line(
                    f"Attempt {attempt + 1}/{self.config.max_retries + 1} for {self.config.method} {self.config.url}"
                )

                if self.config.method.upper() == "GET":
                    response = await self.client.get(
                        self.config.url, headers=self.config.headers
                    )
                elif self.config.method.upper() == "POST":
                    response = await self.client.post(
                        self.config.url,
                        headers=self.config.headers,
                        json=self.config.payload,
                    )
                else:
                    response = await self.client.request(
                        self.config.method,
                        self.config.url,
                        headers=self.config.headers,
                        json=self.config.payload,
                    )

                self._add_context_line(
                    f"Response: {response.status_code} from {self.config.url}"
                )

                # Check if response indicates an error
                if response.status_code >= 400:
                    error_msg = f"HTTP {response.status_code}: {response.reason_phrase}"
                    self._add_context_line(f"Error response: {error_msg}")
                    raise httpx.HTTPStatusError(
                        error_msg, request=response.request, response=response
                    )

                self._add_context_line(
                    f"Success: Content-Length={len(response.content)} bytes"
                )
                return True, response, None

            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                self._add_context_line(f"Request failed: {type(e).__name__} - {str(e)}")

                if attempt == self.config.max_retries:
                    exc_event = self._capture_exception(e, getattr(e, "response", None))
                    return False, None, exc_event
                else:
                    wait_time = 2**attempt  # Exponential backoff
                    self._add_context_line(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)

            except Exception as e:
                self._add_context_line(
                    f"Unexpected error: {type(e).__name__} - {str(e)}"
                )
                exc_event = self._capture_exception(e)
                return False, None, exc_event

        return False, None, None

    async def start_monitoring(self):
        """Start continuous monitoring"""
        self.is_running = True
        logger.info(
            f"Starting monitoring for {self.config.url} (interval: {self.config.interval}s)"
        )

        while self.is_running:
            try:
                success, response, exception_event = await self._make_request()

                if success and response:
                    # Log successful response details
                    content_preview = (
                        response.text[:200] if response.text else "No content"
                    )
                    self._add_context_line(f"Response preview: {content_preview}...")

                # Wait for next interval
                await asyncio.sleep(self.config.interval)

            except asyncio.CancelledError:
                logger.info(f"Monitoring cancelled for {self.config.url}")
                break
            except Exception as e:
                self._add_context_line(
                    f"Monitor loop error: {type(e).__name__} - {str(e)}"
                )
                exc_event = self._capture_exception(e)
                await asyncio.sleep(self.config.interval)

    async def monitor_with_exceptions(self) -> AsyncGenerator[ExceptionEvent, None]:
        """Start monitoring and yield exceptions as they occur"""
        self.is_running = True
        logger.info(
            f"Starting monitoring with exception yielding for {self.config.url} (interval: {self.config.interval}s)"
        )

        while self.is_running:
            try:
                success, response, exception_event = await self._make_request()

                # Yield exception if one occurred during request
                if exception_event:
                    yield exception_event

                if success and response:
                    # Log successful response details
                    content_preview = (
                        response.text[:200] if response.text else "No content"
                    )
                    self._add_context_line(f"Response preview: {content_preview}...")

                # Wait for next interval
                await asyncio.sleep(self.config.interval)

            except asyncio.CancelledError:
                logger.info(f"Monitoring cancelled for {self.config.url}")
                break
            except Exception as e:
                self._add_context_line(
                    f"Monitor loop error: {type(e).__name__} - {str(e)}"
                )
                exc_event = self._capture_exception(e)
                yield exc_event
                await asyncio.sleep(self.config.interval)

    def stop_monitoring(self):
        """Stop monitoring"""
        self.is_running = False
        logger.info(f"Stopping monitoring for {self.config.url}")

    def get_exceptions(self) -> List[ExceptionEvent]:
        """Get all captured exceptions"""
        return self.exceptions.copy()

    def export_exceptions(self, filename: Optional[str] = None) -> str:
        """Export exceptions to JSON file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"exceptions_{timestamp}.json"

        exceptions_data = []
        for exc in self.exceptions:
            exceptions_data.append(
                {
                    "timestamp": exc.timestamp.isoformat(),
                    "url": exc.url,
                    "exception": exc.exception,
                    "exception_type": exc.exception_type,
                    "context_lines": exc.context_lines,
                    "response_status": exc.response_status,
                    "response_body": exc.response_body,
                }
            )

        with open(filename, "w") as f:
            json.dump(exceptions_data, f, indent=2)

        logger.info(f"Exported {len(exceptions_data)} exceptions to {filename}")
        return filename


class MultiHTTPMonitor:
    """Manager for multiple HTTP monitors"""

    def __init__(self, configs: List[MonitorConfig]):
        self.configs = configs
        self.monitors: List[HTTPMonitor] = []
        self.tasks: List[asyncio.Task] = []

    async def start_all_monitors(self):
        """Start all monitors concurrently"""
        logger.info(f"Starting {len(self.configs)} HTTP monitors")

        for config in self.configs:
            monitor = HTTPMonitor(config)
            self.monitors.append(monitor)

            # Start monitor in async context
            async with monitor:
                task = asyncio.create_task(monitor.start_monitoring())
                self.tasks.append(task)

        # Wait for all tasks to complete (or be cancelled)
        try:
            await asyncio.gather(*self.tasks)
        except asyncio.CancelledError:
            logger.info("All monitoring tasks cancelled")

    async def monitor_all_with_exceptions(
        self,
    ) -> AsyncGenerator[Tuple[str, ExceptionEvent], None]:
        """Start all monitors and yield exceptions with URL as they occur"""
        logger.info(
            f"Starting {len(self.configs)} HTTP monitors with exception yielding"
        )

        # Create queues for each monitor to send exceptions
        exception_queue = asyncio.Queue()
        monitor_tasks = []

        async def monitor_single(config: MonitorConfig):
            """Monitor single endpoint and put exceptions in queue"""
            monitor = HTTPMonitor(config)
            self.monitors.append(monitor)
            async with monitor:
                async for exception in monitor.monitor_with_exceptions():
                    await exception_queue.put((config.url, exception))

        # Start all monitor tasks
        for config in self.configs:
            task = asyncio.create_task(monitor_single(config))
            monitor_tasks.append(task)
            self.tasks.append(task)

        # Yield exceptions from the queue
        try:
            while True:
                # Check if all tasks are done
                if all(task.done() for task in monitor_tasks):
                    # Drain remaining items from queue
                    while not exception_queue.empty():
                        try:
                            url, exception = exception_queue.get_nowait()
                            yield url, exception
                        except asyncio.QueueEmpty:
                            break
                    break

                try:
                    # Wait for next exception with timeout
                    url, exception = await asyncio.wait_for(
                        exception_queue.get(), timeout=1.0
                    )
                    yield url, exception
                except asyncio.TimeoutError:
                    # Check if we should continue
                    continue

        except asyncio.CancelledError:
            logger.info("Exception monitoring cancelled")
            # Cancel all monitor tasks
            for task in monitor_tasks:
                if not task.done():
                    task.cancel()
            raise

    def stop_all_monitors(self):
        """Stop all monitors"""
        logger.info("Stopping all monitors")

        for monitor in self.monitors:
            monitor.stop_monitoring()

        for task in self.tasks:
            if not task.done():
                task.cancel()

    def get_all_exceptions(self) -> Dict[str, List[ExceptionEvent]]:
        """Get exceptions from all monitors"""
        all_exceptions = {}
        for monitor in self.monitors:
            all_exceptions[monitor.config.url] = monitor.get_exceptions()
        return all_exceptions

    def export_all_exceptions(self, filename: Optional[str] = None) -> str:
        """Export all exceptions to JSON file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"all_exceptions_{timestamp}.json"

        all_data = {}
        for monitor in self.monitors:
            url = monitor.config.url
            exceptions_data = []
            for exc in monitor.exceptions:
                exceptions_data.append(
                    {
                        "timestamp": exc.timestamp.isoformat(),
                        "url": exc.url,
                        "exception": exc.exception,
                        "exception_type": exc.exception_type,
                        "context_lines": exc.context_lines,
                        "response_status": exc.response_status,
                        "response_body": exc.response_body,
                    }
                )
            all_data[url] = exceptions_data

        with open(filename, "w") as f:
            json.dump(all_data, f, indent=2)

        total_exceptions = sum(len(exceptions) for exceptions in all_data.values())
        logger.info(
            f"Exported {total_exceptions} total exceptions from {len(self.monitors)} monitors to {filename}"
        )
        return filename


async def main():
    """Example usage of the HTTP monitor"""

    # Example configurations
    configs = [
        MonitorConfig(
            url="https://httpbin.org/get",
            interval=10.0,
            context_lines=5,
            headers={"User-Agent": "HTTPMonitor/1.0"},
        ),
        MonitorConfig(
            url="https://httpbin.org/status/500",  # This will cause exceptions
            interval=15.0,
            context_lines=8,
            timeout=5.0,
        ),
        MonitorConfig(
            url="https://httpbin.org/delay/2",
            interval=20.0,
            context_lines=10,
            timeout=3.0,  # This might timeout
        ),
        MonitorConfig(
            url="https://httpbin.org/post",
            method="POST",
            interval=25.0,
            payload={"test": "data", "timestamp": datetime.now().isoformat()},
            headers={"Content-Type": "application/json"},
        ),
    ]

    # Create and start multi-monitor
    multi_monitor = MultiHTTPMonitor(configs)

    try:
        # Run for a specific duration (for demo purposes)
        await asyncio.wait_for(
            multi_monitor.start_all_monitors(), timeout=120.0
        )  # 2 minutes
    except asyncio.TimeoutError:
        logger.info("Demo timeout reached")
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        multi_monitor.stop_all_monitors()

        # Export all exceptions
        filename = multi_monitor.export_all_exceptions()

        # Print summary
        all_exceptions = multi_monitor.get_all_exceptions()
        for url, exceptions in all_exceptions.items():
            print(f"\n{url}: {len(exceptions)} exceptions")
            for exc in exceptions[-3:]:  # Show last 3 exceptions
                print(f"  - {exc.timestamp}: {exc.exception_type} - {exc.exception}")


if __name__ == "__main__":
    asyncio.run(main())
