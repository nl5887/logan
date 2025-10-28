"""
Pluggable notification system for Logan code analysis.

Supports different notification providers (Slack, email, webhooks, etc.)
with thread support for progress updates.
"""

import asyncio
import json
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, asdict
import httpx


logger = logging.getLogger(__name__)


@dataclass
class NotificationMessage:
    """Represents a notification message with metadata."""

    content: str
    title: Optional[str] = None
    timestamp: Optional[datetime] = None
    thread_id: Optional[str] = None
    message_type: str = "info"  # info, success, warning, error
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


@dataclass
class AnalysisSummary:
    """Summary of analysis to be performed."""

    repository_path: str
    commit_hash: Optional[str] = None
    branch: Optional[str] = None
    task_description: str = ""
    estimated_tasks: List[str] = None
    analysis_type: str = "code_analysis"

    def __post_init__(self):
        if self.estimated_tasks is None:
            self.estimated_tasks = []


class NotificationProvider(ABC):
    """Abstract base class for notification providers."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get("enabled", True)

    @abstractmethod
    async def send_initial_notification(
        self, summary: AnalysisSummary
    ) -> Optional[str]:
        """
        Send initial notification when analysis starts.

        Returns:
            Thread ID for follow-up messages, if supported
        """
        pass

    @abstractmethod
    async def send_progress_update(self, message: NotificationMessage) -> bool:
        """
        Send a progress update message.

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    async def send_completion_notification(
        self, summary: str, success: bool = True
    ) -> bool:
        """
        Send final completion notification.

        Returns:
            True if successful, False otherwise
        """
        pass

    async def send_error_notification(
        self, error: str, context: Optional[str] = None
    ) -> bool:
        """Send error notification."""
        message = NotificationMessage(
            content=f"❌ Error: {error}"
            + (f"\n\nContext: {context}" if context else ""),
            title="Analysis Error",
            message_type="error",
        )
        return await self.send_progress_update(message)


