#!/usr/bin/env python3
"""
Logan - A streaming assistant using LangChain with AWS Bedrock and tool calling
Reads input from stdin and streams output to console with dulwich memory analyzer integration
"""

import sys
import asyncio
import json
import io
import os
import sys
from contextlib import redirect_stdout, redirect_stderr
from typing import Optional, Dict, List, Any

# Try to import AWS dependencies, handle gracefully if missing
try:
    import boto3
    from langchain_aws import ChatBedrock
    from langchain_core.messages import (
        HumanMessage,
        SystemMessage,
        ToolMessage,
        AIMessage,
    )
    from langchain_core.tools import BaseTool
    from langchain_core.callbacks import AsyncCallbackHandler
    from langchain_core.outputs import LLMResult

    AWS_AVAILABLE = True
except ImportError as e:
    AWS_AVAILABLE = False
    IMPORT_ERROR = str(e)

    # Create mock message classes for when AWS dependencies are not available
    class HumanMessage:
        def __init__(self, content):
            self.content = content

    class SystemMessage:
        def __init__(self, content):
            self.content = content

    class ToolMessage:
        def __init__(self, content, tool_call_id):
            self.content = content
            self.tool_call_id = tool_call_id

    class AIMessage:
        def __init__(self, content):
            self.content = content

    # Mock BaseTool class
    class BaseTool:
        def __init__(self):
            pass

    # Mock AsyncCallbackHandler
    class AsyncCallbackHandler:
        def __init__(self):
            pass

    # Mock LLMResult
    class LLMResult:
        def __init__(self):
            pass


# Always import pydantic regardless of AWS availability
try:
    from pydantic import BaseModel, Field
except ImportError:
    # Create mock classes if pydantic is not available
    class BaseModel:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    def Field(**kwargs):
        return kwargs.get("default", None)


# Tool input schemas
class SearchCodeInput(BaseModel):
    """Input for search_code tool"""

    pattern: str = Field(description="Pattern to search for in code")
    search_type: str = Field(
        default="both", description="Search in functions, classes, or both"
    )


class PreviewCodeInput(BaseModel):
    """Input for preview_code tool"""

    identifier: str = Field(
        description="Function name or file:line location to preview"
    )


class ListInput(BaseModel):
    """Input for list tools"""

    limit: int = Field(default=20, description="Maximum number of items to return")


class FileListInput(BaseModel):
    """Input for list_files tool"""

    pattern: str = Field(
        default="*", description="File pattern to match (e.g., '*.py', 'main*')"
    )
    limit: int = Field(default=50, description="Maximum number of files to return")


class FunctionCallsInput(BaseModel):
    """Input for find_function_calls tool"""

    function_name: str = Field(description="Name of the function to find calls for")
    search_type: str = Field(
        default="both",
        description="Search for 'calls_to' this function, 'calls_from' this function, or 'both'",
    )


class SwitchCommitInput(BaseModel):
    """Input for switch_commit tool"""

    commit_id: str = Field(description="Git commit SHA to switch to (full or short)")
    reload_analysis: bool = Field(
        default=True, description="Whether to reload code analysis after switching"
    )


class ListAllFilesInput(BaseModel):
    """Input for list_all_files tool"""

    pattern: str = Field(
        default="*",
        description="File pattern to match (e.g., '*.py', 'main*', '*config*')",
    )
    limit: int = Field(default=100, description="Maximum number of files to return")


class GrepContentInput(BaseModel):
    """Input for grep_content tool"""

    pattern: str = Field(description="Text pattern to search for (supports regex)")
    file_pattern: str = Field(
        default="*.py", description="File pattern to search within"
    )
    case_sensitive: bool = Field(
        default=False, description="Whether search is case sensitive"
    )
    line_limit: int = Field(
        default=50, description="Maximum number of matching lines to return"
    )


class CreatePatchInput(BaseModel):
    """Input for create_patch tool"""

    description: str = Field(description="Description of the changes for the patch")
    files: List[str] = Field(
        default=[],
        description="List of files to track (optional, inferred from changes)",
    )
    search_replace: List[dict] = Field(
        default=None,
        description="""Simple search and replace operations.

Format: [{"file": "main.py", "search": "old_code", "replace": "new_code"}]
Use this for simple text replacements within files.""",
    )
    patch_content: str = Field(
        default="",
        description="""Unified diff patch content for complex changes.

Format:
--- a/file.py
+++ b/file.py
@@ -10,3 +10,3 @@
 context line
-old line
+new line
 context line

Use this for complex multi-line changes with context.""",
    )
    branch_name: str = Field(
        default="", description="Name for the new branch (optional)"
    )
    commit_message: str = Field(default="", description="Commit message (optional)")
    auto_commit: bool = Field(
        default=False, description="Create commit in memory repository"
    )
    auto_push: bool = Field(default=False, description="Push to remote repository")
    real_push: bool = Field(
        default=True, description="Enable actual git push operations"
    )


class ApplyPatchInput(BaseModel):
    """Input for apply_patch tool"""

    patch_content: str = Field(
        description="""Unified diff patch content to apply.

MANDATORY WORKFLOW:
1. Use preview_code or grep_content to examine the target file content first
2. Create patch with EXACT context lines from the actual file
3. Ensure the lines you want to change actually exist in the file
4. Use proper diff format with correct line numbers

The patch will be applied using intelligent pattern matching to the memory repository."""
    )
    target_branch: str = Field(
        default="main", description="Branch to apply the patch to"
    )
    create_branch: bool = Field(
        default=True, description="Whether to create a new branch for the patch"
    )
    branch_name: str = Field(
        default="", description="Name for the new branch (auto-generated if empty)"
    )
    auto_apply: bool = Field(
        default=False, description="Apply patch to memory repository"
    )
    auto_commit: bool = Field(
        default=False,
        description="Commit changes in memory repository after applying patch",
    )
    auto_push: bool = Field(
        default=False,
        description="Actually push branch to origin repository (auto-enabled when auto_apply=True)",
    )
    real_push: bool = Field(
        default=True,
        description="Enable real git push operations when auto_push=True (default: True)",
    )
    commit_message: str = Field(
        default="", description="Custom commit message (auto-generated if empty)"
    )


class ApplyCodeChangesInput(BaseModel):
    """Input for apply_code_changes tool"""

    files: List[Dict[str, Any]] = Field(description="List of file changes to apply")
    description: str = Field(description="Description of the changes being applied")

    class Config:
        schema_extra = {
            "example": {
                "files": [
                    {
                        "path": "main.py",
                        "changes": [
                            {
                                "line": 2587,
                                "old_content": 'tool_input = tool_call.get("input")',
                                "new_content": 'tool_input = tool_call[0].get("input")',
                            },
                            {
                                "line": 2601,
                                "old_content": 'log.error(f"Error running tool: {e}")',
                                "new_content": 'logger.error(f"Error running tool: {e}")',
                            },
                        ],
                    }
                ],
                "description": "Fix AttributeError and NameError in run_tool function",
            }
        }


class DulwichSearchTool(BaseTool if AWS_AVAILABLE else object):
    """Tool for searching code in the loaded repository"""

    name: str = "search_code"
    description: str = (
        "Search for functions and classes by pattern in the loaded repository"
    )
    args_schema: type = SearchCodeInput if AWS_AVAILABLE else None
    analyzer_ref: object = None

    def __init__(self, analyzer_ref):
        super().__init__() if AWS_AVAILABLE else None
        object.__setattr__(self, "analyzer_ref", analyzer_ref)

    def _run(self, pattern: str, search_type: str = "both") -> str:
        analyzer = self.analyzer_ref.analyzer
        if not analyzer:
            return "❌ No repository loaded. Load a repository first."

        try:
            if not hasattr(analyzer, "functions") or not analyzer.functions:
                return "❌ No repository data available. Load a repository first."

            results = analyzer.search_combined(pattern, search_type)
            if not results:
                return f"❌ No matches found for pattern: {pattern}"

            output = []
            for i, result in enumerate(results[:10], 1):  # Limit to 10 results
                if result["type"] == "function":
                    func_type = "Method" if result.get("is_method") else "Function"
                    async_marker = "async " if result.get("is_async") else ""
                    class_info = (
                        f" ({result.get('class_name')})"
                        if result.get("class_name")
                        else ""
                    )
                    output.append(
                        f"{i:2d}. 🔧 {async_marker}{func_type}: {result['highlighted_name']}"
                        f"\n    📄 {result['file']}:{result['line_start']}-{result['line_end']}{class_info}"
                    )
                else:  # class
                    methods_info = f" - {result.get('methods_count', 0)} methods"
                    base_info = (
                        f" extends {', '.join(result.get('base_classes', []))}"
                        if result.get("base_classes")
                        else ""
                    )
                    output.append(
                        f"{i:2d}. 🏗️  Class: {result['highlighted_name']}"
                        f"\n    📄 {result['file']}:{result['line_start']}-{result['line_end']}{methods_info}{base_info}"
                    )

            if len(results) > 10:
                output.append(f"\n... and {len(results) - 10} more matches")

            return f"🔍 Found {len(results)} matches for '{pattern}':\n" + "\n".join(
                output
            )

        except Exception as e:
            return f"❌ Search failed: {str(e)}"


class DulwichPreviewTool(BaseTool if AWS_AVAILABLE else object):
    """Tool for previewing code content"""

    name: str = "preview_code"
    description: str = "Preview code content for a specific function or location"
    args_schema: type = PreviewCodeInput if AWS_AVAILABLE else None
    analyzer_ref: object = None

    def __init__(self, analyzer_ref):
        super().__init__() if AWS_AVAILABLE else None
        object.__setattr__(self, "analyzer_ref", analyzer_ref)

    def _run(self, identifier: str) -> str:
        analyzer = self.analyzer_ref.analyzer
        if not analyzer:
            return "❌ No repository loaded. Load a repository first."

        try:
            if not hasattr(analyzer, "functions") or not analyzer.functions:
                return "❌ No repository data available. Load a repository first."

            # Capture the preview output
            import io
            from contextlib import redirect_stdout

            output_buffer = io.StringIO()
            with redirect_stdout(output_buffer):
                analyzer.preview_method(identifier)

            preview_content = output_buffer.getvalue().strip()
            if preview_content:
                return f"👀 Code Preview for '{identifier}':\n\n{preview_content}"
            else:
                return f"❌ Could not find or preview '{identifier}'"

        except Exception as e:
            return f"❌ Preview failed: {str(e)}"


class DulwichListFunctionsTool(BaseTool if AWS_AVAILABLE else object):
    """Tool for listing functions"""

    name: str = "list_functions"
    description: str = "List all functions in the loaded repository"
    args_schema: type = ListInput if AWS_AVAILABLE else None
    analyzer_ref: object = None

    def __init__(self, analyzer_ref):
        super().__init__() if AWS_AVAILABLE else None
        object.__setattr__(self, "analyzer_ref", analyzer_ref)

    def _run(self, limit: int = 20) -> str:
        analyzer = self.analyzer_ref.analyzer
        if not analyzer:
            return "❌ No repository loaded. Load a repository first."

        try:
            if not hasattr(analyzer, "functions") or not analyzer.functions:
                return "❌ No repository data available. Load a repository first."

            functions = list(analyzer.functions.items())
            total_count = len(functions)

            if total_count == 0:
                return "❌ No functions found in the loaded repository."

            output = [
                f"📋 Functions in repository ({total_count} total, showing first {min(limit, total_count)}):\n"
            ]

            # Group by file for better organization
            by_file = {}
            for func_name, func_info in functions[:limit]:
                file_path = func_info.file_path
                if file_path not in by_file:
                    by_file[file_path] = []
                by_file[file_path].append((func_name, func_info))

            for file_path in sorted(by_file.keys()):
                output.append(f"📄 {file_path}:")
                file_functions = sorted(
                    by_file[file_path], key=lambda x: x[1].line_start
                )

                for func_name, func_info in file_functions:
                    func_type = "Method" if func_info.is_method else "Function"
                    async_prefix = "async " if func_info.is_async else ""
                    class_info = (
                        f" ({func_info.class_name})" if func_info.class_name else ""
                    )
                    output.append(
                        f"   🔧 {async_prefix}{func_name} (L{func_info.line_start}-{func_info.line_end}) - {func_type}{class_info}"
                    )
                output.append("")

            return "\n".join(output)

        except Exception as e:
            return f"❌ List functions failed: {str(e)}"


class DulwichListClassesTool(BaseTool if AWS_AVAILABLE else object):
    """Tool for listing classes"""

    name: str = "list_classes"
    description: str = "List all classes in the loaded repository"
    args_schema: type = ListInput if AWS_AVAILABLE else None
    analyzer_ref: object = None

    def __init__(self, analyzer_ref):
        super().__init__() if AWS_AVAILABLE else None
        object.__setattr__(self, "analyzer_ref", analyzer_ref)

    def _run(self, limit: int = 20) -> str:
        analyzer = self.analyzer_ref.analyzer
        if not analyzer:
            return "❌ No repository loaded. Load a repository first."

        try:
            if not hasattr(analyzer, "classes") or not analyzer.classes:
                return "❌ No repository data available. Load a repository first."

            classes = list(analyzer.classes.items())
            total_count = len(classes)

            if total_count == 0:
                return "❌ No classes found in the loaded repository."

            output = [
                f"📋 Classes in repository ({total_count} total, showing first {min(limit, total_count)}):\n"
            ]

            for i, (class_name, class_info) in enumerate(classes[:limit], 1):
                base_info = (
                    f" extends {', '.join(class_info.base_classes)}"
                    if class_info.base_classes
                    else ""
                )
                output.append(
                    f"{i:2d}. 🏗️  {class_name} ({class_info.file_path}:L{class_info.line_start}-{class_info.line_end})"
                    f"\n    📊 {len(class_info.methods)} methods{base_info}"
                )

            return "\n".join(output)

        except Exception as e:
            return f"❌ List classes failed: {str(e)}"


class DulwichListFilesTool(BaseTool if AWS_AVAILABLE else object):
    """Tool for listing files in the repository"""

    name: str = "list_files"
    description: str = "List files in the repository with optional pattern matching"
    args_schema: type = FileListInput if AWS_AVAILABLE else None
    analyzer_ref: object = None

    def __init__(self, analyzer_ref):
        super().__init__() if AWS_AVAILABLE else None
        object.__setattr__(self, "analyzer_ref", analyzer_ref)

    def _run(self, pattern: str = "*", limit: int = 50) -> str:
        analyzer = self.analyzer_ref.analyzer
        if not analyzer:
            return "❌ No repository loaded."

        try:
            if not hasattr(analyzer, "virtual_files") or not analyzer.virtual_files:
                return "❌ No files available in repository."

            import fnmatch

            files = []
            for file_path, virtual_file in analyzer.virtual_files.items():
                if fnmatch.fnmatch(file_path, pattern) or fnmatch.fnmatch(
                    file_path.split("/")[-1], pattern
                ):
                    files.append(file_path)

            files = sorted(files)[:limit]

            if not files:
                return f"❌ No files found matching pattern: '{pattern}'"

            output = [
                f"📁 Files matching '{pattern}' ({len(files)} found, showing first {min(limit, len(files))}):\n"
            ]

            for i, file_path in enumerate(files, 1):
                output.append(f"{i:2d}. 📄 {file_path}")

            total_files = len(analyzer.virtual_files)
            if total_files > len(files):
                output.append(f"\nTotal files in repository: {total_files}")

            return "\n".join(output)

        except Exception as e:
            return f"❌ List files failed: {str(e)}"


