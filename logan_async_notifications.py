"""
Async Logan Assistant with real-time notifications.

This version converts Logan to use async callbacks for real-time Slack notifications
during LLM execution without batching or threading issues.
"""

import asyncio
import os
import sys
from typing import List, Optional, Dict, Any

# Enhanced interactive imports
try:
    from prompt_toolkit.application import create_app_session
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.shortcuts import confirm, PromptSession
    from rich.console import Console
    from rich.progress import (
        Progress,
        SpinnerColumn,
        TextColumn,
        BarColumn,
        TimeRemainingColumn,
    )
    from rich.syntax import Syntax
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import print as rich_print

    ENHANCED_INTERACTIVE_AVAILABLE = True
except ImportError:
    ENHANCED_INTERACTIVE_AVAILABLE = False
    print(
        "⚠️  Enhanced interactive mode not available. Install with: pip install prompt-toolkit rich"
    )

# Import the original Logan classes and functions
from logan import LoganAssistant as BaseLoganAssistant, AWS_AVAILABLE
from notifications import (
    NotificationManager,
    AnalysisSummary,
    create_notification_manager,
    DummyNotificationProvider,
)

if AWS_AVAILABLE:
    from langchain_core.callbacks import AsyncCallbackHandler
    from langchain_aws import ChatBedrock
    import boto3


class AsyncNotificationCallbackHandler(
    AsyncCallbackHandler if AWS_AVAILABLE else object
):
    """Async callback handler for real-time notifications."""

    def __init__(self, notification_manager: NotificationManager):
        if AWS_AVAILABLE:
            super().__init__()
        self.notification_manager = notification_manager
        print("🐛 [ASYNC_NOTIFICATION] Async callback handler created")
        print(
            f"🐛 [ASYNC_NOTIFICATION] Manager enabled: {notification_manager.is_enabled()}"
        )
        print(
            f"🐛 [ASYNC_NOTIFICATION] Manager providers: {len(notification_manager.providers)}"
        )

    async def on_llm_start(self, serialized, prompts, **kwargs):
        """Called when LLM starts."""
        print(f"🐛 [ASYNC_NOTIFICATION] ========== LLM START ==========")
        print(f"🐛 [ASYNC_NOTIFICATION] LLM Start - {len(prompts)} prompts")
        print(
            f"🐛 [ASYNC_NOTIFICATION] Manager enabled: {self.notification_manager.is_enabled()}"
        )

    async def on_llm_end(self, response, **kwargs):
        """Called when LLM completes - send response immediately."""
        print(f"🐛 [ASYNC_NOTIFICATION] ========== LLM END ==========")
        print(f"🐛 [ASYNC_NOTIFICATION] Response type: {type(response)}")
        print(
            f"🐛 [ASYNC_NOTIFICATION] Manager enabled: {self.notification_manager.is_enabled()}"
        )

        try:
            # Extract content from response
            content = ""
            if hasattr(response, "content"):
                content = str(response.content)
            elif hasattr(response, "generations"):
                for gen in response.generations:
                    for choice in gen:
                        if hasattr(choice, "text") and choice.text:
                            content += choice.text
                        elif hasattr(choice, "message") and hasattr(
                            choice.message, "content"
                        ):
                            content += str(choice.message.content)

            # Send immediately - no threading needed!
            if content.strip():
                print(
                    f"🐛 [ASYNC_NOTIFICATION] ✅ Sending to Slack: {len(content)} chars"
                )
                await self.notification_manager.send_progress_update(
                    content.strip(), "info"
                )
                print(f"🐛 [ASYNC_NOTIFICATION] ✅ Sent successfully")
            else:
                print(f"🐛 [ASYNC_NOTIFICATION] No content to send")

        except Exception as e:
            print(f"🐛 [ASYNC_NOTIFICATION] Error: {e}")
            import traceback

            traceback.print_exc()

    async def on_tool_start(self, serialized, input_str, **kwargs):
        """Called when tool starts - send immediately."""
        print(f"🐛 [ASYNC_NOTIFICATION] ========== TOOL START ==========")
        try:
            tool_name = serialized.get("name", "Unknown tool")
            print(f"🐛 [ASYNC_NOTIFICATION] Tool start: {tool_name}")
            print(
                f"🐛 [ASYNC_NOTIFICATION] Manager enabled: {self.notification_manager.is_enabled()}"
            )
            if self.notification_manager.is_enabled():
                await self.notification_manager.send_progress_update(
                    f"🔧 Running tool: {tool_name}", "progress"
                )
                print(f"🐛 [ASYNC_NOTIFICATION] ✅ Tool start notification sent")
            else:
                print(
                    f"🐛 [ASYNC_NOTIFICATION] ❌ Manager disabled, skipping notification"
                )
        except Exception as e:
            print(f"🐛 [ASYNC_NOTIFICATION] Tool start error: {e}")
            import traceback

            traceback.print_exc()

    async def on_tool_end(self, output, **kwargs):
        """Called when tool ends - send immediately."""
        print(f"🐛 [ASYNC_NOTIFICATION] ========== TOOL END ==========")
        try:
            output_str = str(output).strip()
            if output_str and len(output_str) > 0:
                # Truncate long outputs
                if len(output_str) > 300:
                    output_str = output_str[:300] + "..."

                print(f"🐛 [ASYNC_NOTIFICATION] Tool end: {len(output_str)} chars")
                print(
                    f"🐛 [ASYNC_NOTIFICATION] Manager enabled: {self.notification_manager.is_enabled()}"
                )
                if self.notification_manager.is_enabled():
                    await self.notification_manager.send_progress_update(
                        f"📋 Tool result: {output_str}", "success"
                    )
                    print(f"🐛 [ASYNC_NOTIFICATION] ✅ Tool result notification sent")
                else:
                    print(
                        f"🐛 [ASYNC_NOTIFICATION] ❌ Manager disabled, skipping notification"
                    )
        except Exception as e:
            print(f"🐛 [ASYNC_NOTIFICATION] Tool end error: {e}")
            import traceback

            traceback.print_exc()

    async def on_llm_error(self, error, **kwargs):
        """Called when LLM errors."""
        try:
            await self.notification_manager.send_error_notification(
                f"LLM Error: {str(error)}"
            )
        except Exception as e:
            print(f"🐛 [ASYNC_NOTIFICATION] Error notification failed: {e}")