class SlackNotificationProvider(NotificationProvider):
    """Slack notification provider using Web API for proper threading."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.webhook_url = config.get("webhook_url") or os.getenv("SLACK_WEBHOOK_URL")
        self.bot_token = config.get("bot_token") or os.getenv("SLACK_BOT_TOKEN")
        self.channel = config.get("channel", "#general")
        self.username = config.get("username", "Logan Analyzer")
        self.thread_ts = None  # For threading messages
        self.use_web_api = bool(self.bot_token)  # Use Web API if bot token available

        if not self.webhook_url and not self.bot_token and self.enabled:
            logger.warning(
                "Neither Slack webhook URL nor bot token provided. Slack notifications will be disabled."
            )
            self.enabled = False

        if self.bot_token:
            logger.info("Using Slack Web API (threading enabled)")
        elif self.webhook_url:
            logger.info("Using Slack webhooks (threading disabled)")
            logger.warning(
                "For message threading, provide SLACK_BOT_TOKEN instead of webhook"
            )

    async def _send_slack_message(
        self, payload: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Send message to Slack via webhook or Web API."""
        if not self.enabled:
            return None

        try:
            async with httpx.AsyncClient() as client:
                if self.use_web_api and self.bot_token:
                    # Use Web API for proper threading support
                    headers = {
                        "Authorization": f"Bearer {self.bot_token}",
                        "Content-Type": "application/json",
                    }
                    response = await client.post(
                        "https://slack.com/api/chat.postMessage",
                        json=payload,
                        headers=headers,
                        timeout=30.0,
                    )
                    response.raise_for_status()

                    try:
                        result = response.json()
                        if result.get("ok"):
                            return result
                        else:
                            logger.error(
                                f"Slack API error: {result.get('error', 'Unknown error')}"
                            )
                            return None
                    except json.JSONDecodeError:
                        logger.error("Invalid JSON response from Slack API")
                        return None

                elif self.webhook_url:
                    # Fallback to webhook (no threading)
                    response = await client.post(
                        self.webhook_url, json=payload, timeout=30.0
                    )
                    response.raise_for_status()

                    if response.text and response.text != "ok":
                        try:
                            return json.loads(response.text)
                        except json.JSONDecodeError:
                            pass

                    return {"status": "ok"}
                else:
                    logger.error("No Slack webhook URL or bot token available")
                    return None

        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return None

    def _format_analysis_summary(self, summary: AnalysisSummary) -> Dict[str, Any]:
        """Format analysis summary for Slack."""
        repo_name = os.path.basename(summary.repository_path.rstrip("/"))

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🔍 Starting Analysis: {repo_name}",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Repository:* `{repo_name}`"},
                    {
                        "type": "mrkdwn",
                        "text": f"*Type:* {summary.analysis_type.replace('_', ' ').title()}",
                    },
                ],
            },
        ]

        if summary.commit_hash:
            blocks[1]["fields"].append(
                {"type": "mrkdwn", "text": f"*Commit:* `{summary.commit_hash[:8]}`"}
            )

        if summary.branch:
            blocks[1]["fields"].append(
                {"type": "mrkdwn", "text": f"*Branch:* `{summary.branch}`"}
            )

        if summary.task_description:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Task:* {summary.task_description}",
                    },
                }
            )

        if summary.estimated_tasks:
            task_list = "\n".join(f"• {task}" for task in summary.estimated_tasks[:10])
            if len(summary.estimated_tasks) > 10:
                task_list += (
                    f"\n• ... and {len(summary.estimated_tasks) - 10} more tasks"
                )

            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Planned Tasks:*\n{task_list}",
                    },
                }
            )

        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Started at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
                    }
                ],
            }
        )

        return {
            "channel": self.channel,
            "username": self.username,
            "icon_emoji": ":mag:",
            "blocks": blocks,
        }

    def _get_message_emoji(self, message_type: str) -> str:
        """Get emoji for message type."""
        emoji_map = {
            "info": "ℹ️",
            "success": "✅",
            "warning": "⚠️",
            "error": "❌",
            "progress": "🔄",
        }
        return emoji_map.get(message_type, "ℹ️")

    def _convert_markdown_to_slack(self, content: str) -> str:
        """Convert standard markdown to Slack mrkdwn format."""
        import re

        # Convert tables to Slack-friendly format
        content = self._convert_tables_to_slack(content)

        # Convert code blocks (```lang\ncode\n``` -> ```\ncode\n```)
        content = re.sub(
            r"```\w*\n(.*?)\n```", r"```\n\1\n```", content, flags=re.DOTALL
        )

        # Convert headers (## Header -> *Header*)
        content = re.sub(r"^### (.+)$", r"*\1*", content, flags=re.MULTILINE)
        content = re.sub(r"^## (.+)$", r"*\1*", content, flags=re.MULTILINE)
        content = re.sub(r"^# (.+)$", r"*\1*", content, flags=re.MULTILINE)

        # Convert **bold** to *bold* - handle complex content with special chars
        # Use non-greedy matching and handle newlines/special characters
        content = re.sub(
            r"\*\*([^*]+(?:\*(?!\*)[^*]*)*)\*\*", r"*\1*", content, flags=re.DOTALL
        )

        # Inline code (`code`) is already correct for Slack
        # No change needed for `code`

        # Convert bullet points (- item -> • item)
        content = re.sub(r"^-\s+(.+)$", r"• \1", content, flags=re.MULTILINE)

        # Fix nested bullet points with proper spacing
        content = re.sub(r"^(\s*)•\s+(.+)$", r"\1• \2", content, flags=re.MULTILINE)

        # Convert numbered lists (1. item -> 1. item) - already correct
        # No change needed

        return content

    def _convert_tables_to_slack(self, content: str) -> str:
        """Convert markdown tables to Slack-friendly format."""
        import re

        def replace_table(match):
            lines = match.group(0).strip().split("\n")
            if len(lines) < 2:
                return match.group(0)

            # Parse header row
            header = [cell.strip() for cell in lines[0].split("|")[1:-1]]

            # Skip separator row (line 1)
            data_rows = []
            for line in lines[2:]:
                if line.strip():
                    row = [cell.strip() for cell in line.split("|")[1:-1]]
                    data_rows.append(row)

            # Format as structured text for Slack with better spacing
            result = []

            # Add each row with proper formatting and line breaks
            for row in data_rows:
                row_parts = []
                for i, cell in enumerate(row):
                    if i < len(header):
                        # Format as "Header: Value" with emoji conversion
                        cell_formatted = cell.replace(":white_check_mark:", "✅")
                        row_parts.append(f"*{header[i]}*: {cell_formatted}")

                # Join with line breaks instead of pipes for better readability
                result.append("\n".join(f"  {part}" for part in row_parts))

            return "\n\n".join(result)

        # Match markdown tables (basic format)
        table_pattern = r"^\|.+?\|\s*\n\|[-\s\|]+\|\s*\n(?:\|.+?\|\s*\n?)+"
        content = re.sub(table_pattern, replace_table, content, flags=re.MULTILINE)

        return content

    async def send_initial_notification(
        self, summary: AnalysisSummary
    ) -> Optional[str]:
        """Send initial notification to Slack."""
        if not self.enabled:
            return None

        # If thread already exists, don't send another initial message
        if self.thread_ts:
            logger.debug("Thread already exists, skipping initial notification")
            return self.thread_ts

        payload = self._format_analysis_summary(summary)

        # Web API payload format
        if self.use_web_api:
            # Convert webhook format to Web API format
            payload["channel"] = payload.pop("channel", self.channel)
            if "username" in payload:
                payload.pop("username")  # Not supported in Web API
            if "icon_emoji" in payload:
                payload.pop("icon_emoji")  # Use bot's default icon

        response = await self._send_slack_message(payload)

        if response and response.get("ts"):
            self.thread_ts = response["ts"]
            return self.thread_ts
        elif response and not self.use_web_api:
            # For webhooks, generate a dummy thread ID
            self.thread_ts = "webhook_thread"
            return self.thread_ts

        return None

    async def send_progress_update(self, message: NotificationMessage) -> bool:
        """Send progress update to Slack."""
        if not self.enabled:
            return False

        emoji = self._get_message_emoji(message.message_type)

        # Convert markdown to Slack mrkdwn format
        slack_content = self._convert_markdown_to_slack(message.content)

        payload = {
            "channel": self.channel,
            "text": f"{emoji} {slack_content}",
            "mrkdwn": True,
        }

        # Web API format adjustments
        if self.use_web_api:
            # Always use the established thread_ts for threading
            thread_id = self.thread_ts or message.thread_id
            if thread_id and thread_id != "webhook_thread":
                payload["thread_ts"] = thread_id
        else:
            # Webhook format
            payload["username"] = self.username
            payload["icon_emoji"] = ":gear:"

        response = await self._send_slack_message(payload)
        return response is not None

    async def send_completion_notification(
        self, summary: str, success: bool = True
    ) -> bool:
        """Send completion notification to Slack."""
        if not self.enabled:
            return False

        emoji = "✅" if success else "❌"
        status = "Completed" if success else "Failed"

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{emoji} Analysis {status}"},
            },
            {"type": "section", "text": {"type": "mrkdwn", "text": summary}},
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Finished at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
                    }
                ],
            },
        ]

        payload = {
            "channel": self.channel,
            "blocks": blocks,
            "mrkdwn": True,
        }

        # Web API vs Webhook format
        if self.use_web_api:
            if self.thread_ts and self.thread_ts != "webhook_thread":
                payload["thread_ts"] = self.thread_ts
        else:
            payload["username"] = self.username
            payload["icon_emoji"] = ":checkered_flag:"

        response = await self._send_slack_message(payload)
        return response is not None