class DulwichRepoSummaryTool(BaseTool if AWS_AVAILABLE else object):
    """Tool for getting repository summary"""

    name: str = "get_repo_summary"
    description: str = (
        "Get comprehensive summary of the repository structure and statistics"
    )
    args_schema: type = None
    analyzer_ref: object = None

    def __init__(self, analyzer_ref):
        super().__init__() if AWS_AVAILABLE else None
        object.__setattr__(self, "analyzer_ref", analyzer_ref)

    def _run(self) -> str:
        analyzer = self.analyzer_ref.analyzer
        if not analyzer:
            return "❌ No repository loaded."

        try:
            # Collect statistics
            stats = {
                "files": len(getattr(analyzer, "virtual_files", {})),
                "functions": len(getattr(analyzer, "functions", {})),
                "classes": len(getattr(analyzer, "classes", {})),
                "python_files": 0,
                "total_lines": 0,
            }

            # Count Python files and lines
            if hasattr(analyzer, "virtual_files"):
                for file_path, virtual_file in analyzer.virtual_files.items():
                    if file_path.endswith(".py"):
                        stats["python_files"] += 1
                        if hasattr(virtual_file, "content"):
                            stats["total_lines"] += len(
                                virtual_file.content.splitlines()
                            )

            # Get file type breakdown
            file_extensions = {}
            if hasattr(analyzer, "virtual_files"):
                for file_path in analyzer.virtual_files.keys():
                    ext = (
                        file_path.split(".")[-1].lower()
                        if "." in file_path
                        else "no_ext"
                    )
                    file_extensions[ext] = file_extensions.get(ext, 0) + 1

            # Get repository info
            repo_info = getattr(analyzer, "repo_info", None)

            output = ["📊 REPOSITORY SUMMARY", "=" * 50]

            if repo_info:
                output.append(f"🌐 Repository: {repo_info.url}")
                output.append(f"🌿 Branch: {repo_info.branch}")
                if hasattr(repo_info, "commit_sha") and repo_info.commit_sha:
                    output.append(f"📝 Commit: {repo_info.commit_sha[:8]}")

            output.extend(
                [
                    "",
                    "📈 STATISTICS:",
                    f"   📁 Total files: {stats['files']}",
                    f"   🐍 Python files: {stats['python_files']}",
                    f"   🔧 Functions: {stats['functions']}",
                    f"   🏗️  Classes: {stats['classes']}",
                    f"   📏 Total lines: {stats['total_lines']}",
                    "",
                    "📋 FILE TYPES:",
                ]
            )

            for ext, count in sorted(
                file_extensions.items(), key=lambda x: x[1], reverse=True
            )[:10]:
                ext_display = f".{ext}" if ext != "no_ext" else "no extension"
                output.append(f"   {ext_display}: {count} files")

            return "\n".join(output)

        except Exception as e:
            return f"❌ Get repo summary failed: {str(e)}"


class DulwichFindCallsTool(BaseTool if AWS_AVAILABLE else object):
    """Tool for finding function calls and references"""

    name: str = "find_function_calls"
    description: str = "Find where a function is called from or what functions it calls"
    args_schema: type = FunctionCallsInput if AWS_AVAILABLE else None
    analyzer_ref: object = None

    def __init__(self, analyzer_ref):
        super().__init__() if AWS_AVAILABLE else None
        object.__setattr__(self, "analyzer_ref", analyzer_ref)

    def _run(self, function_name: str, search_type: str = "both") -> str:
        analyzer = self.analyzer_ref.analyzer
        if not analyzer:
            return "❌ No repository loaded."

        try:
            if not hasattr(analyzer, "virtual_files") or not analyzer.virtual_files:
                return "❌ No files available in repository."

            calls_to_function = []
            calls_from_function = []

            # Search through all files for function calls
            import re

            for file_path, virtual_file in analyzer.virtual_files.items():
                if not file_path.endswith(".py"):
                    continue

                if hasattr(virtual_file, "content"):
                    content = virtual_file.content
                    lines = content.splitlines()

                    for line_num, line in enumerate(lines, 1):
                        # Find calls TO this function
                        if search_type in ["both", "calls_to"]:
                            # Look for function_name( patterns
                            call_pattern = rf"\b{re.escape(function_name)}\s*\("
                            if re.search(call_pattern, line):
                                calls_to_function.append(
                                    {
                                        "file": file_path,
                                        "line": line_num,
                                        "content": line.strip(),
                                    }
                                )

                        # Find calls FROM this function (if we're inside it)
                        if search_type in ["both", "calls_from"]:
                            # This is more complex - we'd need to track if we're inside the function
                            # For now, let's do a simpler approach
                            if (
                                f"def {function_name}(" in line
                                or f"async def {function_name}(" in line
                            ):
                                # Found function definition, look for calls in subsequent lines
                                func_start = line_num
                                indent_level = len(line) - len(line.lstrip())

                                # Look ahead to find function calls within this function
                                for next_line_num in range(
                                    line_num + 1, min(line_num + 100, len(lines))
                                ):
                                    next_line = lines[next_line_num - 1]
                                    next_indent = len(next_line) - len(
                                        next_line.lstrip()
                                    )

                                    # If we've dedented to same or less level, we're out of the function
                                    if (
                                        next_line.strip()
                                        and next_indent <= indent_level
                                    ):
                                        break

                                    # Look for function calls in this line
                                    call_matches = re.findall(r"(\w+)\s*\(", next_line)
                                    for called_func in call_matches:
                                        if called_func not in [
                                            "if",
                                            "for",
                                            "while",
                                            "print",
                                            "len",
                                            "str",
                                            "int",
                                            "float",
                                            "bool",
                                            "dict",
                                            "list",
                                            "tuple",
                                            "set",
                                        ]:
                                            calls_from_function.append(
                                                {
                                                    "file": file_path,
                                                    "line": next_line_num,
                                                    "called_function": called_func,
                                                    "content": next_line.strip(),
                                                }
                                            )

            # Format results
            output = []

            if search_type in ["both", "calls_to"] and calls_to_function:
                output.extend(
                    [
                        f"📞 CALLS TO '{function_name}' ({len(calls_to_function)} found):",
                        "",
                    ]
                )
                for i, call in enumerate(
                    calls_to_function[:20], 1
                ):  # Limit to 20 results
                    output.append(f"{i:2d}. 📄 {call['file']}:{call['line']}")
                    output.append(f"    {call['content']}")
                    output.append("")

                if len(calls_to_function) > 20:
                    output.append(f"... and {len(calls_to_function) - 20} more calls")
                    output.append("")

            if search_type in ["both", "calls_from"] and calls_from_function:
                output.extend(
                    [
                        f"📤 CALLS FROM '{function_name}' ({len(calls_from_function)} found):",
                        "",
                    ]
                )
                unique_calls = {}
                for call in calls_from_function:
                    key = call["called_function"]
                    if key not in unique_calls:
                        unique_calls[key] = []
                    unique_calls[key].append(call)

                for i, (called_func, occurrences) in enumerate(unique_calls.items(), 1):
                    output.append(
                        f"{i:2d}. 🔧 {called_func} ({len(occurrences)} times)"
                    )
                    for occ in occurrences[:3]:  # Show first 3 occurrences
                        output.append(
                            f"    📄 {occ['file']}:{occ['line']} - {occ['content']}"
                        )
                    if len(occurrences) > 3:
                        output.append(f"    ... and {len(occurrences) - 3} more")
                    output.append("")

            if not calls_to_function and not calls_from_function:
                return f"❌ No function calls found for '{function_name}'"

            return "\n".join(output)

        except Exception as e:
            return f"❌ Find function calls failed: {str(e)}"


class DulwichSwitchCommitTool(BaseTool if AWS_AVAILABLE else object):
    """Tool for switching to a different commit"""

    name: str = "switch_commit"
    description: str = "Switch to a specific commit ID and reload the analysis"
    args_schema: type = SwitchCommitInput if AWS_AVAILABLE else None
    analyzer_ref: object = None

    def __init__(self, analyzer_ref):
        super().__init__() if AWS_AVAILABLE else None
        object.__setattr__(self, "analyzer_ref", analyzer_ref)

    def _run(self, commit_id: str, reload_analysis: bool = True) -> str:
        logan_assistant = self.analyzer_ref
        if not logan_assistant.analyzer:
            return "❌ No repository loaded."

        try:
            # Get repository URL from current analyzer
            repo_info = getattr(logan_assistant.analyzer, "repo_info", None)
            if not repo_info or not repo_info.url:
                return "❌ No repository URL available."

            repo_url = repo_info.url

            # Fetch specific commit
            success = logan_assistant._fetch_specific_commit(
                logan_assistant.analyzer, repo_url, commit_id
            )

            if success:
                func_count = len(getattr(logan_assistant.analyzer, "functions", {}))
                class_count = len(getattr(logan_assistant.analyzer, "classes", {}))

                return f"✅ Switched to commit {commit_id[:8]}\n📊 Reloaded: {func_count} functions, {class_count} classes"
            else:
                return f"❌ Failed to switch to commit {commit_id[:8]}"

        except Exception as e:
            return f"❌ Switch commit failed: {str(e)}"


class DulwichListAllFilesTool(BaseTool if AWS_AVAILABLE else object):
    """Tool for listing all files in the repository"""

    name: str = "list_all_files"
    description: str = "List all files in the repository with optional pattern matching"
    args_schema: type = ListAllFilesInput if AWS_AVAILABLE else None
    analyzer_ref: object = None

    def __init__(self, analyzer_ref):
        super().__init__() if AWS_AVAILABLE else None
        object.__setattr__(self, "analyzer_ref", analyzer_ref)

    def _run(self, pattern: str = "*", limit: int = 100) -> str:
        analyzer = self.analyzer_ref.analyzer
        if not analyzer:
            return "❌ No repository loaded."

        try:
            if not hasattr(analyzer, "virtual_files") or not analyzer.virtual_files:
                return "❌ No files available in repository."

            import fnmatch

            files = []
            for file_path in analyzer.virtual_files.keys():
                if fnmatch.fnmatch(file_path, pattern) or fnmatch.fnmatch(
                    file_path.split("/")[-1], pattern
                ):
                    files.append(file_path)

            files = sorted(files)

            if not files:
                return f"❌ No files found matching pattern: '{pattern}'"

            output = [
                f"📁 All files matching '{pattern}' ({len(files)} found, showing first {min(limit, len(files))}):\n"
            ]

            for i, file_path in enumerate(files[:limit], 1):
                output.append(f"{i:3d}. 📄 {file_path}")

            if len(files) > limit:
                output.append(f"\n... and {len(files) - limit} more files")

            total_files = len(analyzer.virtual_files)
            output.append(f"\nTotal files in repository: {total_files}")

            return "\n".join(output)

        except Exception as e:
            return f"❌ List all files failed: {str(e)}"