class LLMNotificationWrapper:
    """Wrapper that captures LLM calls and sends notifications."""

    def __init__(self, llm, notification_manager, parent_assistant=None):
        self.llm = llm
        self.notification_manager = notification_manager
        self._parent_assistant = parent_assistant
        # Notification wrapper initialized

    def __getattr__(self, name):
        """Delegate all other attributes to the wrapped LLM."""
        return getattr(self.llm, name)

    async def astream(self, *args, **kwargs):
        """Wrap astream to capture start/end and handle tool calls using astream_events."""
        try:
            response_content = ""
            complete_response = None

            # Use astream_events to capture both streaming chunks and final response
            async for event in self.llm.astream_events(*args, **kwargs):
                event_type = event.get("event")

                if event_type == "on_chat_model_stream":
                    # Handle streaming chunks
                    chunk = event.get("data", {}).get("chunk")
                    if chunk:
                        # Extract text content for notification
                        chunk_text = ""
                        if hasattr(chunk, "content"):
                            if isinstance(chunk.content, str):
                                chunk_text = chunk.content
                            elif isinstance(chunk.content, list):
                                for item in chunk.content:
                                    if (
                                        isinstance(item, dict)
                                        and item.get("type") == "text"
                                    ):
                                        chunk_text += item.get("text", "")

                        response_content += chunk_text
                        yield chunk

                elif event_type == "on_chat_model_end":
                    # Handle complete response with tool calls
                    complete_response = event.get("data", {}).get("output")

                    # Store complete response for parent to access
                    if hasattr(self, "_parent_assistant") and complete_response:
                        self._parent_assistant.captured_response = complete_response

                        # Debug output if enabled
                        if (
                            hasattr(self._parent_assistant, "debug_mode")
                            and self._parent_assistant.debug_mode
                        ):
                            print(
                                f"🐛 [DEBUG] Complete LLM Response captured via astream_events:"
                            )
                            print(f"🐛 [DEBUG]   Type: {type(complete_response)}")
                            if hasattr(complete_response, "tool_calls"):
                                print(
                                    f"🐛 [DEBUG]   Tool calls: {complete_response.tool_calls}"
                                )
                            if hasattr(complete_response, "response_metadata"):
                                print(
                                    f"🐛 [DEBUG]   Response metadata: {complete_response.response_metadata}"
                                )

            # Send notification with complete response
            if response_content.strip() and self.notification_manager.is_enabled():
                await self.notification_manager.send_progress_update(
                    response_content.strip(), "info"
                )
        except Exception as e:
            print(f"❌ Error in LLM stream: {e}")
            raise

    async def ainvoke(self, *args, **kwargs):
        """Wrap ainvoke to capture calls and tool usage."""
        result = await self.llm.ainvoke(*args, **kwargs)

        # Send notifications for tool calls if present
        if (
            hasattr(result, "tool_calls")
            and result.tool_calls
            and self.notification_manager.is_enabled()
        ):
            for tool_call in result.tool_calls:
                tool_name = tool_call.get("name", "Unknown tool")
                tool_args = tool_call.get("args", {})

                # Format tool arguments for display
                args_str = ""
                if tool_args:
                    # Show first few key arguments
                    arg_parts = []
                    for key, value in list(tool_args.items())[:3]:
                        if isinstance(value, str) and len(value) > 50:
                            value = value[:50] + "..."
                        arg_parts.append(f"{key}: {value}")
                    if len(tool_args) > 3:
                        arg_parts.append("...")
                    args_str = f" ({', '.join(arg_parts)})"

                await self.notification_manager.send_progress_update(
                    f"🔧 Running tool: {tool_name}{args_str}", "progress"
                )

        return result