class DummyNotificationProvider(NotificationProvider):
    """Dummy notification provider for testing and when notifications are disabled."""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config or {})
        self.messages = []  # Store messages for testing
        self.thread_id = "dummy_thread_123"

    async def send_initial_notification(
        self, summary: AnalysisSummary
    ) -> Optional[str]:
        """Log initial notification."""
        message = f"[DUMMY] Starting analysis of {summary.repository_path}"
        if summary.task_description:
            message += f" - {summary.task_description}"

        logger.info(message)
        self.messages.append(("initial", summary))
        return self.thread_id

    async def send_progress_update(self, message: NotificationMessage) -> bool:
        """Log progress update."""
        logger.info(f"[DUMMY] {message.message_type.upper()}: {message.content}")
        self.messages.append(("progress", message))
        return True

    async def send_completion_notification(
        self, summary: str, success: bool = True
    ) -> bool:
        """Log completion notification."""
        status = "SUCCESS" if success else "FAILURE"
        logger.info(f"[DUMMY] Analysis {status}: {summary}")
        self.messages.append(("completion", {"summary": summary, "success": success}))
        return True


class NotificationManager:
    """Manages multiple notification providers."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.providers: List[NotificationProvider] = []
        self.current_thread_id = None
        self.initial_notification_sent = False  # Track if initial notification was sent

        # Initialize providers based on config
        self._initialize_providers()

    def _initialize_providers(self):
        """Initialize notification providers from config."""
        providers_config = self.config.get("providers", {})

        # Slack provider
        if providers_config.get("slack", {}).get("enabled", False) or os.getenv(
            "SLACK_WEBHOOK_URL"
        ):
            slack_config = providers_config.get("slack", {})
            slack_config.setdefault("enabled", True)
            self.providers.append(SlackNotificationProvider(slack_config))

        # If no providers configured, use dummy
        if not self.providers:
            self.providers.append(DummyNotificationProvider())

    def add_provider(self, provider: NotificationProvider):
        """Add a notification provider."""
        self.providers.append(provider)

    async def send_initial_notification(self, summary: AnalysisSummary) -> bool:
        """Send initial notification through all providers (only once)."""
        # Prevent duplicate initial notifications
        if self.initial_notification_sent:
            logger.debug("Initial notification already sent, skipping duplicate")
            return True

        success = False
        for provider in self.providers:
            try:
                thread_id = await provider.send_initial_notification(summary)
                if thread_id:
                    self.current_thread_id = thread_id
                success = True
            except Exception as e:
                logger.error(
                    f"Provider {provider.__class__.__name__} failed to send initial notification: {e}"
                )

        if success:
            self.initial_notification_sent = True
        return success

    async def send_progress_update(
        self, content: str, message_type: str = "info", title: Optional[str] = None
    ) -> bool:
        """Send progress update through all providers."""
        message = NotificationMessage(
            content=content,
            title=title,
            thread_id=self.current_thread_id,
            message_type=message_type,
        )

        success = False
        for provider in self.providers:
            try:
                if await provider.send_progress_update(message):
                    success = True
            except Exception as e:
                logger.error(
                    f"Provider {provider.__class__.__name__} failed to send progress update: {e}"
                )

        return success

    async def send_completion_notification(
        self, summary: str, success: bool = True
    ) -> bool:
        """Send completion notification through all providers."""
        result = False
        for provider in self.providers:
            try:
                if await provider.send_completion_notification(summary, success):
                    result = True
            except Exception as e:
                logger.error(
                    f"Provider {provider.__class__.__name__} failed to send completion notification: {e}"
                )

        return result

    async def send_error_notification(
        self, error: str, context: Optional[str] = None
    ) -> bool:
        """Send error notification through all providers."""
        success = False
        for provider in self.providers:
            try:
                if await provider.send_error_notification(error, context):
                    success = True
            except Exception as e:
                logger.error(
                    f"Provider {provider.__class__.__name__} failed to send error notification: {e}"
                )

        return success

    def is_enabled(self) -> bool:
        """Check if any provider is enabled."""
        return any(provider.enabled for provider in self.providers)


# Configuration helper
def load_notification_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load notification configuration from file or environment."""
    config = {}

    # Try to load from file if provided
    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
        except Exception as e:
            logger.warning(
                f"Failed to load notification config from {config_path}: {e}"
            )

    # Override with environment variables
    if os.getenv("SLACK_WEBHOOK_URL") or os.getenv("SLACK_BOT_TOKEN"):
        config.setdefault("providers", {})
        config["providers"].setdefault("slack", {})
        config["providers"]["slack"].update(
            {
                "enabled": True,
                "webhook_url": os.getenv("SLACK_WEBHOOK_URL"),
                "bot_token": os.getenv("SLACK_BOT_TOKEN"),
                "channel": os.getenv("SLACK_CHANNEL", "#general"),
                "username": os.getenv("SLACK_USERNAME", "Logan Analyzer"),
            }
        )

    return config


# Factory function for easy initialization
def create_notification_manager(
    config_path: Optional[str] = None,
) -> NotificationManager:
    """Create and configure notification manager."""
    config = load_notification_config(config_path)
    return NotificationManager(config)
