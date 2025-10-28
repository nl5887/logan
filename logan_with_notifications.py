"""
Logan Assistant with integrated notification system.

This version extends the original Logan assistant with clean notifications
that integrate with the existing callback system for LLM responses.
"""

import asyncio
import os
import sys
from typing import List, Optional, Dict, Any

# Import the original Logan classes and functions
from logan import LoganAssistant as BaseLoganAssistant, AWS_AVAILABLE
from notifications import (
    NotificationManager,
    AnalysisSummary,
    create_notification_manager,
    DummyNotificationProvider,
)


class LoganAssistantWithNotifications(BaseLoganAssistant):
    """Enhanced Logan Assistant with notification support."""

    def __init__(
        self,
        model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0",
        max_iterations: int = 5,
        debug_mode: bool = False,
        notification_config_path: Optional[str] = None,
        enable_notifications: bool = True,
    ):
        # Initialize the base Logan assistant
        super().__init__(model_id, max_iterations, debug_mode)

        # Always initialize a notification manager (dummy if disabled)
        if enable_notifications:
            self.notification_manager = create_notification_manager(
                notification_config_path
            )
        else:
            # Use dummy notification manager when disabled
            self.notification_manager = NotificationManager()
            self.notification_manager.add_provider(DummyNotificationProvider())

        # Track analysis state
        self.current_analysis: Optional[AnalysisSummary] = None
        self.analysis_started = False

    def _initialize_bedrock(self):
        """Override to add our notification callback to the LLM."""
        # Call parent initialization first
        llm = super()._initialize_bedrock()

        if llm is None:
            return None

        # Add notification callback if enabled
        if self.notification_manager.is_enabled():
            try:
                from langchain_core.callbacks import BaseCallbackHandler

                class NotificationCallbackHandler(BaseCallbackHandler):
                    def __init__(self, notification_manager):
                        self.notification_manager = notification_manager
                        self.pending_notifications = []
                        print("🐛 [NOTIFICATION] Callback handler created")

                    def on_llm_end(self, response, **kwargs):
                        """Called when LLM completes - send the response to notifications."""
                        print(f"🐛 [NOTIFICATION] ========== LLM END CALLED ==========")
                        print(f"🐛 [NOTIFICATION] Response type: {type(response)}")
                        print(
                            f"🐛 [NOTIFICATION] Response dir: {[attr for attr in dir(response) if not attr.startswith('_')]}"
                        )

                        if hasattr(response, "content"):
                            print(
                                f"🐛 [NOTIFICATION] Response.content type: {type(response.content)}"
                            )
                            print(
                                f"🐛 [NOTIFICATION] Response.content: {str(response.content)[:200]}..."
                            )

                        if hasattr(response, "generations"):
                            print(
                                f"🐛 [NOTIFICATION] Response.generations: {len(response.generations)} generations"
                            )
                            for i, gen in enumerate(response.generations):
                                print(
                                    f"🐛 [NOTIFICATION] Generation {i}: {len(gen)} choices"
                                )
                                for j, choice in enumerate(gen):
                                    print(
                                        f"🐛 [NOTIFICATION] Choice {j} type: {type(choice)}"
                                    )
                                    if hasattr(choice, "text"):
                                        print(
                                            f"🐛 [NOTIFICATION] Choice {j} text: {str(choice.text)[:100]}..."
                                        )
                                    if hasattr(choice, "message"):
                                        print(
                                            f"🐛 [NOTIFICATION] Choice {j} message type: {type(choice.message)}"
                                        )
                                        if hasattr(choice.message, "content"):
                                            print(
                                                f"🐛 [NOTIFICATION] Choice {j} message.content: {str(choice.message.content)[:100]}..."
                                            )

                        try:
                            # Extract content from response
                            content = ""
                            if hasattr(response, "content"):
                                content = str(response.content)
                                print(
                                    f"🐛 [NOTIFICATION] Extracted from response.content: {content[:100]}..."
                                )
                            elif hasattr(response, "generations"):
                                for gen in response.generations:
                                    for choice in gen:
                                        if hasattr(choice, "text") and choice.text:
                                            content += choice.text
                                            print(
                                                f"🐛 [NOTIFICATION] Added choice.text: {choice.text[:50]}..."
                                            )
                                        elif hasattr(choice, "message") and hasattr(
                                            choice.message, "content"
                                        ):
                                            content += str(choice.message.content)
                                            print(
                                                f"🐛 [NOTIFICATION] Added choice.message.content: {str(choice.message.content)[:50]}..."
                                            )

                            print(
                                f"🐛 [NOTIFICATION] Final content length: {len(content)}"
                            )
                            print(
                                f"🐛 [NOTIFICATION] Final content preview: {content[:200]}..."
                            )

                            # Store notifications to be sent later
                            if content.strip():
                                print(f"🐛 [NOTIFICATION] ✅ STORING FOR SLACK")
                                self.pending_notifications.append(
                                    ("llm_response", content.strip())
                                )
                            else:
                                print(f"🐛 [NOTIFICATION] ❌ NO CONTENT TO SEND")

                        except Exception as e:
                            print(f"🐛 [NOTIFICATION] Exception: {e}")
                            import traceback

                            traceback.print_exc()

                        print(
                            f"🐛 [NOTIFICATION] ========== LLM END FINISHED =========="
                        )

                    def on_tool_start(self, serialized, input_str, **kwargs):
                        """Called when a tool starts executing."""
                        try:
                            tool_name = serialized.get("name", "Unknown tool")
                            self.pending_notifications.append(
                                ("tool_start", f"🔧 Running tool: {tool_name}")
                            )
                        except Exception:
                            pass

                    def on_tool_end(self, output, **kwargs):
                        """Called when a tool finishes executing."""
                        try:
                            # Send tool output if it's meaningful and not too long
                            output_str = str(output).strip()
                            if output_str and len(output_str) > 0:
                                # Truncate long outputs
                                if len(output_str) > 300:
                                    output_str = output_str[:300] + "..."
                                self.pending_notifications.append(
                                    ("tool_result", f"📋 Tool result: {output_str}")
                                )
                        except Exception:
                            pass

                # Get existing callbacks and add our notification handler
                existing_callbacks = []
                if hasattr(llm, "_default_params") and llm._default_params:
                    existing_callbacks = llm._default_params.get("callbacks", [])

                notification_handler = NotificationCallbackHandler(
                    self.notification_manager
                )
                all_callbacks = existing_callbacks + [notification_handler]

                print(f"🐛 [NOTIFICATION] Adding callback handler to LLM")
                llm = llm.with_config(callbacks=all_callbacks)
                print(f"🐛 [NOTIFICATION] LLM configured with callbacks")

            except Exception as e:
                print(f"🐛 [NOTIFICATION] Error adding callbacks: {e}")

        return llm

    async def send_pending_notifications(self):
        """Send all pending notifications that were captured during LLM execution."""
        if hasattr(self, "llm") and self.llm and hasattr(self.llm, "_default_params"):
            callbacks = self.llm._default_params.get("callbacks", [])
            for callback in callbacks:
                if (
                    hasattr(callback, "pending_notifications")
                    and callback.pending_notifications
                ):
                    print(
                        f"🐛 [NOTIFICATION] Sending {len(callback.pending_notifications)} pending notifications"
                    )
                    for msg_type, content in callback.pending_notifications:
                        try:
                            if msg_type == "llm_response":
                                await self.notification_manager.send_progress_update(
                                    content, "info"
                                )
                            elif msg_type == "tool_start":
                                await self.notification_manager.send_progress_update(
                                    content, "progress"
                                )
                            elif msg_type == "tool_result":
                                await self.notification_manager.send_progress_update(
                                    content, "success"
                                )
                            print(f"🐛 [NOTIFICATION] ✅ Sent: {msg_type}")
                        except Exception as e:
                            print(f"🐛 [NOTIFICATION] Failed to send {msg_type}: {e}")
                    callback.pending_notifications.clear()

    async def start_analysis_notification(self, task_description: str) -> None:
        """Send initial notification when starting analysis."""
        if self.analysis_started:
            return

        # Get repository information
        repo_url = os.getenv("REPOSITORY_URL", "")
        commit_id = os.getenv("COMMIT_ID")
        branch = os.getenv("REPOSITORY_BRANCH", "main")

        # Create analysis summary
        self.current_analysis = AnalysisSummary(
            repository_path=repo_url or "Local Repository",
            commit_hash=commit_id,
            branch=branch if not commit_id else None,
            task_description=task_description,
            estimated_tasks=[],
            analysis_type="code_analysis",
        )

        # Send initial notification
        try:
            await self.notification_manager.send_initial_notification(
                self.current_analysis
            )
            self.analysis_started = True
        except Exception as e:
            print(f"⚠️  Failed to send initial notification: {e}")

    async def send_completion_notification(self, summary: str = None) -> None:
        """Send final completion notification."""

        try:
            # Create summary with repository info
            if not summary:
                summary = "Analysis completed"

            # Add repository context if available
            if self.current_analysis:
                repo_info = []
                if self.current_analysis.commit_hash:
                    repo_info.append(f"Commit: {self.current_analysis.commit_hash[:8]}")
                if self.current_analysis.branch:
                    repo_info.append(f"Branch: {self.current_analysis.branch}")
                if self.current_analysis.repository_path:
                    repo_info.append(
                        f"Repository: {self.current_analysis.repository_path}"
                    )

                if repo_info:
                    summary += "\n\n📍 " + " | ".join(repo_info)

            await self.notification_manager.send_completion_notification(
                summary, success=True
            )
        except Exception as e:
            print(f"⚠️  Failed to send completion notification: {e}")

    async def stream_response_with_notifications(self, user_input: str) -> None:
        """Stream response with notification integration."""
        # Send initial notification
        await self.start_analysis_notification(user_input)

        try:
            # Call the original stream_response method (outputs to console normally)
            # The notification callback will automatically capture LLM responses
            await self.stream_response(user_input)

            # Send all pending notifications that were captured
            await self.send_pending_notifications()

            # Send completion notification
            await self.send_completion_notification()

        except Exception as e:
            # Send error notification
            try:
                await self.notification_manager.send_error_notification(
                    str(e), f"Error during analysis of: {user_input}"
                )
            except:
                pass  # Don't fail if notification fails
            # Re-raise the original exception
            raise

    async def run_interactive_with_notifications(self) -> None:
        """Run interactive mode with notification support."""
        print("🚀 Logan Assistant with Code Analysis Tools!")
        print()

        # Show model information
        print(self._format_model_info())

        # Show notification status
        if self.notification_manager.is_enabled():
            provider_count = len(self.notification_manager.providers)
            print(
                f"📲 Notifications enabled ({provider_count} provider{'s' if provider_count != 1 else ''})"
            )
        else:
            print("📲 Notifications disabled (interactive mode)")

        if not AWS_AVAILABLE:
            print("⚠️  AWS dependencies not available")
            print("💡 Install: pip install boto3 langchain langchain-aws")
        else:
            print("🔧 Code analysis tools ready!")
            print(
                f"🛠️  {len(self.tools) if hasattr(self, 'tools') else 0} tools available"
            )

        # Show repository status
        repo_url = os.getenv("REPOSITORY_URL")
        commit_id = os.getenv("COMMIT_ID")
        branch = os.getenv("REPOSITORY_BRANCH", "main")

        if repo_url:
            if commit_id:
                print(f"📂 Repository: {repo_url} @ {commit_id[:8]}")
            else:
                print(f"📂 Repository: {repo_url} (branch: {branch})")

            if self.analyzer and hasattr(self.analyzer, "functions"):
                func_count = len(self.analyzer.functions)
                class_count = len(getattr(self.analyzer, "classes", {}))
                print(f"📊 Loaded: {func_count} functions, {class_count} classes")
        else:
            print("⚠️  No repository configured (set REPOSITORY_URL)")

        print()
        print("💡 Example commands:")
        print("  • Search for code: 'Find all async functions'")
        print("  • Preview code: 'Show me the main function'")
        print("  • Ask questions: 'What does this codebase do?'")
        print()
        print("🔧 Environment variables:")
        print("  • REPOSITORY_URL: Git repository to analyze")
        print("  • SLACK_BOT_TOKEN: Slack bot token for notifications")
        print("  • SLACK_CHANNEL: Slack channel (default: #general)")
        print()
        print("Type 'quit', 'exit', or 'bye' to stop.")
        print("Type 'reset' to start a new analysis session.")
        print("=" * 60)

        while True:
            user_input = self.get_user_input()

            if user_input is None:
                print("\n👋 Goodbye!")
                break

            if not user_input:
                continue

            # Handle special commands
            if user_input.lower() in ["quit", "exit", "bye"]:
                break
            elif user_input.lower() in ["reset", "new"]:
                self.analysis_started = False
                self.current_analysis = None
                print("🔄 Analysis session reset")
                continue
            elif user_input.lower() in ["version", "ver", "v"]:
                print("\n🚀 Logan Assistant with Notifications v1.1.0")
                print(f"🤖 {self._format_model_info()}")
                print(
                    f"📲 Notifications: {'✅ Enabled' if self.notification_manager.is_enabled() else '❌ Disabled'}"
                )
                continue
            elif user_input.lower() in ["help", "h", "?"]:
                print("\n🔧 Logan Assistant Commands:")
                print("=" * 30)
                print("• version/ver/v - Show version and system info")
                print("• help/h/? - Show this help message")
                print("• reset/new - Start new analysis session")
                print("• quit/exit/bye - Exit Logan")
                print(
                    f"• Notifications: {'Enabled' if self.notification_manager.is_enabled() else 'Disabled'}"
                )
                continue

            # Use regular stream response (no notifications in interactive mode)
            await self.stream_response(user_input)

    async def run_single_mode_with_notifications(self) -> None:
        """Run single mode (non-interactive) with notification support."""
        try:
            user_input = sys.stdin.read().strip()

            if not user_input:
                print("❌ No input provided.", file=sys.stderr)
                sys.exit(1)

            # Use notification-aware stream response for single mode
            await self.stream_response_with_notifications(user_input)

        except KeyboardInterrupt:
            print("\n⚠️  Interrupted by user.", file=sys.stderr)
            try:
                await self.notification_manager.send_error_notification(
                    "Analysis interrupted by user",
                    user_input if "user_input" in locals() else "Unknown request",
                )
            except:
                pass
            sys.exit(1)
        except Exception as e:
            print(f"\n❌ Error: {e}", file=sys.stderr)
            try:
                await self.notification_manager.send_error_notification(
                    str(e),
                    user_input if "user_input" in locals() else "Unknown request",
                )
            except:
                pass
            sys.exit(1)


async def main():
    """Main entry point with notification support."""
    import argparse

    parser = argparse.ArgumentParser(description="Logan Assistant with Notifications")
    parser.add_argument(
        "--model",
        default="anthropic.claude-3-sonnet-20240229-v1:0",
        help="Model ID to use",
    )
    parser.add_argument("--iterations", type=int, default=5, help="Maximum iterations")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--interactive", action="store_true", help="Interactive mode")
    parser.add_argument(
        "--notification-config", help="Path to notification config file"
    )

    args = parser.parse_args()

    # Create Logan assistant with notifications only for non-interactive mode
    assistant = LoganAssistantWithNotifications(
        model_id=args.model,
        max_iterations=args.iterations,
        debug_mode=args.debug,
        notification_config_path=args.notification_config,
        enable_notifications=not args.interactive,  # Disable notifications for interactive mode
    )

    if args.interactive:
        await assistant.run_interactive_with_notifications()
    else:
        await assistant.run_single_mode_with_notifications()


if __name__ == "__main__":
    asyncio.run(main())