class AsyncLoganWithNotifications(BaseLoganAssistant):
    """Async Logan Assistant with real-time notifications."""

    def __init__(
        self,
        model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0",
        max_iterations: int = 20,
        debug_mode: bool = False,
        notification_config_path: Optional[str] = None,
        enable_notifications: bool = True,
    ):
        # Initialize basic attributes without calling super().__init__ to avoid double loading
        self.model_id = model_id
        self.max_iterations = max_iterations
        self.debug_mode = debug_mode or os.getenv("LOGAN_DEBUG", "").lower() in (
            "true",
            "1",
            "yes",
        )

        # Initialize system prompt with Jinja2 templating
        try:
            prompt_file = os.path.join(os.path.dirname(__file__), "system_prompt.md")
            with open(prompt_file, "r", encoding="utf-8") as f:
                template_content = f.read()

            # Import Jinja2 for advanced templating
            try:
                from jinja2 import Template
            except ImportError:
                print("Warning: Jinja2 not available, install with: pip install jinja2")
                self.system_prompt = template_content
                return

            # Prepare template context
            from datetime import datetime

            now = datetime.now()
            context = {
                # DateTime information
                "current_datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
                "current_date": now.strftime("%Y-%m-%d"),
                "current_time": now.strftime("%H:%M:%S"),
                "timestamp": now.strftime("%Y%m%d%H%M"),
                "year": now.year,
                "month": now.month,
                "day": now.day,
                "hour": now.hour,
                "minute": now.minute,
                # Environment information
                "repository_url": os.getenv("REPOSITORY_URL", "Unknown"),
                "repository_branch": os.getenv("REPOSITORY_BRANCH", "main"),
                "commit_id": os.getenv("COMMIT_ID", "latest"),
                "model_id": self.model_id,
                "max_iterations": self.max_iterations,
                "debug_mode": self.debug_mode,
                # Session context
                "session_type": "interactive"
                if hasattr(self, "_interactive_mode")
                else "single_prompt",
                "notifications_enabled": hasattr(self, "notification_manager")
                and self.notification_manager.is_enabled(),
            }

            # Render template with context
            template = Template(template_content)
            self.system_prompt = template.render(**context)

        except Exception as e:
            print(f"Warning: Could not load system_prompt.md: {e}")
            self.system_prompt = "You are Logan, a powerful code analysis assistant."

        # Add missing attributes that tools expect
        self.verbose = os.getenv("LOGAN_VERBOSE", "").lower() in ("true", "1", "yes")
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.iteration_token_history = []

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

        # Initialize tools and LLM (with repository loading indicator)
        if AWS_AVAILABLE:
            self._init_tools_with_progress()
            self._init_async_llm()
        else:
            self.tools = []
            self.llm = None

    def _init_tools_with_progress(self):
        """Initialize tools with repository loading progress indicator."""
        repo_url = os.getenv("REPOSITORY_URL")
        if repo_url:
            # Show loading message
            print("📥 Loading repository...", end="", flush=True)

        # Call parent's _init_tools method
        self._init_tools()

        if repo_url and hasattr(self, "analyzer") and self.analyzer:
            # Show completion
            func_count = len(getattr(self.analyzer, "functions", {}))
            class_count = len(getattr(self.analyzer, "classes", {}))
            file_count = len(getattr(self.analyzer, "virtual_files", {}))

            print(
                f"\r✅ Repository loaded: {file_count} files, {func_count} functions, {class_count} classes"
            )
        elif repo_url:
            print("\r⚠️ Repository loading failed")

    def _initialize_bedrock(self):
        """Override parent's LLM initialization completely to avoid duplicate callbacks."""
        if not AWS_AVAILABLE:
            print(f"❌ AWS dependencies not available", file=sys.stderr)
            return None

        try:
            import boto3
            from langchain_aws import ChatBedrock

            # Creating Bedrock client

            bedrock_client = boto3.client(
                service_name="bedrock-runtime",
                region_name="us-east-1",
            )

            # Bedrock client created, creating LLM

            # Create base LLM without any callbacks
            llm = ChatBedrock(
                client=bedrock_client,
                model_id=self.model_id,
                streaming=True,
                model_kwargs={
                    "max_tokens": 4096,
                    "temperature": 0.1,
                },
            )

            # Base LLM created successfully

            # Bind tools to the LLM FIRST, before wrapping
            if hasattr(self, "tools") and self.tools:
                llm = llm.bind_tools(self.tools)

            # Wrap LLM with our notification wrapper AFTER tools are bound
            if self.notification_manager.is_enabled():
                llm = LLMNotificationWrapper(llm, self.notification_manager, self)

            return llm

        except Exception as e:
            print(f"❌ Error initializing Bedrock: {e}", file=sys.stderr)
            return None

    def _init_async_llm(self):
        """Initialize the LLM with async callbacks."""
        initialized_llm = self._initialize_bedrock()
        if initialized_llm is None:
            print("❌ Failed to initialize LLM")
            return

        # IMPORTANT: Set self.llm to ensure it's not None when parent checks
        self.llm = initialized_llm

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
            print("📲 Initial notification sent")
        except Exception as e:
            print(f"⚠️ Failed to send initial notification: {e}")

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
            print(f"⚠️ Failed to send completion notification: {e}")

    async def stream_response(self, user_input: str) -> None:
        """Stream response using parent's method with notification wrapper."""
        try:
            # Call parent's stream_response - wrapper will handle notifications automatically
            await super().stream_response(user_input)

        except Exception as e:
            print(f"\n❌ Error during streaming: {e}")
            await self.notification_manager.send_error_notification(
                str(e), f"Error during analysis of: {user_input}"
            )
            raise

    async def run_single_mode(self) -> None:
        """Run single mode with notifications."""
        try:
            user_input = sys.stdin.read().strip()

            if not user_input:
                print("❌ No input provided.", file=sys.stderr)
                sys.exit(1)

            # Send initial notification
            await self.start_analysis_notification(user_input)

            # Stream response with real-time notifications
            await self.stream_response(user_input)

            # Send completion notification
            await self.send_completion_notification()

        except KeyboardInterrupt:
            print("\n⚠️ Interrupted by user.", file=sys.stderr)
            await self.notification_manager.send_error_notification(
                "Analysis interrupted by user",
                user_input if "user_input" in locals() else "Unknown request",
            )
            sys.exit(1)
        except Exception as e:
            print(f"\n❌ Error: {e}", file=sys.stderr)
            await self.notification_manager.send_error_notification(
                str(e),
                user_input if "user_input" in locals() else "Unknown request",
            )
            sys.exit(1)

    async def run_interactive_mode(self) -> None:
        """Run interactive mode with enhanced UI if available."""
        if ENHANCED_INTERACTIVE_AVAILABLE:
            await self.run_enhanced_interactive_mode()
        else:
            await self.run_basic_interactive_mode()

    async def run_basic_interactive_mode(self) -> None:
        """Run basic interactive mode (fallback)."""
        print("🚀 Async Logan Assistant (Interactive Mode)")
        print("📲 Notifications disabled (interactive mode)")

        if not AWS_AVAILABLE:
            print("⚠️ AWS dependencies not available")
            return

        print("\nType 'quit' to exit.")

        while True:
            try:
                user_input = input("\n🤖 Query: ").strip()

                if user_input.lower() in ["quit", "exit", "bye"]:
                    break

                if not user_input:
                    continue

                # No notifications in interactive mode
                await self.stream_response(user_input)

            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except EOFError:
                print("\n👋 Goodbye!")
                break

    async def run_enhanced_interactive_mode(self) -> None:
        """Run enhanced interactive mode with prompt_toolkit and rich."""
        import sys

        # Check if we're in a proper terminal
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            print("⚠️ Enhanced mode requires a terminal. Falling back to basic mode...")
            await self.run_basic_interactive_mode()
            return

        console = Console()

        # Welcome banner
        console.print(
            Panel.fit(
                "[bold blue]🚀 Enhanced Logan Assistant[/bold blue]\n"
                "[dim]Powered by prompt-toolkit & rich[/dim]",
                border_style="blue",
            )
        )

        if not AWS_AVAILABLE:
            console.print("⚠️ AWS dependencies not available", style="bold red")
            return

        # Setup auto-completion
        # Common question starters and commands for auto-completion
        logan_commands = [
            # Natural language starters
            "what",
            "how",
            "where",
            "why",
            "show me",
            "find",
            "list",
            "explain",
            "analyze",
            "check",
            # Analysis targets
            "functions",
            "classes",
            "imports",
            "dependencies",
            "patterns",
            "files",
            "modules",
            "structure",
            "complexity",
            "issues",
            "errors",
            "security",
            "performance",
            # System commands
            "help",
            "clear",
            "history",
            "quit",
            "exit",
        ]

        completer = WordCompleter(logan_commands, ignore_case=True)

        # Command history
        history = FileHistory(".logan_history")

        # Status info
        console.print(f"📱 Model: [bold]{self.model_id}[/bold]")
        console.print(f"🔄 Max iterations: [bold]{self.max_iterations}[/bold]")
        console.print(
            "📲 Notifications: [bold red]disabled[/bold red] (interactive mode)"
        )

        # Show repository status if available
        repo_url = os.getenv("REPOSITORY_URL")
        if repo_url:
            commit_id = os.getenv("COMMIT_ID")
            branch = os.getenv("REPOSITORY_BRANCH", "main")

            if commit_id:
                console.print(
                    f"📂 Repository: [cyan]{repo_url}[/cyan] @ [yellow]{commit_id[:8]}[/yellow]"
                )
            else:
                console.print(
                    f"📂 Repository: [cyan]{repo_url}[/cyan] ([green]{branch}[/green] branch)"
                )

            # Show repository stats if loaded
            if hasattr(self, "analyzer") and self.analyzer:
                func_count = len(getattr(self.analyzer, "functions", {}))
                class_count = len(getattr(self.analyzer, "classes", {}))
                file_count = len(getattr(self.analyzer, "virtual_files", {}))

                console.print(
                    f"📊 Analysis ready: [bold]{file_count}[/bold] files, "
                    f"[bold]{func_count}[/bold] functions, [bold]{class_count}[/bold] classes"
                )

            console.print()

        console.print(
            "\n[dim]Ask me anything about your code, type 'help' for examples, 'quit' to exit[/dim]\n"
        )

        # Create prompt session for async usage
        session = PromptSession(
            completer=completer,
            history=history,
            auto_suggest=AutoSuggestFromHistory(),
            multiline=False,
        )

        while True:
            try:
                # Enhanced async prompt with auto-completion and history
                try:
                    user_input = (await session.prompt_async("🤖 Logan> ")).strip()
                except (OSError, RuntimeError) as prompt_error:
                    # If prompt fails, fall back to basic input
                    console.print(f"⚠️ Prompt error: {prompt_error}")
                    console.print("Falling back to basic input mode...")
                    await self.run_basic_interactive_mode()
                    return

                if user_input.lower() in ["quit", "exit", "bye"]:
                    console.print("👋 [bold green]Goodbye![/bold green]")
                    break

                if not user_input:
                    continue

                # Handle special commands (but allow natural language for everything else)
                if user_input.lower() == "help":
                    self._show_help(console)
                    continue
                elif user_input.lower() == "clear":
                    console.clear()
                    continue
                elif user_input.lower() == "history":
                    self._show_history(console)
                    continue

                # Accept any input as a natural language query
                # Progress indicator with informative status messages
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                    transient=True,
                ) as progress:
                    task = progress.add_task("🚀 Starting analysis...", total=None)

                    # Capture the response for enhanced formatting
                    try:
                        # No notifications in interactive mode
                        await self.stream_response_enhanced(
                            user_input, console, progress, task
                        )
                    except Exception as e:
                        progress.stop()
                        console.print(f"\n[bold red]❌ Error:[/bold red] {str(e)}")

            except KeyboardInterrupt:
                console.print("\n⚠️  [yellow]Interrupted! Use 'quit' to exit[/yellow]")
                continue
            except EOFError:
                console.print("\n👋 [bold green]Goodbye![/bold green]")
                break

    def _show_help(self, console: Console) -> None:
        """Show help information with rich formatting."""
        help_table = Table(
            title="Logan Assistant Commands",
            show_header=True,
            header_style="bold magenta",
        )
        help_table.add_column("Command", style="cyan", no_wrap=True)
        help_table.add_column("Description", style="white")

        # Show example questions instead of rigid commands
        examples = [
            ("Natural Questions", "Example"),
            ("─" * 20, "─" * 40),
            ("Code Analysis", "What functions are defined in this code?"),
            ("", "How does the authentication system work?"),
            ("", "Show me all the classes"),
            ("", "Find security vulnerabilities"),
            ("Code Quality", "Check for code complexity issues"),
            ("", "Are there any performance problems?"),
            ("", "What are the main dependencies?"),
            ("Exploration", "List all Python files"),
            ("", "Explain how the login process works"),
            ("", "Where is the database connection made?"),
            ("System", "help - Show this information"),
            ("", "clear - Clear the terminal"),
            ("", "quit/exit - Exit the assistant"),
        ]

        for category, example in examples:
            if "─" in category:
                help_table.add_row(category, example)
            else:
                help_table.add_row(category, example)

        console.print(help_table)
        console.print(
            "\n[dim]💡 Ask questions naturally! Use Tab for completion, ↑/↓ for history[/dim]"
        )
        console.print(
            '\n[green]Try asking:[/green] [cyan]"What functions are in this code?"[/cyan] or [cyan]"Find security issues"[/cyan]'
        )

    def _show_history(self, console: Console) -> None:
        """Show command history."""
        try:
            with open(".logan_history", "r") as f:
                history_lines = f.readlines()[-10:]  # Show last 10 commands

            if history_lines:
                console.print("[bold]Recent Commands:[/bold]")
                for i, line in enumerate(history_lines, 1):
                    console.print(f"  {i}. {line.strip()}")
            else:
                console.print("[dim]No command history found[/dim]")
        except FileNotFoundError:
            console.print("[dim]No command history found[/dim]")

    async def stream_response_enhanced(
        self, user_input: str, console: Console, progress: Progress, task
    ) -> None:
        """Enhanced response streaming with real-time streaming and smart markdown enhancement."""
        try:
            # Update progress to show we're waiting for LLM
            progress.update(task, description="🧠 Logan is thinking...")

            # Initialize streaming state
            self._init_streaming_state()

            # Custom streaming with markdown enhancement
            await self._stream_with_smart_buffering(user_input, console, progress, task)

        except Exception as e:
            progress.stop()
            console.print(
                Panel(
                    f"[red]❌ Error: {str(e)}[/red]",
                    title="[bold red]Error[/bold red]",
                    border_style="red",
                    padding=(0, 1),
                )
            )
            raise

    def _init_streaming_state(self):
        """Initialize markdown state machine for intelligent streaming."""
        self._buffer = ""
        self._state = "PLAIN"  # PLAIN, IN_BOLD, IN_ITALIC, IN_LIST, IN_HEADER, IN_CODE
        self._markdown_buffer = ""
        self._pending_markdown = False

    def _markdown_state_machine(self, chunk_text: str, console) -> str:
        """State machine for intelligent markdown streaming vs buffering."""
        if not hasattr(self, "_buffer"):
            self._init_streaming_state()

        self._buffer += chunk_text

        i = 0
        while i < len(chunk_text):
            char = chunk_text[i]

            if self._state == "PLAIN":
                # Check for markdown triggers
                if char == "*" and i + 1 < len(chunk_text) and chunk_text[i + 1] == "*":
                    # Start bold formatting - stream with rich styling
                    self._state = "IN_BOLD"
                    self._markdown_buffer = ""
                    i += 1  # Skip both **
                elif char == "*" and (i == 0 or chunk_text[i - 1] == " "):
                    # Start italic formatting - single *
                    self._state = "IN_ITALIC"
                    self._markdown_buffer = ""
                elif (
                    char == "-"
                    and (
                        i == 0
                        or self._buffer[len(self._buffer) - len(chunk_text) + i - 1]
                        == "\n"
                    )
                    and (i + 1 < len(chunk_text) and chunk_text[i + 1] == " ")
                ):
                    # Start list item - buffer for proper formatting
                    self._state = "IN_LIST"
                    self._markdown_buffer = "- "
                    i += 1  # Skip the space after -
                elif char == "#" and (
                    i == 0
                    or self._buffer[len(self._buffer) - len(chunk_text) + i - 1] == "\n"
                ):
                    # Start header - count # symbols and buffer
                    header_level = 1
                    j = i + 1
                    while j < len(chunk_text) and chunk_text[j] == "#":
                        header_level += 1
                        j += 1

                    if j < len(chunk_text) and chunk_text[j] == " ":
                        self._state = "IN_HEADER"
                        self._markdown_buffer = "#" * header_level + " "
                        i = j  # Skip all # and space
                else:
                    # Plain text - stream immediately
                    print(char, end="", flush=True)

            elif self._state == "IN_BOLD":
                if char == "*" and i + 1 < len(chunk_text) and chunk_text[i + 1] == "*":
                    # End bold - print styled content
                    console.print(f"[bold]{self._markdown_buffer}[/bold]", end="")
                    self._reset_to_plain()
                    i += 1  # Skip second *
                else:
                    # Accumulate bold content
                    self._markdown_buffer += char

            elif self._state == "IN_ITALIC":
                if char == "*":
                    # End italic - print styled content
                    console.print(f"[italic]{self._markdown_buffer}[/italic]", end="")
                    self._reset_to_plain()
                else:
                    # Accumulate italic content
                    self._markdown_buffer += char

            elif self._state == "IN_LIST":
                if char == "\n":
                    # End of list item - render with bullet, processing any bold formatting
                    list_content = self._markdown_buffer[
                        2:
                    ].strip()  # Remove "- " prefix
                    # Process bold and italic formatting within list content
                    import re

                    list_content = re.sub(
                        r"\*\*(.*?)\*\*", r"[bold]\1[/bold]", list_content
                    )
                    list_content = re.sub(
                        r"\*([^*]*?)\*", r"[italic]\1[/italic]", list_content
                    )
                    console.print(f"• {list_content}")
                    self._reset_to_plain()
                else:
                    # Continue accumulating list content
                    self._markdown_buffer += char

            elif self._state == "IN_HEADER":
                if char == "\n":
                    # End of header - render with appropriate styling
                    header_prefix = ""
                    content_start = 2

                    # Determine header level and styling
                    if self._markdown_buffer.startswith("#### "):
                        header_prefix = "📄 "
                        content_start = 5
                    elif self._markdown_buffer.startswith("### "):
                        header_prefix = "🔹 "
                        content_start = 4
                    elif self._markdown_buffer.startswith("## "):
                        header_prefix = "📋 "
                        content_start = 3
                    elif self._markdown_buffer.startswith("# "):
                        header_prefix = "📖 "
                        content_start = 2

                    header_content = self._markdown_buffer[content_start:].strip()

                    # Remove existing emoji if present in content to avoid duplication
                    if header_content.startswith(("📄 ", "🔹 ", "📋 ", "📖 ")):
                        header_content = header_content[2:].strip()

                    # Process bold and italic formatting within header content
                    import re

                    header_content = re.sub(r"\*\*(.*?)\*\*", r"\1", header_content)
                    header_content = re.sub(r"\*([^*]*?)\*", r"\1", header_content)

                    console.print(
                        f"[bold blue]{header_prefix}{header_content}[/bold blue]"
                    )
                    self._reset_to_plain()
                else:
                    # Continue accumulating header content
                    self._markdown_buffer += char

            i += 1

    def _render_markdown_section(self, markdown_text: str, console):
        """Render a complete markdown section."""
        try:
            from rich.markdown import Markdown

            # Add proper spacing around markdown blocks
            print()
            markdown = Markdown(markdown_text.strip())
            console.print(markdown)
            print()
        except ImportError:
            # Fallback to plain text with proper spacing
            print(f"\n{markdown_text.strip()}\n", end="", flush=True)

    def _reset_to_plain(self):
        """Reset state machine to plain text mode."""
        self._state = "PLAIN"
        self._markdown_buffer = ""
        self._pending_markdown = False

    def _flush_remaining_markdown(self, console):
        """Flush any remaining markdown content."""
        if hasattr(self, "_markdown_buffer") and self._markdown_buffer.strip():
            if self._state == "IN_BOLD":
                console.print(f"[bold]{self._markdown_buffer}[/bold]", end="")
            elif self._state == "IN_ITALIC":
                console.print(f"[italic]{self._markdown_buffer}[/italic]", end="")
            elif self._state == "IN_LIST":
                list_content = (
                    self._markdown_buffer[2:].strip()
                    if self._markdown_buffer.startswith("- ")
                    else self._markdown_buffer.strip()
                )
                console.print(f"• {list_content}")
            elif self._state == "IN_HEADER":
                header_prefix = ""
                content_start = 2

                # Determine header level and styling
                if self._markdown_buffer.startswith("#### "):
                    header_prefix = "📄 "
                    content_start = 5
                elif self._markdown_buffer.startswith("### "):
                    header_prefix = "🔹 "
                    content_start = 4
                elif self._markdown_buffer.startswith("## "):
                    header_prefix = "📋 "
                    content_start = 3
                elif self._markdown_buffer.startswith("# "):
                    header_prefix = "📖 "
                    content_start = 2

                header_content = (
                    self._markdown_buffer[content_start:].strip()
                    if len(self._markdown_buffer) > content_start
                    else self._markdown_buffer.strip()
                )

                # Remove existing emoji if present in content to avoid duplication
                if header_content.startswith(("📄 ", "🔹 ", "📋 ", "📖 ")):
                    header_content = header_content[2:].strip()

                # Process bold and italic formatting within header content
                import re

                header_content = re.sub(r"\*\*(.*?)\*\*", r"\1", header_content)
                header_content = re.sub(r"\*([^*]*?)\*", r"\1", header_content)

                console.print(f"[bold blue]{header_prefix}{header_content}[/bold blue]")
            self._reset_to_plain()

    async def _stream_with_smart_buffering(
        self, user_input: str, console, progress, task
    ):
        """Stream response using parent's logic but override chunk processing."""
        progress.stop()

        # Initialize state machine
        self._init_streaming_state()

        # Override the chunk processing in parent's stream_response
        original_extract = self._extract_text_from_chunk
        self._captured_response = None  # Store the response object

        def enhanced_extract(chunk):
            """Extract and process chunk through state machine."""
            chunk_text = original_extract(chunk)
            if chunk_text:
                # Don't print directly - let state machine handle it
                self._markdown_state_machine(chunk_text, console)
                return ""  # Return empty to prevent parent from printing
            return chunk_text

        # Use the real LLM responses - no mocking needed
        # The parent stream_response method will handle ainvoke properly

        # Override print to filter debug messages
        import builtins

        original_print = builtins.print

        def filtered_print(*args, **kwargs):
            if args and isinstance(args[0], str):
                text = args[0]
                if "🔄 Iteration" in text and not self.debug_mode:
                    return  # Skip iteration counter
                elif "🤖 Logan: " in text:
                    return  # Skip Logan: prefix
                elif "Get complete response for tool calls" in text:
                    return  # Skip redundant message
            original_print(*args, **kwargs)

        builtins.print = filtered_print

        # Temporarily replace chunk extraction
        self._extract_text_from_chunk = enhanced_extract

        try:
            # Reset chunk buffer
            self._chunk_buffer = []

            # Call parent's complete stream_response with all tool processing
            await super().stream_response(user_input)

            # Reconstruct response from chunks if needed
            if hasattr(self, "_chunk_buffer") and self._chunk_buffer:
                # Create a mock response object from the last chunk
                last_chunk = self._chunk_buffer[-1] if self._chunk_buffer else None
                if last_chunk and hasattr(last_chunk, "tool_calls"):
                    self._captured_response = last_chunk

            # Flush any remaining markdown
            self._flush_remaining_markdown(console)

        finally:
            # Restore original extraction and print
            self._extract_text_from_chunk = original_extract
            builtins.print = original_print

            # Clean up complete

        print()  # Single newline after response


async def main():
    """Main async entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Async Logan Assistant with Notifications"
    )
    parser.add_argument(
        "--model",
        default="anthropic.claude-3-sonnet-20240229-v1:0",
        help="Model ID to use",
    )
    parser.add_argument("--iterations", type=int, default=20, help="Maximum iterations")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--interactive", action="store_true", help="Interactive mode")
    parser.add_argument(
        "--notification-config", help="Path to notification config file"
    )

    args = parser.parse_args()

    # Create async Logan assistant
    assistant = AsyncLoganWithNotifications(
        model_id=args.model,
        max_iterations=args.iterations,
        debug_mode=args.debug,
        notification_config_path=args.notification_config,
        enable_notifications=not args.interactive,  # Disable notifications for interactive mode
    )

    if args.interactive:
        await assistant.run_interactive_mode()
    else:
        await assistant.run_single_mode()


if __name__ == "__main__":
    asyncio.run(main())