class DulwichCreatePatchTool(BaseTool if AWS_AVAILABLE else object):
    """Tool for creating patches using simple search-replace or unified diff approaches"""

    name: str = "create_patch"
    description: str = """Create and apply patches to the memory repository using two simple approaches:

APPROACH 1 - SEARCH & REPLACE (recommended for simple changes):
Use 'search_replace' parameter with list of replacements:
[{"file": "main.py", "search": "old_code", "replace": "new_code"}]

APPROACH 2 - UNIFIED DIFF (for complex changes):
Use 'patch_content' parameter with standard unified diff format.

WORKFLOW:
1. FIRST: Use preview_code to examine current file content
2. Choose approach based on complexity
3. For search_replace: provide exact text to find and replace
4. For unified diff: provide complete diff with context lines

The tool will apply changes to the memory repository."""
    args_schema: type = CreatePatchInput if AWS_AVAILABLE else None
    analyzer_ref: object = None

    def __init__(self, analyzer_ref):
        super().__init__() if AWS_AVAILABLE else None
        object.__setattr__(self, "analyzer_ref", analyzer_ref)

    def get_file_content_preview(
        self, file_path: str, start_line: int = 1, lines: int = 50
    ) -> str:
        """Get preview of file content to help create accurate patches"""
        try:
            analyzer = self.analyzer_ref.analyzer
            if not analyzer or not hasattr(analyzer, "virtual_files"):
                return "❌ No virtual files available"

            if file_path not in analyzer.virtual_files:
                available_files = list(analyzer.virtual_files.keys())[:10]
                return (
                    f"❌ File {file_path} not found. Available files: {available_files}"
                )

            virtual_file = analyzer.virtual_files[file_path]
            if not hasattr(virtual_file, "content"):
                return f"❌ File {file_path} has no content"

            content = virtual_file.content
            if isinstance(content, bytes):
                content = content.decode("utf-8")

            content_lines = content.split("\n")
            total_lines = len(content_lines)

            end_line = min(start_line + lines - 1, total_lines)
            preview_lines = content_lines[start_line - 1 : end_line]

            preview = []
            preview.append(
                f"📄 {file_path} (showing lines {start_line}-{end_line} of {total_lines}):"
            )
            preview.append("=" * 50)

            for i, line in enumerate(preview_lines, start_line):
                preview.append(f"{i:4}: {line}")

            return "\n".join(preview)

        except Exception as e:
            return f"❌ Error getting file preview: {e}"

    def _run(
        self,
        description: str,
        files: List[str],
        search_replace: List[dict] = None,
        patch_content: str = "",
        branch_name: str = "",
        commit_message: str = "",
        auto_commit: bool = False,
        auto_push: bool = False,
        real_push: bool = True,
    ) -> str:
        # Debug logging for push configuration
        print(
            f"🔧 create_patch called with: auto_commit={auto_commit}, auto_push={auto_push}, real_push={real_push}"
        )

        # Auto-enable auto_push when auto_commit=True (default behavior)
        if auto_commit and not auto_push:
            auto_push = True
            print(f"🔧 Auto-enabled auto_push because auto_commit=True")

        # Auto-enable real_push when auto_push is True
        if auto_push and not real_push:
            real_push = True
            print(f"🔧 Auto-enabled real_push because auto_push=True")

        analyzer = self.analyzer_ref.analyzer
        if not analyzer:
            return "❌ No repository loaded. Load a repository first."

        if not hasattr(analyzer, "virtual_files") or not analyzer.virtual_files:
            return "❌ No virtual files available in repository."

        try:
            if search_replace is None:
                search_replace = []
            results = []

            # APPROACH 1: Simple search and replace
            if search_replace:
                results.append("🔄 Applying search and replace operations:")
                for operation in search_replace:
                    file_path = operation.get("file", "")
                    search_text = operation.get("search", "")
                    replace_text = operation.get("replace", "")

                    if not all(
                        [file_path, search_text is not None, replace_text is not None]
                    ):
                        results.append(f"❌ Invalid operation: {operation}")
                        continue

                    result = self._apply_search_replace(
                        analyzer, file_path, search_text, replace_text
                    )
                    results.append(result)

            # APPROACH 2: Unified diff patch
            elif patch_content.strip():
                results.append("🔄 Applying unified diff patch:")
                result = self._apply_unified_patch(analyzer, patch_content.strip())
                results.append(result)

            else:
                return "❌ No changes specified. Provide either search_replace or patch_content."

            # Check which files were modified
            modified_files = []
            if search_replace:
                # For search_replace, get files from operations
                for operation in search_replace:
                    file_path = operation.get("file", "")
                    if file_path and file_path in analyzer.virtual_files:
                        if file_path not in modified_files:
                            modified_files.append(file_path)
            elif files:
                # For unified patch, use provided files list
                for file_path in files:
                    if file_path in analyzer.virtual_files:
                        modified_files.append(file_path)

            # Generate summary of results
            summary_lines = []
            summary_lines.append(f"# Patch Applied: {description}")
            summary_lines.append(f"# Modified files: {len(modified_files)}")
            for file_path in modified_files:
                summary_lines.append(f"#   - {file_path}")
            summary_lines.append("")

            # Add the actual results
            summary_lines.extend(results)

            # Create patch metadata for tracking
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            patch_id = f"patch_{timestamp}"

            # Get repository info if available
            repo_info = getattr(analyzer, "repo_info", None)

            output = [
                f"🎉 Patch applied successfully!",
                f"📝 Description: {description}",
                f"🆔 Patch ID: {patch_id}",
            ]

            if repo_info:
                output.append(f"📊 Repository: {repo_info.url}")
                output.append(f"🌿 Base branch: {repo_info.branch}")

            output.append("")

            if modified_files:
                output.extend(["", f"📦 Results:", "```"])
                # Show focused results with reasonable context
                max_display = 50  # Maximum lines to show in output

                if len(summary_lines) <= max_display:
                    output.extend(summary_lines)
                else:
                    # Show first part of results
                    output.extend(summary_lines[: max_display // 2])
                    output.append("@@ ... (more results) ... @@")
                    # Show last part of results
                    output.extend(summary_lines[-max_display // 2 :])

                output.append("```")
            # Handle memory repository operations if requested
            if auto_commit:
                memory_result = self._perform_memory_operations(
                    modified_files,
                    branch_name or f"patch-{patch_id}",
                    commit_message or description,
                    auto_push,
                    analyzer,
                    real_push,
                )
                output.extend(["", "🔧 Memory Repository Operations:"])
                output.extend(
                    [f"   {line}" for line in memory_result.split("\n") if line.strip()]
                )
            else:
                # Calculate total lines with bytes handling
                total_lines = 0
                for f in modified_files:
                    if f in analyzer.virtual_files and hasattr(
                        analyzer.virtual_files[f], "content"
                    ):
                        content = analyzer.virtual_files[f].content
                        if isinstance(content, bytes):
                            content = content.decode("utf-8")
                        total_lines += len(content.splitlines())

                output.extend(
                    [
                        "",
                        "💡 Changes applied to virtual files in memory.",
                        "🔧 Use auto_commit=True to commit changes to memory repository.",
                        f"📋 Summary: {len(modified_files)} files modified, {total_lines} total lines",
                    ]
                )

                return "\n".join(output)

        except Exception as e:
            return f"❌ Virtual patch creation failed: {str(e)}"

    def _perform_memory_operations(
        self,
        files: List[str],
        branch_name: str,
        commit_message: str,
        auto_push: bool,
        analyzer,
        real_push: bool = False,
    ) -> str:
        """Perform memory repository operations: create branch, commit, and optionally push"""

        try:
            # Get repository URL early to avoid scope issues
            repo_url = analyzer.repo_info.url
            operations_log = [f"📂 Memory Repository: {repo_url}"]

            # Import dulwich components
            from dulwich.repo import MemoryRepo
            from dulwich.objects import Blob, Tree, Commit
            from dulwich.client import get_transport_and_path
            from dulwich import porcelain
            from datetime import datetime, timezone
            import hashlib

            operations_log.append(f"📍 Base branch: {analyzer.repo_info.branch}")

            # Create memory repository for truly in-memory operations
            memory_repo = MemoryRepo()

            # Get authentication credentials
            auth_username = getattr(analyzer, "username", None)
            auth_password = getattr(analyzer, "password", None)

            operations_log.append("🔄 Setting up in-memory repository...")

            try:
                # Fetch original repository state into memory
                fetch_url = repo_url
                if auth_username and auth_password:
                    fetch_url = repo_url.replace(
                        "https://", f"https://{auth_username}:{auth_password}@"
                    )

                # Fetch to memory repository
                from dulwich.client import get_transport_and_path

                client, path = get_transport_and_path(fetch_url)
                remote_refs = client.fetch(path, memory_repo)
                operations_log.append(f"📥 Fetched repository to memory")

                # Get HEAD commit
                main_ref = f"refs/heads/{analyzer.repo_info.branch}".encode()
                if main_ref in remote_refs:
                    head_commit_id = remote_refs[main_ref]
                    head_commit = memory_repo[head_commit_id]

                    # Create blobs for modified files only
                    patches_applied = 0
                    for file_path in files:
                        if file_path in analyzer.virtual_files:
                            virtual_file = analyzer.virtual_files[file_path]
                            if hasattr(virtual_file, "content"):
                                content = virtual_file.content
                                if isinstance(content, bytes):
                                    file_content = content
                                else:
                                    file_content = content.encode("utf-8")

                                # Create blob for modified file
                                blob = Blob.from_string(file_content)
                                memory_repo.object_store.add_object(blob)
                                patches_applied += 1
                                operations_log.append(f"🔧 Patched: {file_path}")

                    # Create new tree based on original with modifications
                    from dulwich.diff_tree import tree_changes

                    original_tree = memory_repo[head_commit.tree]

                    # Build new tree with changes
                    tree_items = list(original_tree.items())

                    # Update modified files
                    for file_path in files:
                        if file_path in analyzer.virtual_files:
                            virtual_file = analyzer.virtual_files[file_path]
                            if hasattr(virtual_file, "content"):
                                content = virtual_file.content
                                if isinstance(content, bytes):
                                    file_content = content
                                else:
                                    file_content = content.encode("utf-8")

                                blob = Blob.from_string(file_content)
                                memory_repo.object_store.add_object(blob)

                                # Replace or add file in tree
                                file_path_bytes = file_path.encode("utf-8")
                                tree_items = [
                                    (name, mode, sha)
                                    for name, mode, sha in tree_items
                                    if name != file_path_bytes
                                ]
                                tree_items.append((file_path_bytes, 0o100644, blob.id))

                    # Create new tree
                    new_tree = Tree()
                    for name, mode, sha in tree_items:
                        new_tree.add(name, mode, sha)
                    memory_repo.object_store.add_object(new_tree)

                    # Create commit
                    from datetime import datetime, timezone

                    # Get actual git config or use environment variables
                    author_name = os.getenv("GIT_AUTHOR_NAME", "Logan Assistant")
                    author_email = os.getenv("GIT_AUTHOR_EMAIL", "logan@assistant.com")
                    author = committer = f"{author_name} <{author_email}>".encode()
                    commit_time = int(datetime.now(timezone.utc).timestamp())

                    commit = Commit()
                    commit.tree = new_tree.id
                    commit.parents = [head_commit_id]
                    commit.author = author
                    commit.committer = committer
                    commit.commit_time = commit_time
                    commit.author_time = commit_time
                    commit.commit_timezone = 0
                    commit.author_timezone = 0
                    commit.encoding = b"UTF-8"
                    commit.message = commit_message.encode("utf-8")

                    memory_repo.object_store.add_object(commit)
                    commit_hash = commit.id.decode("ascii")[:8]
                    operations_log.append(f"💾 Created commit: {commit_hash}")

                    # Update branch ref
                    memory_repo.refs[f"refs/heads/{branch_name}".encode("utf-8")] = (
                        commit.id
                    )
                    operations_log.append(f"🌿 Updated branch: {branch_name}")

                else:
                    operations_log.append(
                        "❌ Could not find main branch in remote refs"
                    )
                    return "\n".join(operations_log)

            except Exception as fetch_error:
                operations_log.append(f"❌ Memory operations failed: {fetch_error}")
                return "\n".join(operations_log)

            if auto_push and real_push and repo_url:
                try:
                    # Perform REAL push from memory repository
                    operations_log.append("🚨 PERFORMING REAL GIT PUSH TO ORIGIN!")

                    push_url = fetch_url  # Use same authenticated URL
                    operations_log.append(f"🚀 Pushing to: {repo_url}")
                    operations_log.append(f"🌿 Branch: {branch_name}")

                    # Push directly from memory repository
                    def update_refs(remote_refs):
                        return {f"refs/heads/{branch_name}".encode(): commit.id}

                    client.send_pack(
                        path,
                        update_refs,
                        memory_repo.object_store.generate_pack_data,
                    )

                    operations_log.append(f"✅ Successfully pushed to: {repo_url}")
                    operations_log.append(f"🌿 Branch: {branch_name}")
                    operations_log.append(f"📝 Commit: {commit_hash}")
                    operations_log.append("🎉 Memory push completed!")

                except Exception as push_error:
                    operations_log.append(f"❌ Real push failed: {push_error}")
                    operations_log.append("💡 Falling back to simulation mode")
                    operations_log.append(f"🚀 Ready to push to: {repo_url}")
                    operations_log.append(f"🌿 Branch {branch_name} prepared for push")

            elif auto_push and not real_push:
                operations_log.append(f"🚀 Ready to push to: {repo_url}")
                operations_log.append(f"🌿 Branch {branch_name} prepared for push")
                operations_log.append("💡 Set real_push=True to enable actual pushing")

            operations_log.extend(
                [
                    "",
                    f"🎉 Memory operations completed successfully!",
                    f"📝 Commit ID: {commit_hash}",
                    f"🌿 Branch: {branch_name}",
                    f"📊 Files committed: {len(files)}",
                    "",
                    "💡 This commit exists in memory and can be applied to the real repository",
                ]
            )

            return "\n".join(operations_log)

        except ImportError as e:
            return f"❌ Dulwich import failed: {e}. Install with: pip install dulwich"
        except Exception as e:
            return f"❌ Memory operations failed: {str(e)}"

    def _apply_llm_code_changes(self, analyzer, files_data, description):
        """Apply LLM-specified code changes to virtual files"""
        try:
            total_changes = 0

            for file_data in files_data:
                file_path = file_data.get("path")
                changes = file_data.get("changes", [])

                if not file_path or not changes:
                    continue

                if file_path in analyzer.virtual_files:
                    virtual_file = analyzer.virtual_files[file_path]
                    if hasattr(virtual_file, "content"):
                        content = virtual_file.content
                        if isinstance(content, bytes):
                            content = content.decode("utf-8")

                        lines = content.split("\n")
                        changes_applied = 0

                        # Sort changes by line number (descending) to avoid line number shifts
                        sorted_changes = sorted(
                            changes, key=lambda x: x.get("line", 0), reverse=True
                        )

                        for change in sorted_changes:
                            line_num = change.get("line")
                            old_content = change.get("old_content", "").strip()
                            new_content = change.get("new_content", "").strip()

                            if line_num and old_content and line_num <= len(lines):
                                # Check if line matches expected content (with some flexibility for whitespace)
                                actual_line = lines[line_num - 1].strip()
                                if (
                                    old_content in actual_line
                                    or actual_line in old_content
                                ):
                                    # Replace the line
                                    lines[line_num - 1] = lines[line_num - 1].replace(
                                        old_content, new_content
                                    )
                                    changes_applied += 1
                                    print(
                                        f"🔧 Applied change at line {line_num}: {old_content} -> {new_content}"
                                    )
                                else:
                                    print(
                                        f"⚠️  Line {line_num} content mismatch. Expected: {old_content}, Found: {actual_line}"
                                    )

                        if changes_applied > 0:
                            # Update virtual file content
                            new_content = "\n".join(lines)
                            virtual_file.content = (
                                new_content.encode("utf-8")
                                if isinstance(virtual_file.content, bytes)
                                else new_content
                            )
                            print(
                                f"✅ Updated {file_path} with {changes_applied} changes"
                            )
                            total_changes += changes_applied

            if total_changes > 0:
                print(f"🎯 Applied {total_changes} LLM-specified code changes")
                return True
            else:
                print("⚠️  No code changes were applied")
                return False

        except Exception as e:
            print(f"⚠️  Could not apply LLM code changes: {e}")
            return False

    def _normalize_line_endings(self, text):
        """Normalize line endings to Unix format"""
        return text.replace("\r\n", "\n").replace("\r", "\n") if text else ""

    def _check_line(self, content_line, patch_line):
        """Check if lines match, ignoring certain punctuation and whitespace"""
        import string

        # Ignore line endings like .,. This helps for example with extending arrays.
        content_stripped = content_line.strip(string.whitespace + ".,")
        patch_stripped = patch_line.strip(string.whitespace + ".,")
        return content_stripped == patch_stripped

    def _parse_unified_diff(self, diff_text):
        """Parse unified diff format and return source, target, and hunks"""
        lines = self._normalize_line_endings(diff_text).splitlines()

        if (
            len(lines) < 3
            or not lines[0].startswith("--- ")
            or not lines[1].startswith("+++ ")
        ):
            raise ValueError("Invalid diff format")

        source_file = lines[0][4:]
        target_file = lines[1][4:]

        hunks = []
        hunk = []

        for i, line in enumerate(lines[2:]):
            if line.startswith("@@"):
                if len(hunk) > 0:
                    hunks.append(hunk)
                hunk = []
            else:
                if len(hunk) == 0 and line.strip() == "":
                    # Skip first empty line of the patch
                    continue
                hunk.append(line)

        if hunk:
            hunks.append(hunk)

        # Remove a/ and b/ prefixes if present
        if source_file.startswith("a/"):
            source_file = source_file[2:]
        if target_file.startswith("b/"):
            target_file = target_file[2:]

        return source_file, target_file, hunks

    def _apply_git_patch_to_virtual_files(self, analyzer, files, patch_content):
        """Apply standard git diff patch to virtual files using pattern-based matching"""
        try:
            if not patch_content.strip():
                return "⚠️  No patch content provided"

            try:
                source_file, target_file, hunks = self._parse_unified_diff(
                    patch_content
                )
            except ValueError as e:
                # Try pattern-based approach if unified diff parsing fails
                return self._apply_pattern_based_patch(analyzer, files, patch_content)

            # Use target file for the patch application
            file_path = target_file

            if file_path not in files:
                return f"⚠️  File {file_path} not in target files list"

            if file_path not in analyzer.virtual_files:
                return f"⚠️  File {file_path} not found in virtual files"

            virtual_file = analyzer.virtual_files[file_path]
            if not hasattr(virtual_file, "content"):
                return f"⚠️  File {file_path} has no content"

            # Get current content
            content = virtual_file.content
            if isinstance(content, bytes):
                content = content.decode("utf-8")

            # First try context-based patch application
            try:
                new_content = self._apply_patch_to_text(content, patch_content)
                virtual_file.content = (
                    new_content.encode("utf-8")
                    if isinstance(virtual_file.content, bytes)
                    else new_content
                )
                return "✅ Git patch applied successfully"
            except Exception as context_error:
                print(f"⚠️  Context-based patch failed: {context_error}")
                # Fallback to pattern-based approach
                return self._apply_pattern_based_patch(analyzer, files, patch_content)

        except Exception as e:
            return f"❌ Failed to apply git patch: {e}"

    def _apply_patch_to_text(self, content, diff_text):
        """Apply unified diff to text content - adapted from apply_patch_to_ytext"""
        _, _, hunks = self._parse_unified_diff(diff_text)
        content_lines = content.split("\n")

        for hunk_index, hunk in enumerate(hunks):
            additions = sum(1 for line in hunk if line.startswith("+"))
            deletions = sum(1 for line in hunk if line.startswith("-"))

            if additions == 0 and deletions == 0:
                continue

            # Check if patch is already applied
            def test_if_already_applied():
                for i in range(len(content_lines)):
                    j = 0
                    valid = True

                    for line in hunk:
                        if line.startswith("+"):
                            # Expect this line if already applied
                            if i + j < len(content_lines) and self._check_line(
                                content_lines[i + j], line[1:]
                            ):
                                valid = valid and True
                            else:
                                valid = False
                        elif line.startswith("-") and i + j < len(content_lines):
                            # Don't expect this line if already applied
                            if self._check_line(content_lines[i + j], line[1:]):
                                continue
                            else:
                                valid = valid and True
                                continue
                        elif i + j < len(content_lines) and self._check_line(
                            content_lines[i + j], line
                        ):
                            valid = valid and True
                        elif (
                            i + j < len(content_lines)
                            and j > 0
                            and content_lines[i + j].strip() == ""
                        ):
                            pass
                        elif j > 0 and line.strip() == "":
                            continue
                        else:
                            valid = False

                        if not valid:
                            break
                        j += 1

                    if valid:
                        return True
                return False

            if test_if_already_applied():
                print(f"⚠️  Hunk {hunk_index} already applied")
                continue

            # Search for hunk location
            found_indices = []
            for i in range(len(content_lines)):
                j = 0
                valid = True

                for line in hunk:
                    if i + j < len(content_lines) and self._check_line(
                        content_lines[i + j], line
                    ):
                        valid = valid and True
                    elif line.startswith("+"):
                        continue
                    elif line.startswith("-") and i + j < len(content_lines):
                        valid = valid and self._check_line(
                            content_lines[i + j], line[1:]
                        )
                    elif (
                        i + j < len(content_lines)
                        and j > 0
                        and content_lines[i + j].strip() == ""
                    ):
                        pass
                    elif j > 0 and line.strip() == "":
                        continue
                    else:
                        valid = False

                    if not valid:
                        break
                    j += 1

                if valid:
                    found_indices.append(i)

            if len(found_indices) == 0:
                raise Exception(
                    f"Hunk {hunk_index} cannot be applied: context mismatch"
                )

            if len(found_indices) > 1:
                raise Exception(
                    f"Hunk {hunk_index} cannot be applied: multiple matches found"
                )

            # Apply the hunk
            i = found_indices[0]

            for line in hunk:
                if i < len(content_lines) and self._check_line(content_lines[i], line):
                    print(f"🔧 Found context line: {line}")
                    i += 1
                elif line.startswith("-"):
                    if i < len(content_lines):
                        removed_line = content_lines.pop(i)
                        print(f"🔧 Removed line {i}: {removed_line.strip()}")
                    else:
                        raise Exception(f"Could not find line to delete: {line[1:]}")
                elif line.startswith("+"):
                    content_lines.insert(i, line[1:])
                    print(f"🔧 Added line {i}: {line[1:].strip()}")
                    i += 1
                elif i < len(content_lines) and content_lines[i].strip() == "":
                    i += 1
                elif line.strip() == "":
                    continue
                else:
                    raise Exception(
                        f"Could not apply hunk {hunk_index}: expected {line}, got {content_lines[i] if i < len(content_lines) else 'EOF'}"
                    )

        return "\n".join(content_lines)

    def _apply_pattern_based_patch(self, analyzer, files, patch_content):
        """Apply patch using pattern-based matching instead of line numbers"""
        try:
            changes_applied = 0

            # Extract simple replacements from patch content
            replacements = self._extract_replacements_from_patch(patch_content)

            if not replacements:
                return "⚠️  No replacements found in patch"

            # Apply to each target file
            for file_path in files:
                if file_path not in analyzer.virtual_files:
                    print(f"⚠️  File {file_path} not found in virtual files")
                    continue

                virtual_file = analyzer.virtual_files[file_path]
                if not hasattr(virtual_file, "content"):
                    print(f"⚠️  File {file_path} has no content")
                    continue

                content = virtual_file.content
                if isinstance(content, bytes):
                    content = content.decode("utf-8")

                # Apply each replacement
                for old_pattern, new_pattern in replacements:
                    if old_pattern in content:
                        content = content.replace(old_pattern, new_pattern, 1)
                        print(
                            f"🔧 Pattern replaced in {file_path}: {old_pattern[:50]}... → {new_pattern[:50]}..."
                        )
                        changes_applied += 1
                    else:
                        # Try more flexible matching
                        old_stripped = old_pattern.strip()
                        if old_stripped and old_stripped in content:
                            # Find the line and replace it while preserving indentation
                            lines = content.split("\n")
                            for i, line in enumerate(lines):
                                if old_stripped in line.strip():
                                    # Preserve original indentation
                                    indent = line[: len(line) - len(line.lstrip())]
                                    lines[i] = indent + new_pattern.strip()
                                    content = "\n".join(lines)
                                    print(
                                        f"🔧 Flexible pattern replaced in {file_path}: {old_stripped[:50]}..."
                                    )
                                    changes_applied += 1
                                    break

                # Update virtual file content
                virtual_file.content = (
                    content.encode("utf-8")
                    if isinstance(virtual_file.content, bytes)
                    else content
                )

            if changes_applied > 0:
                print(f"🎯 Applied {changes_applied} pattern-based changes")
                return "✅ Pattern-based patch applied successfully"
            else:
                return "⚠️  No pattern-based changes applied"

        except Exception as e:
            return f"❌ Pattern-based patch failed: {e}"

    def _extract_replacements_from_patch(self, patch_content):
        """Extract simple old->new replacements from patch content"""
        replacements = []
        lines = patch_content.strip().split("\n")

        # Look for - and + line pairs
        i = 0
        while i < len(lines):
            line = lines[i]

            # Skip headers and context
            if (
                line.startswith("---")
                or line.startswith("+++")
                or line.startswith("@@")
            ):
                i += 1
                continue

            # Look for removal followed by addition
            if (
                line.startswith("-")
                and i + 1 < len(lines)
                and lines[i + 1].startswith("+")
            ):
                old_line = line[1:].strip()  # Remove '-' and whitespace
                new_line = lines[i + 1][1:].strip()  # Remove '+' and whitespace

                if old_line and new_line and old_line != new_line:
                    replacements.append((old_line, new_line))
                    print(f"📋 Found replacement: {old_line} → {new_line}")

                i += 2  # Skip both lines
            else:
                i += 1

        return replacements

    def _apply_search_replace(
        self, analyzer, file_path: str, search_text: str, replace_text: str
    ) -> str:
        """Apply simple search and replace to a file in memory repository"""
        try:
            # Check if file exists in virtual files
            if file_path not in analyzer.virtual_files:
                return f"❌ {file_path}: File not found in virtual files"

            virtual_file = analyzer.virtual_files[file_path]
            if not hasattr(virtual_file, "content"):
                return f"❌ {file_path}: File has no content"

            # Get current content
            content = virtual_file.content
            if isinstance(content, bytes):
                content = content.decode("utf-8")

            # Check if search text exists
            if search_text not in content:
                return f"❌ {file_path}: Search text not found: '{search_text[:50]}...'"

            # Count occurrences
            occurrences = content.count(search_text)

            # Perform replacement
            new_content = content.replace(search_text, replace_text)

            # Update virtual file
            virtual_file.content = (
                new_content.encode("utf-8")
                if isinstance(virtual_file.content, bytes)
                else new_content
            )

            return f"✅ {file_path}: Replaced {occurrences} occurrence(s)"

        except Exception as e:
            return f"❌ {file_path}: Error during replacement: {e}"

    def _apply_unified_patch(self, analyzer, patch_content: str) -> str:
        """Apply unified diff patch using Python's difflib or external patch module"""
        try:
            # Try to use the `patch` module if available
            try:
                import patch

                # Parse the patch
                patchset = patch.fromstring(patch_content)

                results = []
                for patched_file in patchset:
                    file_path = patched_file.target_file.lstrip("b/")

                    # Check if file exists in virtual files
                    if file_path not in analyzer.virtual_files:
                        results.append(
                            f"❌ {file_path}: File not found in virtual files"
                        )
                        continue

                    virtual_file = analyzer.virtual_files[file_path]
                    if not hasattr(virtual_file, "content"):
                        results.append(f"❌ {file_path}: File has no content")
                        continue

                    # Get current content
                    content = virtual_file.content
                    if isinstance(content, bytes):
                        content = content.decode("utf-8")

                    # Apply patch
                    original_lines = content.splitlines(keepends=True)

                    # Apply hunks
                    modified_lines = original_lines.copy()
                    offset = 0

                    for hunk in patched_file:
                        # Apply hunk with offset adjustment
                        target_line = hunk.target_start - 1 + offset

                        # Remove old lines
                        for i in range(hunk.target_length):
                            if target_line < len(modified_lines):
                                modified_lines.pop(target_line)

                        # Insert new lines
                        for line in hunk.target_lines():
                            modified_lines.insert(target_line, line)
                            target_line += 1

                        # Update offset for next hunk
                        offset += len(hunk.target_lines()) - hunk.target_length

                    # Update virtual file
                    new_content = "".join(modified_lines)
                    virtual_file.content = (
                        new_content.encode("utf-8")
                        if isinstance(virtual_file.content, bytes)
                        else new_content
                    )

                    results.append(
                        f"✅ {file_path}: Applied {len(patched_file)} hunk(s)"
                    )

                return "\n".join(results)

            except ImportError:
                # Fallback to manual parsing
                return self._apply_unified_patch_manual(analyzer, patch_content)

        except Exception as e:
            return f"❌ Error applying unified patch: {e}"

    def _apply_unified_patch_manual(self, analyzer, patch_content: str) -> str:
        """Manual unified patch parsing when patch module not available"""
        try:
            lines = patch_content.strip().split("\n")
            results = []

            current_file = None
            current_hunks = []

            i = 0
            while i < len(lines):
                line = lines[i]

                # Look for file headers
                if line.startswith("--- a/") or line.startswith("--- "):
                    if current_file and current_hunks:
                        # Process previous file
                        result = self._apply_hunks_to_file(
                            analyzer, current_file, current_hunks
                        )
                        results.append(result)

                    # Start new file
                    current_file = line[6:] if line.startswith("--- a/") else line[4:]
                    current_hunks = []

                elif line.startswith("+++ "):
                    # Confirm target file (could be different from source)
                    target_file = line[6:] if line.startswith("+++ b/") else line[4:]
                    current_file = target_file

                elif line.startswith("@@"):
                    # Hunk header - parse it
                    hunk_header = line
                    hunk_lines = []

                    # Collect hunk lines
                    i += 1
                    while (
                        i < len(lines)
                        and not lines[i].startswith("@@")
                        and not lines[i].startswith("---")
                    ):
                        if (
                            lines[i].startswith(" ")
                            or lines[i].startswith("+")
                            or lines[i].startswith("-")
                        ):
                            hunk_lines.append(lines[i])
                        i += 1
                    i -= 1  # Back up one since we'll increment at end of loop

                    current_hunks.append((hunk_header, hunk_lines))

                i += 1

            # Process final file
            if current_file and current_hunks:
                result = self._apply_hunks_to_file(
                    analyzer, current_file, current_hunks
                )
                results.append(result)

            return "\n".join(results) if results else "❌ No files found in patch"

        except Exception as e:
            return f"❌ Error in manual patch parsing: {e}"

    def _apply_hunks_to_file(self, analyzer, file_path: str, hunks: list) -> str:
        """Apply a list of hunks to a specific file"""
        try:
            # Check if file exists
            if file_path not in analyzer.virtual_files:
                return f"❌ {file_path}: File not found in virtual files"

            virtual_file = analyzer.virtual_files[file_path]
            if not hasattr(virtual_file, "content"):
                return f"❌ {file_path}: File has no content"

            # Get current content
            content = virtual_file.content
            if isinstance(content, bytes):
                content = content.decode("utf-8")

            lines = content.splitlines()

            # Apply each hunk
            for hunk_header, hunk_lines in hunks:
                # Parse hunk header to get line numbers
                # Format: @@ -old_start,old_count +new_start,new_count @@
                import re

                match = re.match(
                    r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", hunk_header
                )
                if not match:
                    continue

                old_start = int(match.group(1)) - 1  # Convert to 0-based
                new_start = int(match.group(3)) - 1  # Convert to 0-based

                # Apply the hunk
                lines = self._apply_single_hunk(lines, old_start, hunk_lines)

            # Update virtual file
            new_content = "\n".join(lines)
            virtual_file.content = (
                new_content.encode("utf-8")
                if isinstance(virtual_file.content, bytes)
                else new_content
            )

            return f"✅ {file_path}: Applied {len(hunks)} hunk(s)"

        except Exception as e:
            return f"❌ {file_path}: Error applying hunks: {e}"

    def _apply_single_hunk(
        self, lines: list, start_line: int, hunk_lines: list
    ) -> list:
        """Apply a single hunk to file lines"""
        result_lines = lines.copy()

        # Process hunk lines
        line_offset = 0
        current_line = start_line

        for hunk_line in hunk_lines:
            if hunk_line.startswith(" "):
                # Context line - just advance
                current_line += 1
            elif hunk_line.startswith("-"):
                # Remove line
                if current_line + line_offset < len(result_lines):
                    result_lines.pop(current_line + line_offset)
                    line_offset -= 1
            elif hunk_line.startswith("+"):
                # Add line
                new_line = hunk_line[1:]  # Remove the '+'
                result_lines.insert(current_line + line_offset + 1, new_line)
                line_offset += 1
                current_line += 1

        return result_lines


class DulwichApplyPatchTool(BaseTool if AWS_AVAILABLE else object):
    """Tool for applying unified diff patches to the memory repository"""

    name: str = "apply_patch"
    description: str = """Apply unified diff patches to files in the memory repository.

CRITICAL: Before creating patches, you MUST:
1. Use preview_code or grep_content tools to see the ACTUAL current file content
2. Base your patch on the EXACT content that exists, not assumptions
3. Ensure the patch context lines match the real file content exactly

This tool applies patches using intelligent pattern matching and updates both memory and Git repositories."""
    args_schema: type = ApplyPatchInput if AWS_AVAILABLE else None
    analyzer_ref: object = None

    def __init__(self, analyzer_ref):
        super().__init__() if AWS_AVAILABLE else None
        object.__setattr__(self, "analyzer_ref", analyzer_ref)

    def _run(
        self,
        patch_content: str,
        target_branch: str = "main",
        create_branch: bool = True,
        branch_name: str = "",
        auto_apply: bool = False,
        auto_commit: bool = False,
        auto_push: bool = False,
        commit_message: str = "",
        repository_path: str = "",
        force_apply: bool = False,
        real_push: bool = True,
    ) -> str:
        # Debug logging for patch push configuration
        print(
            f"🔧 apply_patch called with: auto_apply={auto_apply}, auto_push={auto_push}, real_push={real_push}"
        )

        # Auto-enable auto_push when auto_apply=True (default behavior)
        if auto_apply and not auto_push:
            auto_push = True
            print(f"🔧 Auto-enabled auto_push because auto_apply=True")

        # Auto-enable real_push when auto_push is True
        if auto_push and not real_push:
            real_push = True
            print(f"🔧 Auto-enabled real_push because auto_push=True")
        analyzer = self.analyzer_ref.analyzer
        if not analyzer:
            return "❌ No repository loaded. Load a repository first."

        try:
            if not hasattr(analyzer, "virtual_files"):
                return "❌ No virtual file system available."

            # Parse patch content using unidiff library
            from unidiff import PatchSet

            try:
                patchset = PatchSet(patch_content)
            except Exception as e:
                return f"❌ Failed to parse patch content: {e}"

            # Extract patch metadata from comments and patch structure
            patch_info = {
                "files_modified": [],
                "description": "",
                "original_branch": "",
                "commit_message": "",
            }

            diff_sections = []
            patch_lines = patch_content.strip().split("\n")

            # Extract metadata from comment lines
            for line in patch_lines:
                if line.startswith("# Patch:"):
                    patch_info["description"] = line.replace("# Patch:", "").strip()
                elif line.startswith("# Commit message:"):
                    patch_info["commit_message"] = line.replace(
                        "# Commit message:", ""
                    ).strip()
                elif line.startswith("# Base branch:"):
                    patch_info["original_branch"] = line.replace(
                        "# Base branch:", ""
                    ).strip()

            # Extract file information from parsed patch
            for patched_file in patchset:
                file_path = patched_file.path
                # Remove a/ or b/ prefix if present
                if file_path.startswith("a/"):
                    file_path = file_path[2:]
                elif file_path.startswith("b/"):
                    file_path = file_path[2:]

                if file_path not in patch_info["files_modified"]:
                    patch_info["files_modified"].append(file_path)

                # Record diff sections (hunks)
                for hunk in patched_file:
                    diff_sections.append(
                        {
                            "file": file_path,
                            "section": f"@@ -{hunk.source_start},{hunk.source_length} +{hunk.target_start},{hunk.target_length} @@",
                        }
                    )

            # Generate branch name if not provided
            if create_branch and not branch_name:
                from datetime import datetime

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                branch_name = f"patch_apply_{timestamp}"

            # Get repository info
            repo_info = getattr(analyzer, "repo_info", None)

            # Check if target files exist in virtual file system
            file_analysis = []
            for file_path in patch_info["files_modified"]:
                if file_path in analyzer.virtual_files:
                    virtual_file = analyzer.virtual_files[file_path]
                    if hasattr(virtual_file, "content"):
                        line_count = len(virtual_file.content.splitlines())
                        file_analysis.append(
                            f"✅ {file_path} - Available ({line_count} lines)"
                        )
                    else:
                        file_analysis.append(
                            f"⚠️  {file_path} - Available but no content"
                        )
                else:
                    file_analysis.append(f"❌ {file_path} - Not found in virtual files")

            output = [
                f"🔍 Patch Analysis Complete!",
                f"📝 Description: {patch_info.get('description', 'No description')}"
                if patch_info.get("description")
                else "",
                f"🎯 Target branch: {target_branch}",
                f"🌿 New branch: {branch_name}"
                if create_branch
                else f"🌿 Direct application to: {target_branch}",
            ]

            if repo_info:
                output.extend(
                    [
                        f"📊 Current repository: {repo_info.url}",
                        f"🌿 Current branch: {repo_info.branch}",
                    ]
                )

            if patch_info.get("original_branch"):
                output.append(f"🔄 Patch from branch: {patch_info['original_branch']}")

            output.extend(
                [
                    "",
                    "📋 Files to be modified:",
                ]
            )

            if file_analysis:
                output.extend([f"   {analysis}" for analysis in file_analysis])
            else:
                output.append("   ℹ️  No files identified in patch")

            if diff_sections:
                output.extend(
                    [
                        "",
                        f"📦 Diff sections found: {len(diff_sections)}",
                    ]
                )
                for i, section in enumerate(
                    diff_sections[:5], 1
                ):  # Show first 5 sections
                    output.append(f"   {i}. {section['file']}: {section['section']}")
                if len(diff_sections) > 5:
                    output.append(f"   ... and {len(diff_sections) - 5} more sections")

            output.extend(
                [
                    "",
                    "💡 Application Strategy:",
                    f"   1. The patch content has been analyzed",
                    f"   2. {len(patch_info['files_modified'])} files would be affected",
                    f"   3. Virtual file system compatibility: {len([f for f in file_analysis if f.startswith('✅')])}/{len(file_analysis)} files available",
                    "",
                    "🔧 To apply this patch to a real repository:",
                    f"   1. git checkout {target_branch}",
                    f"   2. git checkout -b {branch_name}"
                    if create_branch
                    else f"   2. Apply directly to {target_branch}",
                    "   3. Save patch content to a .patch file",
                    "   4. git apply <patch-file>",
                    "   5. Review and commit changes",
                ]
            )

            if patch_info.get("commit_message"):
                output.extend(
                    [
                        "",
                        f"📝 Suggested commit message: {patch_info['commit_message']}",
                    ]
                )

            # Show patch preview - show complete diff sections instead of truncating
            if len(patch_lines) > 0:
                output.extend(["", "📋 Patch Preview:", "```diff"])

                # Find complete diff sections to show
                preview_lines = []
                in_diff_section = False
                section_count = 0
                max_sections = 3  # Show up to 3 complete diff sections

                for line in patch_lines:
                    if line.startswith("diff --git") or line.startswith("@@"):
                        if section_count >= max_sections:
                            break
                        if line.startswith("diff --git"):
                            if in_diff_section:
                                section_count += 1
                            in_diff_section = True

                    if section_count < max_sections:
                        preview_lines.append(line)
                    elif line.startswith("@@"):
                        # Start of a new section we won't show
                        break

                if preview_lines:
                    output.extend(preview_lines)
                    if len(patch_lines) > len(preview_lines):
                        remaining_lines = len(patch_lines) - len(preview_lines)
                        # Show focused remaining content
                        max_remaining = 30
                        if remaining_lines <= max_remaining:
                            output.extend(patch_lines[len(preview_lines) :])
                        else:
                            # Show some of the remaining content
                            output.extend(
                                patch_lines[
                                    len(preview_lines) : len(preview_lines)
                                    + max_remaining // 2
                                ]
                            )
                            output.append(
                                f"@@ ... ({remaining_lines - max_remaining} more patch lines) ... @@"
                            )
                            output.extend(patch_lines[-max_remaining // 2 :])
                else:
                    # Show focused patch content
                    max_patch_display = 40
                    if len(patch_lines) <= max_patch_display:
                        output.extend(patch_lines)
                    else:
                        output.extend(patch_lines[: max_patch_display // 2])
                        output.append(
                            f"@@ ... ({len(patch_lines) - max_patch_display} lines) ... @@"
                        )
                        output.extend(patch_lines[-max_patch_display // 2 :])

                output.append("```")

            # Handle real git operations if requested
            if auto_apply:
                # First apply patch to virtual files in memory
                patch_apply_result = self._apply_patch_to_virtual_files(
                    analyzer, patch_info["files_modified"], patch_content
                )
                output.extend(["", "📦 Patch Application to Virtual Files:"])
                output.extend([f"   {patch_apply_result}"])

                # If patch application succeeded, also do Git operations
                if "successfully" in patch_apply_result:
                    memory_result = self._apply_patch_to_memory_repository(
                        patch_content,
                        target_branch,
                        create_branch,
                        branch_name,
                        auto_commit,
                        auto_push,
                        commit_message,
                        patch_info,
                        real_push,
                    )
                    output.extend(["", "📦 Git Repository Operations:"])
                    output.extend([memory_result])
                    output.extend(["", "🔧 Memory Repository Operations:"])
                    output.extend(
                        [
                            f"   {line}"
                            for line in memory_result.split("\n")
                            if line.strip()
                        ]
                    )
                else:
                    output.extend(
                        [
                            "",
                            "⚠️  Skipping Git operations due to patch application failure",
                        ]
                    )
            else:
                output.extend(
                    [
                        "",
                        "🚀 Patch application with automatic push enabled by default:",
                        f"   auto_apply=True, auto_push=True (automatically pushes to origin)",
                    ]
                )

            return "\n".join(output)

        except Exception as e:
            return f"❌ Patch analysis failed: {str(e)}"

    def _apply_patch_to_memory_repository(
        self,
        patch_content: str,
        target_branch: str,
        create_branch: bool,
        branch_name: str,
        auto_commit: bool,
        auto_push: bool,
        commit_message: str,
        patch_info: dict,
        real_push: bool = False,
    ) -> str:
        """Apply patch to memory repository"""
        from datetime import datetime

        analyzer = self.analyzer_ref.analyzer
        if not analyzer:
            return "❌ No repository loaded."

        try:
            operations_log = [f"📂 Memory Repository: {analyzer.repo_info.url}"]

            operations_log.append(f"📍 Base branch: {analyzer.repo_info.branch}")

            # Generate branch name if needed
            if create_branch and not branch_name:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                branch_name = f"patch_apply_{timestamp}"

            operations_log.append(
                f"🌿 Target branch: {branch_name if create_branch else target_branch}"
            )

            # Parse patch content to extract changes
            changes_applied = 0
            for file_path in patch_info["files_modified"]:
                if file_path in analyzer.virtual_files:
                    operations_log.append(f"📝 Would modify: {file_path}")
                    changes_applied += 1

            operations_log.append(f"📊 Files that would be modified: {changes_applied}")

            # Memory commit if requested
            if auto_commit:
                # Generate commit message if not provided
                if not commit_message:
                    commit_message = patch_info.get(
                        "commit_message",
                        f"Apply patch: {patch_info.get('description', 'patch application')}",
                    )

                # Perform memory operations
                memory_result = self._perform_memory_operations(
                    patch_info["files_modified"],
                    branch_name if create_branch else target_branch,
                    commit_message,
                    auto_push,
                    analyzer,
                    real_push,
                )

                operations_log.append("💾 Memory commit operations:")
                for line in memory_result.split("\n"):
                    if line.strip():
                        operations_log.append(f"   {line}")

            return "\n".join(operations_log)
        except Exception as e:
            return f"❌ Memory patch application failed: {str(e)}"

    def _apply_patch_to_virtual_files(self, analyzer, files, patch_content):
        """Apply patch directly to virtual files in the analyzer"""
        try:
            if not patch_content.strip():
                return "⚠️  No patch content provided"

            changes_applied = 0

            # Extract simple replacements from patch content
            replacements = self._extract_replacements_from_patch(patch_content)

            if not replacements:
                return "⚠️  No replacements found in patch"

            # Apply to each target file
            for file_path in files:
                if file_path not in analyzer.virtual_files:
                    print(f"⚠️  File {file_path} not found in virtual files")
                    continue

                virtual_file = analyzer.virtual_files[file_path]
                if not hasattr(virtual_file, "content"):
                    print(f"⚠️  File {file_path} has no content")
                    continue

                content = virtual_file.content
                if isinstance(content, bytes):
                    content = content.decode("utf-8")

                # Apply each replacement with enhanced matching strategies
                pattern_found = False
                for old_pattern, new_pattern in replacements:
                    if old_pattern in content:
                        content = content.replace(old_pattern, new_pattern, 1)
                        print(
                            f"🔧 Pattern replaced in {file_path}: {old_pattern[:50]}... → {new_pattern[:50]}..."
                        )
                        changes_applied += 1
                        pattern_found = True
                    else:
                        # Try more flexible matching strategies
                        old_stripped = old_pattern.strip()
                        if old_stripped and old_stripped in content:
                            # Find the line and replace it while preserving indentation
                            lines = content.split("\n")
                            for i, line in enumerate(lines):
                                if old_stripped in line.strip():
                                    # Preserve original indentation
                                    indent = line[: len(line) - len(line.lstrip())]
                                    lines[i] = indent + new_pattern.strip()
                                    content = "\n".join(lines)
                                    print(
                                        f"🔧 Flexible pattern replaced in {file_path}: {old_stripped[:50]}..."
                                    )
                                    changes_applied += 1
                                    pattern_found = True
                                    break

                        # Try partial keyword matching
                        if not pattern_found:
                            # Extract key parts of the pattern for matching
                            key_parts = [
                                part.strip()
                                for part in old_pattern.split()
                                if len(part.strip()) > 3
                            ]
                            if key_parts:
                                lines = content.split("\n")
                                for i, line in enumerate(lines):
                                    # Check if line contains most key parts
                                    matching_parts = sum(
                                        1 for part in key_parts[:3] if part in line
                                    )
                                    if matching_parts >= min(len(key_parts), 2):
                                        # Replace the entire line
                                        indent = line[: len(line) - len(line.lstrip())]
                                        lines[i] = indent + new_pattern.strip()
                                        content = "\n".join(lines)
                                        print(
                                            f"🔧 Keyword-based replacement in {file_path}: {line.strip()[:50]}... → {new_pattern[:50]}..."
                                        )
                                        changes_applied += 1
                                        pattern_found = True
                                        break

                        # Report if pattern still not found
                        if not pattern_found:
                            print(
                                f"⚠️  Pattern not found in {file_path}: {old_pattern[:50]}..."
                            )
                            # Show some context of what's actually in the file
                            lines = content.split("\n")
                            print(f"   📄 File has {len(lines)} lines")
                            # Look for similar patterns
                            for i, line in enumerate(
                                lines[:100]
                            ):  # Check first 100 lines
                                if any(
                                    word in line.lower()
                                    for word in old_pattern.lower().split()[:2]
                                ):
                                    print(
                                        f"   📍 Similar content on line {i + 1}: {line.strip()[:60]}..."
                                    )
                                    break
                    pattern_found = False  # Reset for next pattern

                # Update virtual file content
                virtual_file.content = (
                    content.encode("utf-8")
                    if isinstance(virtual_file.content, bytes)
                    else content
                )

            if changes_applied > 0:
                print(f"🎯 Applied {changes_applied} changes to virtual files")
                return "✅ Patch applied successfully to virtual files"
            else:
                return "⚠️  No changes applied to virtual files"

        except Exception as e:
            return f"❌ Failed to apply patch to virtual files: {e}"

    def _extract_replacements_from_patch(self, patch_content):
        """Extract simple old->new replacements from patch content with enhanced flexibility"""
        replacements = []
        lines = patch_content.strip().split("\n")

        # Look for - and + line pairs
        i = 0
        while i < len(lines):
            line = lines[i]

            # Skip headers and context
            if (
                line.startswith("---")
                or line.startswith("+++")
                or line.startswith("@@")
            ):
                i += 1
                continue

            # Look for removal followed by addition
            if (
                line.startswith("-")
                and i + 1 < len(lines)
                and lines[i + 1].startswith("+")
            ):
                old_line = line[1:].strip()  # Remove '-' and whitespace
                new_line = lines[i + 1][1:].strip()  # Remove '+' and whitespace

                if old_line and new_line and old_line != new_line:
                    replacements.append((old_line, new_line))
                    print(f"📋 Found replacement: {old_line} → {new_line}")

                    # Also extract partial patterns for more flexible matching
                    if "=" in old_line and "=" in new_line:
                        # Extract variable assignment patterns
                        old_parts = old_line.split("=", 1)
                        new_parts = new_line.split("=", 1)
                        if len(old_parts) == 2 and len(new_parts) == 2:
                            old_var = old_parts[0].strip()
                            new_var = new_parts[0].strip()
                            old_value = old_parts[1].strip()
                            new_value = new_parts[1].strip()

                            if old_var == new_var and old_value != new_value:
                                # Add just the value part as an alternative replacement
                                replacements.append((old_value, new_value))
                                print(
                                    f"📋 Found value replacement: {old_value} → {new_value}"
                                )

                i += 2  # Skip both lines
            else:
                i += 1

        # If no direct replacements found, try to extract function call changes
        if not replacements:
            print("⚠️  No direct replacements found, trying function call extraction...")
            for i, line in enumerate(lines):
                if line.startswith("-") and "(" in line and ")" in line:
                    old_call = line[1:].strip()
                    # Look for corresponding + line
                    for j in range(i + 1, min(i + 5, len(lines))):
                        if (
                            lines[j].startswith("+")
                            and "(" in lines[j]
                            and ")" in lines[j]
                        ):
                            new_call = lines[j][1:].strip()
                            if old_call != new_call:
                                replacements.append((old_call, new_call))
                                print(
                                    f"📋 Found function call replacement: {old_call} → {new_call}"
                                )
                                break

        return replacements

    def _perform_memory_operations(
        self,
        files: List[str],
        branch_name: str,
        commit_message: str,
        auto_push: bool,
        analyzer,
        real_push: bool = False,
    ) -> str:
        """Perform memory repository operations for patch application"""

        try:
            operations_log = [f"📂 Memory Repository: {analyzer.repo_info.url}"]

            # Import dulwich components
            from dulwich.repo import MemoryRepo
            from dulwich.objects import Blob, Tree, Commit
            from datetime import datetime, timezone

            operations_log.append(f"📍 Base branch: {analyzer.repo_info.branch}")

            # Create memory repository
            memory_repo = MemoryRepo()

            # Create blobs for each file
            file_blobs = {}
            for file_path in files:
                if file_path in analyzer.virtual_files:
                    virtual_file = analyzer.virtual_files[file_path]
                    if hasattr(virtual_file, "content"):
                        # Handle bytes content
                        content = virtual_file.content
                        if isinstance(content, bytes):
                            file_content = content
                        else:
                            file_content = content.encode("utf-8")

                        # Create blob
                        blob = Blob.from_string(file_content)
                        memory_repo.object_store.add_object(blob)
                        file_blobs[file_path.encode("utf-8")] = blob.id
                        operations_log.append(f"📄 Added blob for: {file_path}")

            # Create tree
            tree_items = []
            for file_path, blob_id in file_blobs.items():
                tree_items.append((file_path, 0o100644, blob_id))

            tree = Tree()
            for name, mode, sha in tree_items:
                tree.add(name, mode, sha)
            memory_repo.object_store.add_object(tree)
            operations_log.append(f"🌳 Created tree with {len(file_blobs)} files")

            # Create commit
            import os

            author_name = os.getenv("GIT_AUTHOR_NAME", "Logan Assistant")
            author_email = os.getenv("GIT_AUTHOR_EMAIL", "logan@assistant.com")
            author = committer = f"{author_name} <{author_email}>".encode()
            commit_time = int(datetime.now(timezone.utc).timestamp())
            timezone_offset = 0

            commit = Commit()
            commit.tree = tree.id
            commit.author = author
            commit.committer = committer
            commit.commit_time = commit_time
            commit.author_time = commit_time
            commit.commit_timezone = timezone_offset
            commit.author_timezone = timezone_offset
            commit.encoding = b"UTF-8"
            commit.message = commit_message.encode("utf-8")

            memory_repo.object_store.add_object(commit)
            commit_hash = commit.id.decode("ascii")[:8]
            operations_log.append(f"💾 Created commit: {commit_hash}")

            # Update branch ref
            memory_repo.refs[f"refs/heads/{branch_name}".encode("utf-8")] = commit.id
            operations_log.append(f"🌿 Updated branch: {branch_name}")

            if auto_push:
                try:
                    repo_url = analyzer.repo_info.url
                    if repo_url and real_push:
                        # Perform REAL push directly from memory repository
                        operations_log.append("🚨 PERFORMING REAL GIT PUSH TO ORIGIN!")

                        try:
                            from dulwich.client import get_transport_and_path
                            from dulwich.repo import MemoryRepo
                            from dulwich.objects import Blob, Tree, Commit

                            # Get authentication if available
                            # Use porcelain for cleaner git operations
                            from dulwich import porcelain
                            import tempfile
                            import os

                            operations_log.append(
                                "🔄 Setting up temporary repository for patch..."
                            )

                            # Create temporary directory for porcelain operations
                            with tempfile.TemporaryDirectory() as temp_dir:
                                try:
                                    # Clone the original repository to temp directory
                                    operations_log.append(
                                        f"📥 Cloning original repository for patch..."
                                    )

                                    # Get authentication credentials
                                    auth_username = getattr(analyzer, "username", None)
                                    auth_password = getattr(analyzer, "password", None)

                                    # Setup auth URL for cloning
                                    clone_url = repo_url
                                    if auth_username and auth_password:
                                        clone_url = repo_url.replace(
                                            "https://",
                                            f"https://{auth_username}:{auth_password}@",
                                        )

                                    # Clone to temporary directory
                                    repo = porcelain.clone(
                                        clone_url,
                                        temp_dir,
                                        branch=analyzer.repo_info.branch.encode(
                                            "utf-8"
                                        ),
                                    )

                                    operations_log.append(
                                        f"✅ Cloned to temporary directory for patch"
                                    )

                                    # Apply patches to specific files
                                    patches_applied = 0
                                    for file_path in files:
                                        if file_path in analyzer.virtual_files:
                                            virtual_file = analyzer.virtual_files[
                                                file_path
                                            ]
                                            if hasattr(virtual_file, "content"):
                                                content = virtual_file.content
                                                if isinstance(content, bytes):
                                                    file_content = content.decode(
                                                        "utf-8"
                                                    )
                                                else:
                                                    file_content = content

                                                # Write file to temp repo
                                                full_path = os.path.join(
                                                    temp_dir, file_path
                                                )
                                                os.makedirs(
                                                    os.path.dirname(full_path),
                                                    exist_ok=True,
                                                )

                                                with open(
                                                    full_path, "w", encoding="utf-8"
                                                ) as f:
                                                    f.write(file_content)

                                                patches_applied += 1
                                                operations_log.append(
                                                    f"🔧 Applied patch to: {file_path}"
                                                )

                                    operations_log.append(
                                        f"📝 Applied {patches_applied} patches"
                                    )

                                    # Create new branch
                                    if branch_name != analyzer.repo_info.branch:
                                        porcelain.branch_create(repo, branch_name)
                                        operations_log.append(
                                            f"🌿 Created branch: {branch_name}"
                                        )

                                    # Stage changes
                                    porcelain.add(repo, files)
                                    operations_log.append(
                                        f"📋 Staged {len(files)} files"
                                    )

                                    # Commit changes
                                    author_name = os.getenv(
                                        "GIT_AUTHOR_NAME", "Logan Assistant"
                                    )
                                    author_email = os.getenv(
                                        "GIT_AUTHOR_EMAIL", "logan@assistant.com"
                                    )
                                    author_info = (
                                        f"{author_name} <{author_email}>".encode()
                                    )

                                    commit_sha = porcelain.commit(
                                        repo,
                                        message=commit_message,
                                        author=author_info,
                                        committer=author_info,
                                    )

                                    commit_hash = commit_sha.decode("ascii")[:8]
                                    operations_log.append(
                                        f"💾 Created patch commit: {commit_hash}"
                                    )

                                    # Push using porcelain
                                    push_url = clone_url  # Use same authenticated URL

                                    operations_log.append(
                                        f"🚀 Pushing patch to: {repo_url}"
                                    )
                                    operations_log.append(f"🌿 Branch: {branch_name}")

                                    # Push the branch
                                    porcelain.push(
                                        repo,
                                        push_url,
                                        refspecs=[
                                            f"refs/heads/{branch_name}:refs/heads/{branch_name}"
                                        ],
                                    )

                                    operations_log.append(
                                        f"✅ Successfully pushed patch to: {repo_url}"
                                    )
                                    operations_log.append(f"🌿 Branch: {branch_name}")
                                    operations_log.append(f"📝 Commit: {commit_hash}")
                                    operations_log.append(
                                        "🎉 Porcelain patch push completed!"
                                    )

                                except Exception as porcelain_patch_error:
                                    operations_log.append(
                                        f"❌ Porcelain patch operations failed: {porcelain_patch_error}"
                                    )
                                    return "\n".join(operations_log)

                        except Exception as real_push_error:
                            operations_log.append(
                                f"❌ Real patch push failed: {real_push_error}"
                            )
                            operations_log.append(
                                f"❌ Error type: {type(real_push_error).__name__}"
                            )
                            operations_log.append("💡 Falling back to simulation mode")
                            operations_log.append(f"🚀 Ready to push to: {repo_url}")
                            operations_log.append(
                                f"🚀 Branch {branch_name} prepared for push"
                            )
                            operations_log.append(
                                f"💡 Use: git push origin {branch_name} (in real repo)"
                            )
                        operations_log.append(
                            f"💡 Use: git push origin {branch_name} (in real repo)"
                        )
                        operations_log.append(
                            "💡 Or set real_push=True for actual push (dangerous!)"
                        )
                    else:
                        operations_log.append("⚠️  No repository URL available for push")

                except Exception as push_error:
                    operations_log.append(f"❌ Push operation failed: {push_error}")

            operations_log.extend(
                [
                    "",
                    f"🎉 Memory operations completed successfully!",
                    f"📝 Commit ID: {commit_hash}",
                    f"🌿 Branch: {branch_name}",
                    f"📊 Files committed: {len(file_blobs)}",
                ]
            )

            return "\n".join(operations_log)

        except ImportError as e:
            return f"❌ Dulwich import failed: {e}. Install with: pip install dulwich"
        except Exception as e:
            return f"❌ Memory operations failed: {str(e)}"


class DulwichGrepContentTool(BaseTool if AWS_AVAILABLE else object):
    """Tool for searching (grep) within file contents"""

    name: str = "grep_content"
    description: str = (
        "Search for text patterns within file contents using grep-like functionality"
    )
    args_schema: type = GrepContentInput if AWS_AVAILABLE else None
    analyzer_ref: object = None

    def __init__(self, analyzer_ref):
        super().__init__() if AWS_AVAILABLE else None
        object.__setattr__(self, "analyzer_ref", analyzer_ref)

    def _run(
        self,
        pattern: str,
        file_pattern: str = "*.py",
        case_sensitive: bool = False,
        line_limit: int = 50,
    ) -> str:
        analyzer = self.analyzer_ref.analyzer
        if not analyzer:
            return "❌ No repository loaded."

        try:
            if not hasattr(analyzer, "virtual_files") or not analyzer.virtual_files:
                return "❌ No files available in repository."

            import re
            import fnmatch

            # Compile regex pattern
            try:
                flags = 0 if case_sensitive else re.IGNORECASE
                regex = re.compile(pattern, flags)
            except re.error as e:
                return f"❌ Invalid regex pattern '{pattern}': {e}"

            matches = []

            # Search through files
            for file_path, virtual_file in analyzer.virtual_files.items():
                # Check if file matches the file pattern
                if not (
                    fnmatch.fnmatch(file_path, file_pattern)
                    or fnmatch.fnmatch(file_path.split("/")[-1], file_pattern)
                ):
                    continue

                if hasattr(virtual_file, "content") and virtual_file.content:
                    # Handle different content types (string, bytes, etc.)
                    content = virtual_file.content

                    # Convert to string if needed
                    if isinstance(content, bytes):
                        try:
                            content = content.decode("utf-8", errors="ignore")
                        except Exception:
                            # Skip files that can't be decoded
                            continue
                    elif not isinstance(content, str):
                        # Convert other types to string
                        try:
                            content = str(content)
                        except Exception:
                            continue

                    # Skip empty content
                    if not content.strip():
                        continue

                    lines = content.splitlines()
                    for line_num, line in enumerate(lines, 1):
                        try:
                            if regex.search(line):
                                matches.append(
                                    {
                                        "file": file_path,
                                        "line": line_num,
                                        "content": line.strip(),
                                        "highlighted": regex.sub(
                                            lambda m: f"[{m.group()}]", line.strip()
                                        ),
                                    }
                                )
                        except Exception:
                            # Skip lines that cause regex issues
                            continue

            if not matches:
                return f"❌ No matches found for pattern: '{pattern}'"

            output = [
                f"🔍 Grep results for '{pattern}' ({len(matches)} matches found):\n"
            ]

            # Group by file for better organization
            by_file = {}
            for match in matches:
                file_path = match["file"]
                if file_path not in by_file:
                    by_file[file_path] = []
                by_file[file_path].append(match)

            shown_count = 0
            for file_path in sorted(by_file.keys()):
                if shown_count >= line_limit:
                    break

                output.append(f"📄 {file_path}:")
                file_matches = by_file[file_path]

                for match in file_matches:
                    if shown_count >= line_limit:
                        break
                    output.append(f"   L{match['line']:4d}: {match['highlighted']}")
                    shown_count += 1

                output.append("")

            if len(matches) > line_limit:
                output.append(f"... and {len(matches) - line_limit} more matches")

            output.append(f"Total: {len(matches)} matches in {len(by_file)} files")

            return "\n".join(output)

        except Exception as e:
            return f"❌ Grep content failed: {str(e)}"


class LoganAssistant:
    """Streaming AI Assistant using AWS Bedrock with dulwich code analysis tools"""

    def _format_model_info(self) -> str:
        """Format model information for display"""
        # Extract readable model name from ID first
        model_name = self.model_id
        if "claude-3-haiku" in model_name:
            model_name = "Claude 3 Haiku"
        elif "claude-3-sonnet" in model_name:
            model_name = "Claude 3 Sonnet"
        elif "claude-3-opus" in model_name:
            model_name = "Claude 3 Opus"
        elif "claude-v2" in model_name:
            model_name = "Claude 2.1"
        elif "titan-text-express" in model_name:
            model_name = "Amazon Titan Text Express"
        elif "titan-text-lite" in model_name:
            model_name = "Amazon Titan Text Lite"
        elif "llama2" in model_name:
            model_name = "Meta Llama 2"

        if not AWS_AVAILABLE:
            return f"🤖 Model: {model_name} (AWS dependencies not available)"

        return f"🤖 Model: {model_name}"

    def __init__(
        self,
        model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0",
        max_iterations: int = 5,
        debug_mode: bool = False,
    ):
        self.model_id = model_id
        self.debug_mode = debug_mode or os.getenv("LOGAN_DEBUG", "").lower() in (
            "true",
            "1",
            "yes",
        )

        # Use exact iterations as specified by user
        self.max_iterations = max_iterations

        # Task tracking
        self.original_task = None
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.iteration_token_history = []

        self.llm = None
        self.analyzer = None

        # Initialize tools
        self._init_tools()

        # Show initialization info for debugging
        self.verbose = os.getenv("LOGAN_VERBOSE", "").lower() in ("true", "1", "yes")
        if self.verbose or self.debug_mode:
            print(f"🔧 Logan initialized with model: {self.model_id}")
            print(f"🔧 AWS available: {AWS_AVAILABLE}")
            print(f"🔧 Debug mode: {self.debug_mode}")
            print(
                f"🔧 Tools loaded: {len(self.tools) if hasattr(self, 'tools') else 0}"
            )

        self.system_prompt = """You are Logan, a powerful code analysis assistant with comprehensive access to explore and understand codebases.

The configured Git repository has been automatically loaded and analyzed for you. You have FULL PERMISSION to:

🔍 **EXPLORE THOROUGHLY**: Search through ALL files, functions, and classes to understand the complete codebase
🔎 **INVESTIGATE DEEPLY**: Follow code paths, trace dependencies, and examine related components
🛠️ **ANALYZE COMPREHENSIVELY**: Use all available tools extensively to provide complete analysis
📊 **UNDERSTAND ARCHITECTURE**: Map out how different parts of the code interact and work together
🐛 **FIND ALL ISSUES**: Search for bugs, vulnerabilities, code smells, and improvement opportunities
💡 **PROVIDE SOLUTIONS**: Suggest specific fixes, improvements, and best practices

You have access to these tools for analyzing the codebase:

🔍 **search_code**: Search for functions and classes by pattern
   - Parameters: pattern (required), search_type (optional: "both", "functions", "classes")
   - Supports regex patterns for flexible searching
   - Use extensively to explore related code

👀 **preview_code**: Show code content for functions or locations
   - Parameters: identifier (function name or file:line format)
   - Great for examining specific implementations
   - Don't hesitate to preview multiple functions

📋 **list_functions**: List all functions in the repository
   - Parameters: limit (optional, default: 20)
   - Shows organized view of all functions
   - Use to get overview of codebase structure

🏗️ **list_classes**: List all classes in the repository
   - Parameters: limit (optional, default: 20)
   - Shows class hierarchy and method counts
   - Essential for understanding object-oriented architecture

📁 **list_files**: List files in the repository
   - Parameters: pattern (optional, default: "*"), limit (optional, default: 50)
   - Use patterns like "*.py", "main*", "*config*" to find specific files
   - Great for understanding repository structure

📊 **get_repo_summary**: Get comprehensive repository overview
   - No parameters required
   - Shows file counts, statistics, and file type breakdown
   - Perfect for initial codebase assessment

📞 **find_function_calls**: Find function call relationships
   - Parameters: function_name (required), search_type (optional: "both", "calls_to", "calls_from")
   - Discovers what calls a function and what it calls
   - Critical for understanding code dependencies

🔄 **switch_commit**: Switch to a different commit for analysis
   - Parameters: commit_id (required), reload_analysis (optional: true)
   - Allows analyzing different versions of the code
   - Perfect for comparing changes or investigating history

📁 **list_all_files**: List all files in the repository
   - Parameters: pattern (optional: "*"), limit (optional: 100)
   - Shows complete file structure and organization
   - Use patterns to find specific file types

🔍 **grep_content**: Search within file contents
   - Parameters: pattern (required), file_pattern (optional: "*.py"), case_sensitive (optional: false), line_limit (optional: 50)
   - Powerful grep-like search through all file contents
   - Essential for finding specific code patterns or text

**ANALYSIS APPROACH:**
- Start broad with searches to understand the codebase structure
- Drill down into specific areas of interest
- Follow code relationships and dependencies
- Look for patterns, both good and problematic
- Examine error handling, security, and performance aspects
- Cross-reference similar functions to identify inconsistencies
- Use multiple tool calls to build complete understanding
- Map function call relationships and dependencies
- Analyze file organization and repository structure
- Use grep to find specific patterns across the entire codebase
- List all files to understand project organization

**YOU ARE ENCOURAGED TO:**
- Search extensively through the entire codebase
- Preview as many code sections as needed
- List functions and classes to understand architecture
- Follow every lead and investigate thoroughly
- Make multiple tool calls to answer questions completely
- Explore related code even if not directly requested

**BE PROACTIVE:**
- When asked about bugs, search for similar patterns across the entire codebase
- When analyzing a function, examine its callers and dependencies
- Look for configuration files, constants, and global variables
- Check for related utility functions and helper methods
- Investigate error handling patterns throughout the codebase
- Search for TODO comments, FIXME notes, and other developer annotations
- Examine test files to understand expected behavior
- Look for logging, debugging, and monitoring code
- Check for security-sensitive operations (authentication, authorization, data validation)
- Map function call chains to understand data flow
- Identify unused or orphaned functions
- Find circular dependencies or problematic call patterns
- Switch between commits to trace when issues were introduced
- Compare different versions of the same function
- Grep through all files to find patterns, TODOs, security issues
- Use file listings to understand project structure and organization

**COMPREHENSIVE ANALYSIS MEANS:**
- Don't just answer the immediate question - understand the broader context
- Use multiple search patterns to find all relevant code
- Preview related functions even if not explicitly asked
- Build a mental map of the codebase architecture using file listings and summaries
- Map function call relationships to understand code flow
- Identify patterns, both good and bad, across the entire project
- Analyze repository structure and organization
- Find function usage patterns and potential refactoring opportunities
- Suggest improvements beyond just fixing immediate issues

**PATCH CREATION WORKFLOW (MANDATORY):**
When creating patches, ALWAYS follow this workflow to avoid null patches:
1. **FIRST**: Preview target files using preview_code/grep_content/list_functions
2. **SECOND**: Note EXACT line content, indentation, and formatting
3. **THIRD**: Create unified diff patches based on ACTUAL observed content, never assumptions
- Use apply_patch tool with proper unified diff format
- Match context lines exactly to real file content
- Keep hunks small and focused
- Never create patches based on what you think the code looks like

Always use these tools extensively to provide accurate, detailed, and comprehensive analysis. Don't stop until you have a complete understanding of the relevant code areas and broader implications."""

    def _init_tools(self):
        """Initialize the dulwich analyzer and tools"""
        # Initialize the analyzer and auto-load repository
        self.analyzer = None
        if AWS_AVAILABLE:
            self.analyzer = self._create_and_load_analyzer()

            # Create tools that reference the shared analyzer
            self.search_tool = DulwichSearchTool(self)
            self.preview_tool = DulwichPreviewTool(self)
            self.list_functions_tool = DulwichListFunctionsTool(self)
            self.list_classes_tool = DulwichListClassesTool(self)
            self.list_files_tool = DulwichListFilesTool(self)
            self.repo_summary_tool = DulwichRepoSummaryTool(self)
            self.find_calls_tool = DulwichFindCallsTool(self)
            self.switch_commit_tool = DulwichSwitchCommitTool(self)
            self.list_all_files_tool = DulwichListAllFilesTool(self)
            self.grep_content_tool = DulwichGrepContentTool(self)
            self.apply_patch_tool = DulwichApplyPatchTool(self)

            self.tools = [
                self.search_tool,
                self.preview_tool,
                self.list_functions_tool,
                self.list_classes_tool,
                self.list_files_tool,
                self.repo_summary_tool,
                self.find_calls_tool,
                self.switch_commit_tool,
                self.list_all_files_tool,
                self.grep_content_tool,
                self.apply_patch_tool,
            ]
        else:
            self.tools = []

    def _create_and_load_analyzer(self):
        """Create analyzer and auto-load the configured repository"""
        try:
            # Create analyzer
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                from dulwich_memory_analyzer import InMemoryAnalyzer
            analyzer = InMemoryAnalyzer(verbose=False)

            # Auto-load repository if configured
            repo_url = os.getenv("REPOSITORY_URL", "")
            if repo_url:
                auth_token = os.getenv("REPOSITORY_AUTH", "")
                branch = os.getenv("REPOSITORY_BRANCH", "main")
                commit_id = os.getenv("COMMIT_ID", "")

                if commit_id:
                    print(
                        f"🔧 Auto-loading repository: {repo_url} at commit {commit_id[:8]}",
                        flush=True,
                    )
                else:
                    print(
                        f"🔧 Auto-loading repository: {repo_url} (branch: {branch})",
                        flush=True,
                    )

                # Set up authentication if provided
                if auth_token:
                    if ":" in auth_token:
                        username, password = auth_token.split(":", 1)
                        analyzer.username = username
                        analyzer.password = password
                    else:
                        analyzer.username = auth_token
                        analyzer.password = ""

                # Load repository with specific commit if provided
                if commit_id:
                    # For specific commit, we need to modify the analyzer to support it
                    success = self._fetch_specific_commit(analyzer, repo_url, commit_id)
                else:
                    success = analyzer.fetch_repository_tree(repo_url, branch)
                if success:
                    func_count = len(getattr(analyzer, "functions", {}))
                    class_count = len(getattr(analyzer, "classes", {}))
                    print(
                        f"✅ Repository loaded: {func_count} functions, {class_count} classes",
                        flush=True,
                    )
                else:
                    print(f"❌ Failed to load repository: {repo_url}", flush=True)

            return analyzer
        except Exception as e:
            print(f"❌ Failed to initialize analyzer: {e}", flush=True)
            return None

    def _fetch_specific_commit(self, analyzer, repo_url, commit_id):
        """Fetch repository at a specific commit ID"""
        try:
            print(f"🔧 Fetching specific commit: {commit_id[:8]}...", flush=True)

            # Create a temporary repo info with the commit
            from dulwich_memory_analyzer import RepoInfo

            analyzer.repo_info = RepoInfo(url=repo_url, branch="HEAD")

            # Import dulwich components
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                from dulwich.repo import MemoryRepo
                from dulwich.client import get_transport_and_path

            # Setup auth URL
            fetch_url = analyzer._setup_auth_url(repo_url)

            # Create memory repo and fetch
            memory_repo = MemoryRepo()
            client, path = get_transport_and_path(fetch_url)

            # Fetch all refs to get the commit
            remote_refs = client.fetch(path, memory_repo)

            # Try to find the commit in the repo
            commit_bytes = commit_id.encode("utf-8")

            # Check if the commit exists in memory_repo
            if commit_bytes in memory_repo:
                commit_obj = memory_repo[commit_bytes]
                analyzer.repo_info.commit_sha = commit_id

                # Get tree from commit
                tree_obj = memory_repo[commit_obj.tree]

                # Extract files from tree
                analyzer._extract_tree_to_memory(memory_repo, tree_obj, "")

                # Analyze Python files
                python_files = [
                    f for f in analyzer.virtual_files.keys() if f.endswith(".py")
                ]
                if analyzer.parser and python_files:
                    analyzer._analyze_python_files()

                print(
                    f"✅ Loaded commit {commit_id[:8]}: {len(python_files)} Python files",
                    flush=True,
                )
                return len(python_files) > 0
            else:
                print(f"❌ Commit {commit_id[:8]} not found in repository", flush=True)
                return False

        except Exception as e:
            print(f"❌ Failed to fetch commit {commit_id[:8]}: {e}", flush=True)
            return False

    def _initialize_bedrock(self) -> "ChatBedrock":
        """Initialize the Bedrock LLM client"""
        if not AWS_AVAILABLE:
            print(f"⚠️  AWS dependencies not available: {IMPORT_ERROR}", file=sys.stderr)
            raise RuntimeError(
                f"AWS dependencies required but not available: {IMPORT_ERROR}. Install required dependencies: pip install boto3 langchain langchain-aws"
            )

        try:
            bedrock_client = boto3.client(
                service_name="bedrock-runtime",
                region_name="us-east-1",
            )

            llm = ChatBedrock(
                client=bedrock_client,
                model_id=self.model_id,
                streaming=True,
                model_kwargs={
                    "max_tokens": 4096,
                    "temperature": 0.1,
                },
            )

            # Add debug callback if debug mode is enabled
            if self.debug_mode:
                from langchain_core.callbacks import BaseCallbackHandler

                class DebugCallbackHandler(BaseCallbackHandler):
                    def on_chat_model_start(self, serialized, messages, **kwargs):
                        print(f"🐛 [DEBUG] Chat model start: {len(messages)} messages")
                        for i, msg in enumerate(messages[-3:]):  # Show last 3 messages
                            msg_type = type(msg).__name__
                            content_preview = (
                                str(msg.content)[:100] + "..."
                                if len(str(msg.content)) > 100
                                else str(msg.content)
                            )
                            print(
                                f"🐛 [DEBUG]   Message {i}: {msg_type} - {content_preview}"
                            )

                    def on_llm_start(self, serialized, prompts, **kwargs):
                        print(
                            f"🐛 [DEBUG] LLM start: {serialized.get('name', 'unknown')} with {len(prompts)} prompts"
                        )

                    def on_llm_end(self, response, **kwargs):
                        print(f"🐛 [DEBUG] LLM end (chat_model_end)")
                        if hasattr(response, "generations"):
                            for i, gen in enumerate(response.generations):
                                for j, choice in enumerate(gen):
                                    print(
                                        f"🐛 [DEBUG]   Generation {i}.{j}: {choice.text[:200]}..."
                                    )
                                    if hasattr(choice, "message"):
                                        print(
                                            f"🐛 [DEBUG]   Message type: {type(choice.message)}"
                                        )
                                        if (
                                            hasattr(choice.message, "tool_calls")
                                            and choice.message.tool_calls
                                        ):
                                            print(
                                                f"🐛 [DEBUG]   Tool calls: {len(choice.message.tool_calls)}"
                                            )
                                            for k, tc in enumerate(
                                                choice.message.tool_calls
                                            ):
                                                print(
                                                    f"🐛 [DEBUG]     Tool {k}: {tc.name if hasattr(tc, 'name') else 'unknown'}"
                                                )

                    def on_llm_error(self, error, **kwargs):
                        print(f"🐛 [DEBUG] LLM error: {error}")

                    def on_tool_start(self, serialized, input_str, **kwargs):
                        print(
                            f"🐛 [DEBUG] Tool start: {serialized.get('name', 'unknown')}"
                        )

                    def on_tool_end(self, output, **kwargs):
                        output_preview = (
                            str(output)[:200] + "..."
                            if len(str(output)) > 200
                            else str(output)
                        )
                        print(f"🐛 [DEBUG] Tool end: {output_preview}")

                llm = llm.with_config(callbacks=[DebugCallbackHandler()])

            # Bind tools to the LLM
            if self.tools:
                llm = llm.bind_tools(self.tools)

            return llm

        except Exception as e:
            print(f"Error initializing Bedrock: {e}", file=sys.stderr)
            raise RuntimeError(
                f"Failed to initialize Bedrock: {e}. Install required dependencies: pip install boto3 langchain langchain-aws"
            )

    async def stream_response(self, user_input: str) -> None:
        """Stream a response with conversational loop until question is fully answered"""
        if not self.llm:
            self.llm = self._initialize_bedrock()

        # Track original task to prevent task drift
        self.original_task = user_input
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.iteration_token_history = []

        # Start conversation with initial messages
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=user_input),
        ]

        print("\n🤖 Logan: ", end="", flush=True)

        try:
            # Use robust streaming with safe chunk processing
            text_content = ""
            all_responses = []

            # Multi-iteration processing if enabled
            if self.max_iterations > 1:
                for iteration in range(self.max_iterations):
                    print(
                        f"\n🔄 Iteration {iteration + 1}/{self.max_iterations}:",
                        flush=True,
                    )

                    # Stream the response for real-time display
                    iteration_content = ""
                    async for chunk in self.llm.astream(messages):
                        chunk_text = self._extract_text_from_chunk(chunk)
                        if chunk_text:
                            print(chunk_text, end="", flush=True)
                            iteration_content += chunk_text

                    text_content += iteration_content

                    # Get complete response to check for tool calls
                    response = await self.llm.ainvoke(messages)

                    # Debug: Show raw response details
                    if self.debug_mode:
                        print(f"\n🐛 [DEBUG] Raw LLM Response:")
                        print(f"🐛 [DEBUG]   Type: {type(response)}")
                        print(f"🐛 [DEBUG]   Attributes: {dir(response)}")
                        if hasattr(response, "content"):
                            content_preview = (
                                str(response.content)[:300] + "..."
                                if len(str(response.content)) > 300
                                else str(response.content)
                            )
                            print(f"🐛 [DEBUG]   Content: {content_preview}")
                        if hasattr(response, "tool_calls"):
                            print(f"🐛 [DEBUG]   Tool calls: {response.tool_calls}")
                        if hasattr(response, "stop_reason"):
                            print(f"🐛 [DEBUG]   Stop reason: {response.stop_reason}")
                        if hasattr(response, "usage_metadata"):
                            print(f"🐛 [DEBUG]   Usage: {response.usage_metadata}")
                        if hasattr(response, "response_metadata"):
                            print(
                                f"🐛 [DEBUG]   Response metadata: {response.response_metadata}"
                            )
                        print(f"🐛 [DEBUG] End raw response\n")

                    # Handle tool calls immediately
                    tool_results = []
                    if hasattr(response, "tool_calls") and response.tool_calls:
                        print("\n\n🔧 Using tools...", flush=True)
                        for tool_call in response.tool_calls:
                            result = await self._execute_tool_call(tool_call)
                            print(f"\n{result}", flush=True)
                            tool_results.append(result)
                            text_content += f"\n{result}"

                    # Check LLM stop_reason for proper completion signal
                    llm_wants_to_stop = self._check_llm_stop_reason(response)

                    # Track token usage
                    token_info = self._get_token_usage(response)
                    if token_info.get("total_tokens", 0) > 0:
                        self.total_input_tokens += token_info.get("input_tokens", 0)
                        self.total_output_tokens += token_info.get("output_tokens", 0)
                        self.iteration_token_history.append(
                            {
                                "iteration": iteration + 1,
                                "input_tokens": token_info.get("input_tokens", 0),
                                "output_tokens": token_info.get("output_tokens", 0),
                                "tools_used": len(tool_results) if tool_results else 0,
                                "has_original_task_reference": self.original_task[
                                    :50
                                ].lower()
                                in iteration_content.lower()
                                if self.original_task and iteration_content
                                else False,
                            }
                        )

                    # Debug: Show response details (always show basic info, more details in debug mode)
                    debug_level = "full" if self.debug_mode else "basic"

                    if debug_level == "basic" or self.debug_mode:
                        print(f"\n🔍 Debug - Iteration {iteration + 1}:")
                        print(
                            f"   Tools called: {len(tool_results) if tool_results else 0}"
                        )
                        print(f"   LLM wants to stop: {llm_wants_to_stop}")
                        print(
                            f"   Content length: {len(iteration_content) if iteration_content else 0}"
                        )
                        print(f"   Message count: {len(messages)}")

                        # Show token information with cumulative totals
                        if token_info.get("total_tokens", 0) > 0:
                            print(
                                f"   Tokens: {token_info['input_tokens']} input + {token_info['output_tokens']} output = {token_info['total_tokens']} total"
                            )
                            print(
                                f"   Cumulative: {self.total_input_tokens} input + {self.total_output_tokens} output = {self.total_input_tokens + self.total_output_tokens} total"
                            )

                        # Check if losing track of original task
                        task_drift_check = self._check_task_drift(iteration_content)
                        if task_drift_check:
                            print(f"   ⚠️  {task_drift_check}")

                        if hasattr(response, "stop_reason"):
                            print(f"   Stop reason: {response.stop_reason}")

                        # Log tool call details
                        if hasattr(response, "tool_calls") and response.tool_calls:
                            print(f"   Tool calls found: {len(response.tool_calls)}")
                            for i, tc in enumerate(response.tool_calls):
                                tool_name = (
                                    tc.name if hasattr(tc, "name") else "unknown"
                                )
                                if self.debug_mode and hasattr(tc, "args"):
                                    print(
                                        f"     {i + 1}. {tool_name} - args: {tc.args}"
                                    )
                                else:
                                    print(f"     {i + 1}. {tool_name}")
                        else:
                            print(f"   Tool calls: None")

                    # Check if content suggests tool usage but no tools were called
                    content_suggests_tools = self._content_suggests_tool_usage(
                        iteration_content
                    )
                    if (
                        content_suggests_tools
                        and not tool_results
                        and llm_wants_to_stop
                    ):
                        print(
                            f"   ⚠️  LLM text suggests tool usage but signaled end_turn!"
                        )
                        print(f"   ⚠️  Possible tool binding issue or context overflow")

                    # Check if LLM wants to continue
                    should_continue = (
                        iteration < self.max_iterations - 1
                        and not llm_wants_to_stop  # Don't continue if LLM signaled end_turn
                        and (
                            tool_results or not llm_wants_to_stop
                        )  # Continue if tools used OR LLM hasn't ended turn
                    )

                    # Stop if LLM signaled end_turn and no tools were called
                    if llm_wants_to_stop and not tool_results:
                        if content_suggests_tools:
                            print(
                                f"\n⚠️  LLM signaled end_turn but content suggests it wanted to use tools"
                            )
                            print(
                                f"    Attempting to force tool suggestion in next iteration..."
                            )

                            # Force continue with tool suggestion instead of stopping
                            tool_suggestion = self._suggest_tool_from_content(
                                iteration_content
                            )
                            if tool_suggestion:
                                messages.append(AIMessage(content=iteration_content))
                                messages.append(
                                    HumanMessage(
                                        content=f"You mentioned wanting to examine or get information. Please use the {tool_suggestion} tool to proceed with your investigation."
                                    )
                                )
                                print(
                                    f"🔧 Forcing continuation with {tool_suggestion} tool suggestion"
                                )
                                continue

                        print(f"\n✅ LLM signaled completion (stop_reason: end_turn)")
                        break

                    if should_continue:
                        # Token-based context management using LLM response data
                        token_info = self._get_token_usage(response)
                        current_tokens = token_info.get("total_tokens", 0)

                        if current_tokens > 0:
                            print(f"🪙 Token usage: {current_tokens} tokens")

                        # Manage context based on Claude's 200k token limit
                        should_trim = (current_tokens > 150000) or (len(messages) > 30)

                        if should_trim:
                            print(
                                f"🗂️  Context management: {len(messages)} messages, {current_tokens} tokens, trimming to fit Claude's 200k limit..."
                            )
                            # Keep system message, last few exchanges, and current iteration
                            system_msg = messages[0]
                            recent_messages = messages[-12:]  # Last 6 pairs of messages
                            messages = [system_msg] + recent_messages
                            print(f"🗂️  Context trimmed to {len(messages)} messages")

                        # Build context for next iteration based on tool results
                        context_parts = []
                        if iteration_content.strip():
                            context_parts.append(iteration_content)

                        # Add tool results to context
                        if tool_results:
                            tool_summary = " | ".join(
                                [
                                    r[:100] + "..." if len(r) > 100 else r
                                    for r in tool_results[:3]
                                ]
                            )
                            context_parts.append(f"Tool results: {tool_summary}")

                        full_context = " ".join(context_parts)
                        messages.append(AIMessage(content=full_context))

                        # Create more specific follow-up based on content and tools used
                        # Include original task reminder if drifting
                        task_reminder = ""
                        if iteration > 10 and self.original_task:
                            recent_mentions = sum(
                                1
                                for h in self.iteration_token_history[-5:]
                                if h.get("has_original_task_reference", False)
                            )
                            if recent_mentions < 2:
                                task_reminder = f" Remember: your original task was '{self.original_task[:100]}...'"

                        if content_suggests_tools and not tool_results:
                            follow_up = f"You mentioned wanting to examine or get more information. Please use the appropriate tools to gather the data you need.{task_reminder}"
                        elif tool_results:
                            follow_up = f"Based on the tool results above, continue your analysis. Use additional tools if needed, or provide your conclusions if you have sufficient information.{task_reminder}"
                        else:
                            follow_up = f"Continue your analysis. Use available tools to gather any additional information you need.{task_reminder}"
                        messages.append(HumanMessage(content=follow_up))

                        # Show context status with token information
                        total_chars = sum(
                            len(str(msg.content))
                            for msg in messages
                            if hasattr(msg, "content")
                        )
                        token_display = (
                            f", {current_tokens} tokens" if current_tokens > 0 else ""
                        )

                        # Add token usage warnings
                        if current_tokens > 100000:
                            print(
                                f"⚠️  High token usage: {current_tokens}/200k tokens ({current_tokens / 2000:.1f}%)"
                            )
                        elif current_tokens > 80000:
                            print(
                                f"📊 Token usage: {current_tokens}/200k tokens ({current_tokens / 2000:.1f}%)"
                            )

                        # Show task drift warning if needed
                        total_tokens_used = (
                            self.total_input_tokens + self.total_output_tokens
                        )
                        task_status = ""
                        if iteration > 5 and self.original_task:
                            recent_task_refs = sum(
                                1
                                for h in self.iteration_token_history[-3:]
                                if h.get("has_original_task_reference", False)
                            )
                            if recent_task_refs == 0:
                                task_status = " ⚠️ TASK DRIFT DETECTED"

                        print(
                            f"\n🔄 Continuing to next iteration (tools used: {len(tool_results)}, context: {len(messages)} msgs, {total_chars // 1000}k chars{token_display}, total: {total_tokens_used} tokens){task_status}",
                            flush=True,
                        )
                    else:
                        # Stop iteration - either max reached or no tools used (LLM finished)
                        if not tool_results:
                            print(
                                f"\n🏁 Stopping iterations - LLM signaled completion (no tools requested)"
                            )
                        else:
                            print(
                                f"\n🏁 Max iterations reached ({self.max_iterations})"
                            )
                        break

                # All iterations complete, no additional tool processing needed
                return
            else:
                # Single iteration (default behavior)
                async for chunk in self.llm.astream(messages):
                    chunk_text = self._extract_text_from_chunk(chunk)
                    if chunk_text:
                        print(chunk_text, end="", flush=True)
                        text_content += chunk_text

                # Get complete response for tool calls
                response = await self.llm.ainvoke(messages)

            # Handle tool calls from the complete response
            if hasattr(response, "tool_calls") and response.tool_calls:
                print("\n\n🔧 Using tools...", flush=True)

                tool_results = []
                for tool_call in response.tool_calls:
                    result = await self._execute_tool_call(tool_call)
                    tool_results.append(result)
                    print(f"\n{result}\n", flush=True)

        except KeyboardInterrupt:
            print("\n\n⚠️  Response interrupted by user.", file=sys.stderr)
        except Exception as e:
            print(f"\n❌ Error generating response: {e}", file=sys.stderr)

        print("\n")

    def _check_llm_stop_reason(self, response) -> bool:
        """Check if LLM has signaled completion via stop_reason"""
        try:
            # Check for stop_reason attribute
            if hasattr(response, "stop_reason"):
                stop_reason = response.stop_reason
                if stop_reason == "end_turn":
                    return True
                elif stop_reason == "stop_sequence":
                    return True
                elif stop_reason == "tool_use":
                    return False  # LLM wants to use tools, don't stop

            # Check for response_metadata with stop_reason
            if hasattr(response, "response_metadata"):
                metadata = response.response_metadata
                if isinstance(metadata, dict) and "stop_reason" in metadata:
                    stop_reason = metadata["stop_reason"]
                    if stop_reason == "end_turn":
                        return True
                    elif stop_reason == "tool_use":
                        return False

            # Fallback: if no stop_reason found, check for tool_calls
            if hasattr(response, "tool_calls") and response.tool_calls:
                return False  # Has tool calls, don't stop

            # Default: assume LLM wants to continue if unclear
            return False

        except Exception:
            # If we can't determine stop reason, be conservative and continue
            return False

    def _check_task_drift(self, current_content: str) -> str:
        """Check if the conversation is drifting from the original task"""
        if not self.original_task or not current_content:
            return ""

        # Check if recent iterations mention the original task
        if len(self.iteration_token_history) > 5:
            recent_task_mentions = sum(
                1
                for h in self.iteration_token_history[-5:]
                if h.get("has_original_task_reference", False)
            )
            if recent_task_mentions == 0:
                return "Task drift detected - not referencing original goal"

        # Check token usage efficiency
        if len(self.iteration_token_history) > 3:
            recent_tool_usage = sum(
                h.get("tools_used", 0) for h in self.iteration_token_history[-3:]
            )
            if recent_tool_usage == 0:
                return "Low tool usage - may be losing focus"

        return ""

    def _get_token_usage(self, response) -> dict:
        """Extract token usage information from LLM response"""
        try:
            # Check for usage_metadata in response
            if hasattr(response, "usage_metadata"):
                usage = response.usage_metadata
                return {
                    "input_tokens": getattr(usage, "input_tokens", 0),
                    "output_tokens": getattr(usage, "output_tokens", 0),
                    "total_tokens": getattr(usage, "input_tokens", 0)
                    + getattr(usage, "output_tokens", 0),
                }

            # Check for response_metadata with token info
            if hasattr(response, "response_metadata"):
                metadata = response.response_metadata
                if isinstance(metadata, dict):
                    usage = metadata.get("usage", {})
                    if usage:
                        return {
                            "input_tokens": usage.get("input_tokens", 0),
                            "output_tokens": usage.get("output_tokens", 0),
                            "total_tokens": usage.get("total_tokens", 0),
                        }

            # Check direct attributes
            if hasattr(response, "token_usage"):
                usage = response.token_usage
                return {
                    "input_tokens": getattr(usage, "prompt_tokens", 0),
                    "output_tokens": getattr(usage, "completion_tokens", 0),
                    "total_tokens": getattr(usage, "total_tokens", 0),
                }

            return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        except Exception:
            return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    def _suggest_tool_from_content(self, content: str) -> str:
        """Suggest appropriate tool based on LLM content"""
        if not content:
            return ""

        content_lower = content.lower()

        # Map content patterns to tools
        tool_suggestions = [
            (["preview", "look at", "examine", "see", "show"], "preview_code"),
            (["search", "find", "grep", "pattern"], "grep_content"),
            (["list", "files", "directory"], "list_files"),
            (["function", "calls", "usage"], "find_calls"),
            (["summary", "overview"], "get_repo_summary"),
        ]

        for patterns, tool_name in tool_suggestions:
            for pattern in patterns:
                if pattern in content_lower:
                    return tool_name

        return "preview_code"  # Default fallback

    def _content_suggests_tool_usage(self, content: str) -> bool:
        """Check if content suggests the LLM wants to use tools"""
        if not content:
            return False

        content_lower = content.lower()

        # Phrases that suggest tool usage intent
        tool_intent_phrases = [
            "let me get",
            "let me check",
            "let me examine",
            "let me look at",
            "let me see",
            "let me find",
            "let me search",
            "let me preview",
            "i need to get",
            "i need to check",
            "i need to examine",
            "i need to look at",
            "i need to see",
            "i want to get",
            "i want to check",
            "i want to examine",
            "i want to look at",
            "i want to see",
            "i should get",
            "i should check",
            "i should examine",
            "i should look at",
            "by previewing",
            "by examining",
            "by checking",
            "by getting",
        ]

        for phrase in tool_intent_phrases:
            if phrase in content_lower:
                return True

        return False

    def _extract_text_from_chunk(self, chunk):
        """Extract only text content from chunks, skipping all tool-related content"""
        try:
            # Handle LangChain chunk objects with content attribute
            if hasattr(chunk, "content"):
                content = chunk.content

                # Handle list format in content (Claude's format)
                if isinstance(content, list):
                    text_parts = []
                    for item in content:
                        try:
                            # Only process text type items
                            if isinstance(item, dict) and item.get("type") == "text":
                                if "text" in item:
                                    text_parts.append(str(item["text"]))
                            # Skip everything else (tool_use, partial_json, etc.)
                        except (KeyError, TypeError):
                            continue
                    return "".join(text_parts) if text_parts else None

                # Handle direct string content
                elif isinstance(content, str) and content.strip():
                    return content

                # Handle empty content
                elif not content:
                    return None

            # Handle list format directly (fallback)
            elif isinstance(chunk, list):
                text_parts = []
                for item in chunk:
                    try:
                        if isinstance(item, dict) and item.get("type") == "text":
                            if "text" in item:
                                text_parts.append(str(item["text"]))
                    except (KeyError, TypeError):
                        continue
                return "".join(text_parts) if text_parts else None

            # Handle single dict
            elif isinstance(chunk, dict):
                if chunk.get("type") == "text" and "text" in chunk:
                    return str(chunk["text"])
                return None

            # Handle plain strings
            elif isinstance(chunk, str) and chunk.strip():
                return chunk

        except Exception:
            pass

        return None

    def _get_tool_call_id(self, tool_call):
        """Extract tool call ID from different tool call formats"""
        if hasattr(tool_call, "id"):
            return tool_call.id
        elif isinstance(tool_call, dict) and "id" in tool_call:
            return tool_call["id"]
        else:
            # No valid tool call ID found
            raise ValueError("Tool call missing required ID field")

    async def _execute_tool_call(self, tool_call):
        """Execute a tool call and return result (including errors)"""
        if self.debug_mode:
            print(f"🐛 [DEBUG] Executing tool call: {tool_call}")
        try:
            # Handle different tool_call formats
            tool_name = ""
            tool_args = {}

            if isinstance(tool_call, dict):
                # Dictionary format (most common from streaming)
                tool_name = str(tool_call.get("name", ""))
                tool_args = tool_call.get("args", {}) or tool_call.get("input", {})
                if not isinstance(tool_args, dict):
                    tool_args = {}
            elif hasattr(tool_call, "name") and hasattr(tool_call, "args"):
                # LangChain ToolCall object
                tool_name = str(tool_call.name)
                tool_args = tool_call.args if isinstance(tool_call.args, dict) else {}
            else:
                return f"❌ Invalid tool call format: {type(tool_call)}"

            if not tool_name:
                if self.debug_mode:
                    print(f"🐛 [DEBUG] No tool name in tool_call: {tool_call}")
                return f"❌ No tool name provided in tool call"

            # Find and execute the appropriate tool
            for tool in self.tools:
                if tool.name == tool_name:
                    try:
                        # Filter tool_args to only include parameters that the tool accepts
                        if hasattr(tool, "_run"):
                            import inspect

                            sig = inspect.signature(tool._run)
                            valid_params = set(sig.parameters.keys()) - {"self"}

                            # Debug logging
                            if self.verbose or self.debug_mode:
                                print(f"🔧 Tool: {tool_name}")
                                print(f"   Valid params: {sorted(valid_params)}")
                                print(f"   Provided params: {sorted(tool_args.keys())}")
                                if self.debug_mode:
                                    print(f"🐛 [DEBUG] Tool args: {tool_args}")

                            filtered_args = {
                                k: v for k, v in tool_args.items() if k in valid_params
                            }

                            # Log filtered parameters if any were removed
                            removed_params = set(tool_args.keys()) - valid_params
                            if removed_params and self.verbose:
                                print(f"   Filtered out: {sorted(removed_params)}")

                            result = tool._run(**filtered_args)
                        else:
                            result = tool._run(**tool_args)
                        # Always return the result, whether success or error
                        return result
                    except Exception as tool_error:
                        # Return tool execution errors as results, not exceptions
                        return (
                            f"❌ Tool '{tool_name}' execution error: {str(tool_error)}"
                        )

            return f"❌ Unknown tool: {tool_name}"
        except Exception as e:
            # Return any other errors as results
            return f"❌ Tool call processing error: {str(e)}"

    def get_user_input(self) -> Optional[str]:
        """Get user input from stdin"""
        try:
            print("👤 You: ", end="", flush=True)
            user_input = input().strip()

            if user_input.lower() in ["quit", "exit", "bye"]:
                return None

            return user_input
        except (EOFError, KeyboardInterrupt):
            return None

    async def run_interactive(self) -> None:
        """Run the assistant in interactive mode"""
        print("🚀 Logan Assistant with Code Analysis Tools!")
        print()

        # Show model information
        print(self._format_model_info())

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

                # Show commit info if available
                if hasattr(self.analyzer, "repo_info") and self.analyzer.repo_info:
                    repo_info = self.analyzer.repo_info
                    if hasattr(repo_info, "commit_sha") and repo_info.commit_sha:
                        print(f"📝 At commit: {repo_info.commit_sha[:8]}")
        else:
            print("⚠️  No repository configured (set REPOSITORY_URL)")

        print()
        print("💡 Example commands:")
        print("  • Search for code: 'Find all async functions'")
        print("  • Preview code: 'Show me the main function'")
        print("  • List code: 'List all classes' or 'Show me all functions'")
        print("  • Explore files: 'List all Python files' or 'Show me config files'")
        print("  • Get overview: 'Give me a repository summary'")
        print("  • Find relationships: 'Show me what calls the login function'")
        print("  • Switch commits: 'Switch to commit abc123 to analyze the bug'")
        print("  • List all files: 'Show me all Python files' or 'List config files'")
        print(
            "  • Search content: 'Grep for TODO comments' or 'Find password patterns'"
        )
        print("  • Ask questions: 'What does this codebase do?'")
        print("  • Explore: 'Find authentication related code'")
        print("")
        if self.max_iterations > 1:
            print(f"🔄 Max iterations: {self.max_iterations}")
            print("   Multiple iterations enabled for complex reasoning")
            print("")
        print("🔧 Environment variables:")
        print("  • REPOSITORY_URL: Git repository to analyze")
        print("  • REPOSITORY_AUTH: Authentication credentials")
        print("  • REPOSITORY_BRANCH: Branch to analyze (default: main)")
        print("  • COMMIT_ID: Specific commit SHA to analyze")
        if self.max_iterations > 1:
            print(f"🔄 Multi-iteration mode: {self.max_iterations} iterations")
            print("   (Use 'iterations X' to change)")
        print()
        print("Type 'quit', 'exit', or 'bye' to stop.")
        print("=" * 60)

        while True:
            user_input = self.get_user_input()

            if user_input is None:
                print("\n👋 Goodbye!")
                break

            if not user_input:
                continue

            # Handle special commands
            elif user_input.lower() in ["version", "ver", "v"]:
                print("\n🚀 Logan Assistant v1.0.0")
                print(f"🤖 {self._format_model_info()}")
                print(
                    f"🛠️  {len(self.tools) if hasattr(self, 'tools') else 0} tools available"
                )
                print(
                    f"🌐 AWS Bedrock: {'✅ Available' if AWS_AVAILABLE else '❌ Not available'}"
                )
                if self.max_iterations > 1:
                    print(f"🔄 Max iterations: {self.max_iterations}")
                continue
            elif user_input.lower().startswith("iterations "):
                try:
                    new_iterations = int(user_input.split()[1])
                    self.max_iterations = new_iterations
                    print(f"🔄 Iterations set to: {self.max_iterations}")
                except (ValueError, IndexError):
                    print("❌ Invalid format. Use: iterations <number>")
                continue
            elif user_input.lower() in ["model", "mod", "m"]:
                print(f"\n{self._format_model_info()}")
                print(f"🆔 Full model ID: {self.model_id}")
                continue
            elif user_input.lower() in ["help", "h", "?"]:
                print("\n🔧 Logan Assistant Commands:")
                print("=" * 30)
                print("• version/ver/v - Show version and system info")
                print("• model/mod/m - Show current model information")
                print("• help/h/? - Show this help message")
                print("• quit/exit/bye - Exit Logan")
                print("• iterations <number> - Set iteration count")
                if self.max_iterations > 1:
                    print(f"• Current iterations: {self.max_iterations}")
                print("\n💡 For code analysis, just ask naturally:")
                print("  'Find all functions that use async'")
                print("  'Show me the main.py file'")
                print("  'List all classes in the project'")
                print("\n💡 Iteration Guide:")
                print("  • 1 iteration: Fast, single response")
                print("  • 2-5 iterations: Deeper analysis")
                print("  • 6+ iterations: Very thorough investigation")
                continue

            await self.stream_response(user_input)

    async def run_single_prompt(self) -> None:
        """Run with a single prompt from stdin"""
        # Show model information for single prompt mode
        print(f"🤖 Logan: {self._format_model_info()}", file=sys.stderr)

        try:
            user_input = sys.stdin.read().strip()

            if not user_input:
                print("❌ No input provided.", file=sys.stderr)
                sys.exit(1)

            await self.stream_response(user_input)

        except KeyboardInterrupt:
            print("\n⚠️  Interrupted by user.", file=sys.stderr)
            sys.exit(1)


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Logan - Streaming AI Assistant with Code Analysis Tools"
    )
    parser.add_argument(
        "--model",
        default=os.getenv("LOGAN_MODEL", "anthropic.claude-3-haiku-20240307-v1:0"),
        help="AWS Bedrock model ID to use (can also set LOGAN_MODEL env var)",
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Run in interactive mode",
    )
    parser.add_argument("--system-prompt", "-s", help="Custom system prompt to use")
    parser.add_argument(
        "--iterations",
        type=int,
        default=int(os.getenv("LOGAN_ITERATIONS", "5")),
        help="Number of iterations for multi-step reasoning (default: 5, can also set LOGAN_ITERATIONS env var)",
    )
    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Enable debug mode with detailed LLM output and event tracking (can also set LOGAN_DEBUG=true)",
    )

    args = parser.parse_args()

    # Create assistant instance
    assistant = LoganAssistant(
        model_id=args.model, max_iterations=args.iterations, debug_mode=args.debug
    )

    # Set custom system prompt if provided
    if args.system_prompt:
        assistant.system_prompt = args.system_prompt

    try:
        if args.interactive or sys.stdin.isatty():
            await assistant.run_interactive()
        else:
            await assistant.run_single_prompt()

    except Exception as e:
        print(f"❌ Fatal error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
