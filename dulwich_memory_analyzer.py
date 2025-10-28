#!/usr/bin/env python3
"""
In-Memory Dulwich Repository Analyzer

Analyzes remote Git repositories entirely in memory using dulwich.
No local files are created - everything is kept in memory.

Dependencies:
    pip install dulwich

Usage:
    python dulwich_memory_analyzer.py --repo https://github.com/user/repo
    python dulwich_memory_analyzer.py --repo https://git.example.com/project.git --username user --password pass
    python dulwich_memory_analyzer.py --repo user/repo --search "async.*"
"""

# Debug imports will be conditional on debug mode
import os
import sys
import json
import argparse
import io
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, asdict
import time
import re
import fnmatch
from urllib.parse import urlparse, urlunparse

# Dulwich imports
try:
    from dulwich import porcelain
    from dulwich.repo import MemoryRepo
    from dulwich.client import get_transport_and_path, HTTPUnauthorized
    from dulwich.errors import NotGitRepository, GitProtocolError
    from dulwich.objects import Tree, Blob
    import dulwich.client

    DULWICH_AVAILABLE = True
    pass  # Dulwich imports successful
except ImportError:
    print("❌ dulwich not available. Install with: pip install dulwich")
    DULWICH_AVAILABLE = False
    sys.exit(1)

# Tree-sitter for in-memory analysis
# Tree-sitter imports
try:
    import tree_sitter_python as tspython
    from tree_sitter import Language, Parser, Query

    TREE_SITTER_AVAILABLE = True
    pass  # Tree-sitter imports successful
except ImportError:
    print("⚠️  Tree-sitter not available - limited analysis capabilities")
    TREE_SITTER_AVAILABLE = False


@dataclass
class VirtualFile:
    """Represents a file in memory"""

    path: str
    content: bytes

    @property
    def text_content(self) -> str:
        """Get text content with proper encoding"""
        try:
            return self.content.decode("utf-8")
        except UnicodeDecodeError:
            for enc in ["utf-8", "latin-1", "cp1252"]:
                try:
                    return self.content.decode(enc)
                except UnicodeDecodeError:
                    continue
            return self.content.decode("utf-8", errors="replace")


@dataclass
class FunctionInfo:
    """Information about a function found in code"""

    name: str
    file_path: str
    line_start: int
    line_end: int
    is_method: bool = False
    class_name: Optional[str] = None
    is_async: bool = False
    signature: Optional[str] = None


@dataclass
class ClassInfo:
    """Information about a class found in code"""

    name: str
    file_path: str
    line_start: int
    line_end: int
    methods: List[str] = None
    base_classes: List[str] = None

    def __post_init__(self):
        if self.methods is None:
            self.methods = []
        if self.base_classes is None:
            self.base_classes = []


@dataclass
class RepoInfo:
    """Information about the repository"""

    url: str
    branch: str = "main"
    commit_sha: Optional[str] = None


class InMemoryAnalyzer:
    """In-memory Git repository analyzer using dulwich"""

    def __init__(
        self,
        verbose: bool = False,
        exclude_patterns: List[str] = None,
        username: str = None,
        password: str = None,
        show_all: bool = True,
    ):
        self.verbose = verbose
        self.exclude_patterns = exclude_patterns or []
        self.username = username
        self.password = password
        self.show_all = show_all

        self.repo_info: Optional[RepoInfo] = None
        self.virtual_files: Dict[str, VirtualFile] = {}
        self.functions: Dict[str, FunctionInfo] = {}
        self.classes: Dict[str, ClassInfo] = {}

        # Initialize tree-sitter if available
        if TREE_SITTER_AVAILABLE:
            try:
                self.language = Language(tspython.language())
                self.parser = Parser()
                self.parser.language = self.language
                self._init_queries()
            except Exception as e:
                self._log(f"⚠️  Tree-sitter initialization failed: {e}")
                self.language = None
                self.parser = None
        else:
            self.language = None
            self.parser = None

    def _log(self, message: str, force: bool = False):
        """Log message if verbose mode is enabled"""
        if self.verbose or force:
            print(message)

    def _init_queries(self):
        """Initialize tree-sitter queries"""
        if not self.language:
            return

        self.queries = {
            "functions": Query(self.language, "(function_definition) @func_def"),
            "classes": Query(self.language, "(class_definition) @class_def"),
        }

    def _progress_update(self, message: str):
        """Update progress if callback is available"""
        if hasattr(self, "_progress_callback") and self._progress_callback:
            self._progress_callback(message)

    def fetch_repository_tree(self, repo_url: str, branch: str = None) -> bool:
        """Fetch repository tree into memory without creating local files"""
        try:
            if self.verbose:
                print("🔧 Debug: Starting fetch_repository_tree method")
            self.repo_info = RepoInfo(url=repo_url, branch=branch or "main")
            if self.verbose:
                print("🔧 Debug: Created RepoInfo")

            self._progress_update("Connecting to repository...")
            self._log(f"📥 Fetching repository: {repo_url}")
            self._log(f"🌿 Branch: {self.repo_info.branch}")

            # Setup authentication URL if provided
            if self.verbose:
                print("🔧 Debug: Setting up auth URL...")
            fetch_url = self._setup_auth_url(repo_url)
            if self.verbose:
                print(f"🔧 Debug: Auth URL configured")

            # Create in-memory repository
            if self.verbose:
                print("🔧 Debug: Creating MemoryRepo...")
            memory_repo = MemoryRepo()
            if self.verbose:
                print("🔧 Debug: MemoryRepo created")

            # Get transport and path
            if self.verbose:
                print("🔧 Debug: Getting transport and path...")
            client, path = get_transport_and_path(fetch_url)
            if self.verbose:
                print(f"🔧 Debug: Transport created, path: {path}")

            # Fetch remote refs
            self._progress_update("Fetching remote references...")
            self._log("🔍 Fetching remote references...")
            try:
                remote_refs = client.fetch(path, memory_repo)
            except Exception as fetch_error:
                if "NAK" in str(fetch_error):
                    # Try alternative fetch method for servers that don't support fetch
                    self._log("🔄 Trying alternative method (ls-remote)...")
                    remote_refs = client.get_refs(path)
                else:
                    raise

            # Find the target branch
            branch_ref = None
            target_branch = self.repo_info.branch

            # Try to find the branch in remote refs
            possible_refs = [
                f"refs/heads/{target_branch}",
                f"refs/remotes/origin/{target_branch}",
                target_branch,
            ]

            for ref_name in possible_refs:
                if ref_name.encode() in remote_refs:
                    branch_ref = remote_refs[ref_name.encode()]
                    break

            # If target branch not found, try common defaults
            if not branch_ref:
                for default_branch in ["main", "master", "develop"]:
                    for ref_pattern in [f"refs/heads/{default_branch}", default_branch]:
                        if ref_pattern.encode() in remote_refs:
                            branch_ref = remote_refs[ref_pattern.encode()]
                            self.repo_info.branch = default_branch
                            self._log(f"🔄 Using branch: {default_branch}")
                            break
                    if branch_ref:
                        break

            if not branch_ref:
                # Try to get HEAD or any available ref
                if b"HEAD" in remote_refs:
                    branch_ref = remote_refs[b"HEAD"]
                    self._log("🔄 Using HEAD reference")
                else:
                    # Just take the first available ref
                    branch_ref = list(remote_refs.values())[0]
                    self._log("🔄 Using first available reference")

            self.repo_info.commit_sha = branch_ref.decode("utf-8")
            self._log(f"📝 Target commit: {self.repo_info.commit_sha[:8]}")

            # Get commit object
            self._progress_update("Loading commit information...")
            commit_obj = memory_repo[branch_ref]
            self._log(
                f"👤 Author: {commit_obj.author.decode('utf-8', errors='replace')}"
            )
            message = commit_obj.message.decode("utf-8", errors="replace").strip()
            self._log(f"💬 Message: {message[:60]}...")

            # Get tree from commit
            tree_obj = memory_repo[commit_obj.tree]

            # Extract files from tree
            self._progress_update("Extracting files from repository...")
            self._log("📂 Extracting files from repository tree...")
            self._extract_tree_to_memory(memory_repo, tree_obj, "")

            self._progress_update("Analyzing Python files...")

            python_files = [f for f in self.virtual_files.keys() if f.endswith(".py")]
            self._log(f"🐍 Found {len(python_files)} Python files")

            if python_files:
                self._progress_update(f"Processing {len(python_files)} Python files...")

            if self.verbose and python_files:
                self._log("📋 Python files:")
                if hasattr(self, "show_all") and not self.show_all:
                    for py_file in sorted(python_files)[:10]:
                        self._log(f"   - {py_file}")
                    if len(python_files) > 10:
                        self._log(f"   ... and {len(python_files) - 10} more")
                else:
                    for py_file in sorted(python_files):
                        self._log(f"   - {py_file}")

            # Analyze files if tree-sitter is available
            if self.parser and python_files:
                self._progress_update("Analyzing code structure...")
                self._log("🔍 Analyzing Python files...")
                self._analyze_python_files()
                self._progress_update("Code analysis complete")

            self._progress_update("Repository loading complete")
            return len(python_files) > 0

        except Exception as e:
            self._log(f"❌ Failed to fetch repository: {e}", force=True)

            error_str = str(e).lower()
            if "nak" in error_str:
                self._log(
                    "💡 Git protocol issue - server may not support this operation"
                )
                self._log("   Try using the regular dulwich_analyzer.py instead")
            elif "auth" in error_str or "unauthorized" in error_str:
                self._log("💡 Authentication required. Use --username/--password")
            elif "not found" in error_str or "404" in error_str:
                self._log("💡 Repository not found or not accessible")
            elif "ssl" in error_str:
                self._log("💡 SSL certificate issue")

            return False

    def _setup_auth_url(self, repo_url: str) -> str:
        """Setup authentication in URL if credentials provided"""
        if self.username and self.password:
            self._log("🔐 Setting up basic authentication")
            parsed = urlparse(repo_url)
            if parsed.scheme in ("http", "https"):
                netloc = f"{self.username}:{self.password}@{parsed.hostname}"
                if parsed.port:
                    netloc += f":{parsed.port}"
                return urlunparse(parsed._replace(netloc=netloc))
        return repo_url

    def _extract_tree_to_memory(self, repo, tree_obj: Tree, path_prefix: str):
        """Recursively extract tree contents to memory"""
        for item in tree_obj.items():
            name = item.path.decode("utf-8")
            obj_id = item.sha
            full_path = f"{path_prefix}/{name}" if path_prefix else name

            obj = repo[obj_id]

            if isinstance(obj, Tree):
                # Recursively process subdirectory
                self._extract_tree_to_memory(repo, obj, full_path)
            elif isinstance(obj, Blob):
                # Only keep Python files and check exclusions
                if full_path.endswith(".py") and not self._should_exclude(full_path):
                    virtual_file = VirtualFile(path=full_path, content=obj.data)
                    self.virtual_files[full_path] = virtual_file
                    # Update progress with file count
                    file_count = len(self.virtual_files)
                    self._progress_update(f"Extracted {file_count} Python files...")
                elif self._should_exclude(full_path):
                    self._log(f"🚫 Excluded: {full_path}")

    def _should_exclude(self, file_path: str) -> bool:
        """Check if file should be excluded"""
        if not self.exclude_patterns:
            return False

        file_path_normalized = file_path.replace("\\", "/")
        path_parts = file_path_normalized.split("/")

        for pattern in self.exclude_patterns:
            if fnmatch.fnmatch(file_path_normalized, pattern):
                return True
            for part in path_parts:
                if fnmatch.fnmatch(part, pattern):
                    return True
            if fnmatch.fnmatch(
                file_path_normalized, f"*/{pattern}/*"
            ) or fnmatch.fnmatch(file_path_normalized, f"*/{pattern}"):
                return True

        return False

    def _analyze_python_files(self):
        """Analyze Python files using tree-sitter"""
        if not self.parser:
            return

        total_files = len(self.virtual_files)
        analyzed_count = 0

        for file_path, virtual_file in self.virtual_files.items():
            try:
                analyzed_count += 1
                self._progress_update(
                    f"Analyzing file {analyzed_count}/{total_files}: {file_path}"
                )

                content = virtual_file.content
                tree = self.parser.parse(content)
                root_node = tree.root_node

                # Analyze functions
                self._analyze_functions_in_file(root_node, content, file_path)

                # Analyze classes
                self._analyze_classes_in_file(root_node, content, file_path)

            except Exception as e:
                self._log(f"⚠️  Error analyzing {file_path}: {e}")

    def _analyze_functions_in_file(
        self, root_node, source_bytes: bytes, file_path: str
    ):
        """Find functions in file using tree-sitter"""
        try:
            captures = self.queries["functions"].captures(root_node)
        except:
            # Fallback to manual traversal
            captures = []
            self._traverse_for_functions(root_node, captures)

        for node, _ in captures:
            if node.type == "function_definition":
                name_node = node.child_by_field_name("name")
                if not name_node:
                    continue

                func_name = self._get_node_text(name_node, source_bytes)
                line_start = node.start_point[0] + 1
                line_end = node.end_point[0] + 1

                # Extract function signature
                signature = None
                parameters_node = node.child_by_field_name("parameters")
                if parameters_node:
                    # Get the full function definition line
                    def_start_line = node.start_point[0]
                    def_text = source_bytes.decode("utf-8").split("\n")[def_start_line]

                    # Extract just the signature part (function name + parameters)
                    if "(" in def_text and ")" in def_text:
                        start_idx = def_text.find(func_name)
                        if start_idx != -1:
                            # Find the closing parenthesis, handling nested parens
                            paren_count = 0
                            end_idx = start_idx + len(func_name)
                            while end_idx < len(def_text):
                                char = def_text[end_idx]
                                if char == "(":
                                    paren_count += 1
                                elif char == ")":
                                    paren_count -= 1
                                    if paren_count == 0:
                                        end_idx += 1
                                        break
                                end_idx += 1

                            signature = def_text[start_idx:end_idx].strip()

                # Check if it's a method (inside a class)
                is_method = False
                class_name = None
                parent = node.parent
                while parent:
                    if parent.type == "class_definition":
                        is_method = True
                        class_name_node = parent.child_by_field_name("name")
                        if class_name_node:
                            class_name = self._get_node_text(
                                class_name_node, source_bytes
                            )
                        break
                    parent = parent.parent

                # Check if async
                is_async = False
                for child in node.children:
                    if child.type == "async" or (
                        child.type == "identifier"
                        and self._get_node_text(child, source_bytes) == "async"
                    ):
                        is_async = True
                        break

                full_name = f"{class_name}.{func_name}" if class_name else func_name

                self.functions[full_name] = FunctionInfo(
                    name=func_name,
                    file_path=file_path,
                    line_start=line_start,
                    line_end=line_end,
                    is_method=is_method,
                    class_name=class_name,
                    is_async=is_async,
                    signature=signature,
                )

    def _analyze_classes_in_file(self, root_node, source_bytes: bytes, file_path: str):
        """Find classes in file using tree-sitter"""
        try:
            captures = self.queries["classes"].captures(root_node)
        except:
            # Fallback to manual traversal
            captures = []
            self._traverse_for_classes(root_node, captures)

        for node, _ in captures:
            if node.type == "class_definition":
                name_node = node.child_by_field_name("name")
                if not name_node:
                    continue

                class_name = self._get_node_text(name_node, source_bytes)
                line_start = node.start_point[0] + 1
                line_end = node.end_point[0] + 1

                # Find methods
                methods = []
                for child in node.children:
                    if child.type == "block":
                        for block_child in child.children:
                            if block_child.type == "function_definition":
                                method_name_node = block_child.child_by_field_name(
                                    "name"
                                )
                                if method_name_node:
                                    method_name = self._get_node_text(
                                        method_name_node, source_bytes
                                    )
                                    methods.append(method_name)

                # Find base classes
                base_classes = []
                superclasses_node = node.child_by_field_name("superclasses")
                if superclasses_node:
                    for child in superclasses_node.children:
                        if child.type == "identifier":
                            base_class = self._get_node_text(child, source_bytes)
                            base_classes.append(base_class)

                self.classes[class_name] = ClassInfo(
                    name=class_name,
                    file_path=file_path,
                    line_start=line_start,
                    line_end=line_end,
                    methods=methods,
                    base_classes=base_classes,
                )

    def _traverse_for_functions(self, node, captures):
        """Fallback function traversal"""
        if node.type == "function_definition":
            captures.append((node, "func_def"))
        for child in node.children:
            self._traverse_for_functions(child, captures)

    def _traverse_for_classes(self, node, captures):
        """Fallback class traversal"""
        if node.type == "class_definition":
            captures.append((node, "class_def"))
        for child in node.children:
            self._traverse_for_classes(child, captures)

    def _get_node_text(self, node, source_bytes: bytes) -> str:
        """Get text content of a tree-sitter node"""
        return source_bytes[node.start_byte : node.end_byte].decode(
            "utf-8", errors="replace"
        )

    def search_combined(
        self, pattern: str, search_type: str = "both"
    ) -> List[Dict[str, Any]]:
        """Search functions and/or classes matching pattern"""
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            self._log(f"❌ Invalid regex pattern '{pattern}': {e}")
            return []

        matches = []

        # Search functions
        if search_type in ["both", "functions"]:
            for func_name, func_info in self.functions.items():
                if regex.search(func_info.name) or regex.search(func_name):
                    highlighted_name = regex.sub(lambda m: f"[{m.group()}]", func_name)
                    matches.append(
                        {
                            "type": "function",
                            "name": func_name,
                            "highlighted_name": highlighted_name,
                            "file": func_info.file_path,
                            "line_start": func_info.line_start,
                            "line_end": func_info.line_end,
                            "is_method": func_info.is_method,
                            "class_name": func_info.class_name,
                            "is_async": func_info.is_async,
                            "signature": func_info.signature,
                        }
                    )

        # Search classes
        if search_type in ["both", "classes"]:
            for class_name, class_info in self.classes.items():
                if regex.search(class_info.name):
                    highlighted_name = regex.sub(lambda m: f"[{m.group()}]", class_name)
                    matches.append(
                        {
                            "type": "class",
                            "name": class_name,
                            "highlighted_name": highlighted_name,
                            "file": class_info.file_path,
                            "line_start": class_info.line_start,
                            "line_end": class_info.line_end,
                            "methods_count": len(class_info.methods),
                            "base_classes": class_info.base_classes,
                        }
                    )

        return matches

    def preview_method(self, identifier: str) -> None:
        """Preview method/function content"""
        if ":" in identifier:
            if "-" in identifier:
                # Format: filename:start-end
                self._preview_by_location(identifier)
            else:
                # Format: filename:line_number (show function context)
                self._preview_function_around_line(identifier)
        else:
            self._preview_by_name(identifier)

    def _preview_by_name(self, name: str) -> None:
        """Preview by function/method name"""
        matches = []
        for func_name, func_info in self.functions.items():
            if name.lower() in func_name.lower():
                matches.append(func_info)

        if not matches:
            print(f"❌ No functions found matching '{name}'")
            return

        if len(matches) == 1:
            self._show_function_content(matches[0])
        else:
            print(f"🔍 Multiple matches found for '{name}':")
            for i, match in enumerate(matches, 1):
                func_type = "Method" if match.is_method else "Function"
                class_info = f" ({match.class_name})" if match.class_name else ""
                signature_info = f" - {match.signature}" if match.signature else ""
                print(
                    f"   {i}. {match.name} in {match.file_path} (L{match.line_start}-{match.line_end}) - {func_type}{class_info}{signature_info}"
                )

    def _preview_by_location(self, location: str) -> None:
        """Preview by location (filename:start-end)"""
        parts = location.split(":")
        if len(parts) != 2:
            print(f"❌ Invalid location format: {location}")
            return

        filename, range_part = parts
        if "-" not in range_part:
            print(f"❌ Invalid range format: {range_part}")
            return

        try:
            # Remove 'L' prefix if present (e.g., L80-166 -> 80-166)
            range_clean = range_part.replace("L", "").replace("l", "")
            start_line, end_line = map(int, range_clean.split("-"))
        except ValueError:
            print(f"❌ Invalid line numbers: {range_part}")
            return

        # Find matching file
        matching_files = [
            path for path in self.virtual_files.keys() if filename in path
        ]

        if not matching_files:
            print(f"❌ File not found: {filename}")
            return

        if len(matching_files) > 1:
            print(f"❌ Multiple files match '{filename}': {matching_files}")
            return

        self._show_file_content(matching_files[0], start_line, end_line)

    def _preview_function_around_line(self, location: str) -> None:
        """Preview function context around a specific line number"""
        parts = location.split(":")
        if len(parts) != 2:
            print(f"❌ Invalid location format: {location}")
            return

        filename, line_str = parts
        try:
            target_line = int(line_str.replace("L", "").replace("l", ""))
        except ValueError:
            print(f"❌ Invalid line number: {line_str}")
            return

        # Find matching file
        matching_files = [
            path for path in self.virtual_files.keys() if filename in path
        ]

        if not matching_files:
            print(f"❌ File not found: {filename}")
            return

        if len(matching_files) > 1:
            print(f"❌ Multiple files match '{filename}': {matching_files}")
            return

        file_path = matching_files[0]

        # Find function containing the target line
        containing_function = None
        for func_name, func_info in self.functions.items():
            if (
                func_info.file_path == file_path
                and func_info.line_start <= target_line <= func_info.line_end
            ):
                containing_function = func_info
                break

        if containing_function:
            print(
                f"📍 Line {target_line} is inside function: {containing_function.name}"
            )
            func_type = "Method" if containing_function.is_method else "Function"
            class_info = (
                f" ({containing_function.class_name})"
                if containing_function.class_name
                else ""
            )
            async_prefix = "async " if containing_function.is_async else ""
            print(
                f"🔧 {async_prefix}{func_type}: {containing_function.name}{class_info}"
            )
            print(
                f"📄 Function range: L{containing_function.line_start}-{containing_function.line_end}"
            )
            print()

            # Show the function with some context
            context_start = max(1, containing_function.line_start - 2)
            context_end = containing_function.line_end + 2
            self._show_file_content(
                file_path, context_start, context_end, highlight_line=target_line
            )
        else:
            # No function found, show context around the line
            print(f"📍 No function found containing line {target_line}")
            print(f"🔍 Showing context around line {target_line}")
            print()

            context_start = max(1, target_line - 10)
            context_end = target_line + 10
            self._show_file_content(
                file_path, context_start, context_end, highlight_line=target_line
            )

    def _show_function_content(self, func_info: FunctionInfo) -> None:
        """Show function content"""
        self._show_file_content(
            func_info.file_path, func_info.line_start, func_info.line_end
        )

    def _show_file_content(
        self, file_path: str, start_line: int, end_line: int, highlight_line: int = None
    ) -> None:
        """Show file content for specified lines"""
        if file_path not in self.virtual_files:
            print(f"❌ File not found: {file_path}")
            return

        virtual_file = self.virtual_files[file_path]
        content = virtual_file.text_content
        lines = content.split("\n")

        start_idx = max(0, start_line - 1)
        end_idx = min(len(lines), end_line)

        print(f"\n📖 File: {file_path}")
        print(f"📍 Lines: {start_line}-{end_line}")
        if highlight_line:
            print(f"🎯 Highlighting line: {highlight_line}")
        print("=" * 80)

        for i in range(start_idx, end_idx):
            line_num = i + 1
            line_content = lines[i]

            # Highlight the target line
            if highlight_line and line_num == highlight_line:
                print(f"{line_num:4d} >>> {line_content}")
            else:
                print(f"{line_num:4d} | {line_content}")

        print("=" * 80)
        print(f"📊 Total lines: {end_idx - start_idx}")
        if highlight_line:
            print(f"🎯 Target line {highlight_line} is highlighted with '>>>')")

    def print_summary(self) -> None:
        """Print analysis summary"""
        print(f"\n📊 IN-MEMORY ANALYSIS SUMMARY")
        print("=" * 50)
        print(f"📁 Files analyzed: {len(self.virtual_files)}")
        print(f"🔧 Functions found: {len(self.functions)}")
        print(f"🏗️  Classes found: {len(self.classes)}")

        if self.repo_info:
            print(f"🌿 Branch: {self.repo_info.branch}")
            if self.repo_info.commit_sha:
                print(f"📝 Commit: {self.repo_info.commit_sha[:8]}")

    def list_functions(self, limit: int = 20, show_all: bool = True) -> None:
        """List available functions"""
        if not self.functions:
            print("❌ No functions found")
            return

        print(f"📋 Available Functions ({len(self.functions)} found):")
        print("=" * 50)

        # Group by file
        by_file = {}
        for func_name, func_info in self.functions.items():
            if func_info.file_path not in by_file:
                by_file[func_info.file_path] = []
            by_file[func_info.file_path].append((func_name, func_info))

        shown_count = 0
        for file_path in sorted(by_file.keys()):
            if not show_all and shown_count >= limit:
                break
            print(f"\n📄 {file_path}:")
            file_functions = sorted(by_file[file_path], key=lambda x: x[1].line_start)
            for func_name, func_info in file_functions:
                if not show_all and shown_count >= limit:
                    break
                func_type = "Method" if func_info.is_method else "Function"
                async_prefix = "async " if func_info.is_async else ""
                class_info = (
                    f" ({func_info.class_name})" if func_info.class_name else ""
                )
                signature_info = (
                    f" - {func_info.signature}" if func_info.signature else ""
                )
                print(
                    f"   🔧 {async_prefix}{func_name} (L{func_info.line_start}-{func_info.line_end}) - {func_type}{class_info}{signature_info}"
                )
                shown_count += 1

        if not show_all and len(self.functions) > limit:
            print(f"\n... and {len(self.functions) - limit} more functions")

    def list_classes(self, limit: int = 20, show_all: bool = True) -> None:
        """List available classes"""
        if not self.classes:
            print("❌ No classes found")
            return

        print(f"📋 Available Classes ({len(self.classes)} found):")
        print("=" * 50)

        shown_count = 0
        for class_name, class_info in sorted(self.classes.items()):
            if not show_all and shown_count >= limit:
                break

            base_info = (
                f" extends {', '.join(class_info.base_classes)}"
                if class_info.base_classes
                else ""
            )
            print(
                f"🏗️  {class_name} ({class_info.file_path}:L{class_info.line_start}-{class_info.line_end}) - {len(class_info.methods)} methods{base_info}"
            )
            shown_count += 1

        if not show_all and len(self.classes) > limit:
            print(f"\n... and {len(self.classes) - limit} more classes")

    def list_all_files(self, pattern: str = "*", limit: int = 100) -> None:
        """List all files in the repository with optional pattern matching"""
        if not self.virtual_files:
            print("❌ No files found")
            return

        import fnmatch

        files = []
        for file_path in self.virtual_files.keys():
            if fnmatch.fnmatch(file_path, pattern) or fnmatch.fnmatch(
                file_path.split("/")[-1], pattern
            ):
                files.append(file_path)

        files = sorted(files)

        print(f"📋 Files matching '{pattern}' ({len(files)} found):")
        print("=" * 50)

        # Show files with numbering
        for i, file_path in enumerate(files[:limit], 1):
            print(f"{i:3d}. 📄 {file_path}")

        if len(files) > limit:
            print(f"\n... and {len(files) - limit} more files")

        print(f"\nTotal files in repository: {len(self.virtual_files)}")

    def grep_content(
        self,
        pattern: str,
        file_pattern: str = "*.py",
        case_sensitive: bool = False,
        line_limit: int = 50,
    ) -> None:
        """Search (grep) for text patterns within file contents"""
        if not self.virtual_files:
            print("❌ No files found")
            return

        import re
        import fnmatch

        # Compile regex pattern
        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            regex = re.compile(pattern, flags)
        except re.error as e:
            print(f"❌ Invalid regex pattern '{pattern}': {e}")
            return

        matches = []

        # Search through files
        for file_path, virtual_file in self.virtual_files.items():
            # Check if file matches the file pattern
            if not (
                fnmatch.fnmatch(file_path, file_pattern)
                or fnmatch.fnmatch(file_path.split("/")[-1], file_pattern)
            ):
                continue

            if hasattr(virtual_file, "content") and virtual_file.content:
                lines = virtual_file.content.splitlines()
                for line_num, line in enumerate(lines, 1):
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

        if not matches:
            print(f"❌ No matches found for pattern: '{pattern}'")
            return

        print(f"🔍 Grep results for '{pattern}' ({len(matches)} matches found):")
        print("=" * 50)

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

            print(f"\n📄 {file_path}:")
            file_matches = by_file[file_path]

            for match in file_matches:
                if shown_count >= line_limit:
                    break
                print(f"   L{match['line']:4d}: {match['highlighted']}")
                shown_count += 1

        if len(matches) > line_limit:
            print(f"\n... and {len(matches) - line_limit} more matches")

        print(f"\nTotal: {len(matches)} matches in {len(by_file)} files")


# Main function definition


def main():
    # Parse arguments first to get debug mode

    parser = argparse.ArgumentParser(
        description="In-Memory Dulwich Repository Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python dulwich_memory_analyzer.py --repo https://github.com/user/repo
    python dulwich_memory_analyzer.py --repo https://git.example.com/project.git --username user --password pass
    python dulwich_memory_analyzer.py --repo user/repo --search "async.*"
    python dulwich_memory_analyzer.py --repo user/repo --list-functions --exclude-preset dev
        """,
    )
    # ArgumentParser created

    # Repository options
    parser.add_argument(
        "--repo", required=True, help="Repository URL or GitHub shorthand"
    )
    parser.add_argument("--branch", "-b", help="Branch to analyze (default: main)")

    # Authentication
    parser.add_argument("--username", "-u", help="Username for authentication")
    parser.add_argument("--password", "-p", help="Password for authentication")
    parser.add_argument("--auth", help="Auth in format username:password")

    # Analysis options
    parser.add_argument("--search", help="Search functions and classes")
    parser.add_argument("--search-functions", help="Search functions only")
    parser.add_argument("--search-classes", help="Search classes only")
    parser.add_argument("--preview", help="Preview method/function content")
    parser.add_argument(
        "--list-functions", action="store_true", help="List all functions"
    )
    parser.add_argument("--list-classes", action="store_true", help="List all classes")

    # Exclusions
    parser.add_argument("--exclude", nargs="+", help="Exclude patterns")
    parser.add_argument(
        "--exclude-preset", choices=["dev", "minimal", "comprehensive", "library"]
    )

    # Options
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument(
        "--summary",
        "-s",
        action="store_true",
        help="Show abbreviated output with limits",
    )

    args = parser.parse_args()

    # Enable debug mode if verbose is set
    debug_mode = args.verbose

    # Parse auth
    username = args.username
    password = args.password
    if args.auth and ":" in args.auth:
        username, password = args.auth.split(":", 1)
    if debug_mode:
        print(f"🔧 Debug: Auth parsed, username: {'Yes' if username else 'No'}")

    # Parse exclusions
    exclude_patterns = []
    if args.exclude:
        exclude_patterns.extend(args.exclude)
    if args.exclude_preset:
        try:
            from combined_cli_analyzer import get_exclusion_preset

            exclude_patterns.extend(get_exclusion_preset(args.exclude_preset))
        except ImportError:
            print(
                "⚠️  Exclusion presets not available (combined_cli_analyzer not found)"
            )

    print("🚀 In-Memory Dulwich Repository Analyzer")
    print("=" * 50)

    if debug_mode:
        print(f"🔧 Debug: Starting with repo: {args.repo}")
        print(f"🔧 Debug: Username provided: {'Yes' if username else 'No'}")
        print(f"🔧 Debug: Exclude patterns: {exclude_patterns}")

    # Analyze
    if debug_mode:
        print("🔧 Debug: Creating analyzer...")
    analyzer = InMemoryAnalyzer(
        verbose=args.verbose,
        exclude_patterns=exclude_patterns,
        username=username,
        password=password,
        show_all=not args.summary,
    )
    if debug_mode:
        print("🔧 Debug: Analyzer created successfully")

    # Fetch repository
    if debug_mode:
        print("🔧 Debug: About to fetch repository...")
    if not analyzer.fetch_repository_tree(args.repo, args.branch):
        if debug_mode:
            print("🔧 Debug: Repository fetch failed")
        return 1
    if debug_mode:
        print("🔧 Debug: Repository fetch completed")

    # Determine analysis type and execute
    if args.search:
        matches = analyzer.search_combined(args.search, "both")
        if matches:
            print(f"\n🔍 Found {len(matches)} matches for '{args.search}':")
            for match in matches:
                if match["type"] == "function":
                    func_type = "Method" if match["is_method"] else "Function"
                    async_prefix = "async " if match["is_async"] else ""
                    class_info = (
                        f" ({match['class_name']})" if match.get("class_name") else ""
                    )
                    signature_info = (
                        f" - {match['signature']}" if match.get("signature") else ""
                    )
                    print(
                        f"🔧 {async_prefix}{match['highlighted_name']} ({match['file']}:L{match['line_start']}-{match['line_end']}) - {func_type}{class_info}{signature_info}"
                    )
                else:
                    base_info = (
                        f" extends {', '.join(match['base_classes'])}"
                        if match.get("base_classes")
                        else ""
                    )
                    print(
                        f"🏗️  {match['highlighted_name']} ({match['file']}:L{match['line_start']}-{match['line_end']}) - {match['methods_count']} methods{base_info}"
                    )
        else:
            print(f"❌ No matches found for '{args.search}'")

    elif args.search_functions:
        matches = analyzer.search_combined(args.search_functions, "functions")
        if matches:
            print(
                f"\n🔧 Found {len(matches)} function matches for '{args.search_functions}':"
            )
            for match in matches:
                func_type = "Method" if match["is_method"] else "Function"
                async_prefix = "async " if match["is_async"] else ""
                class_info = (
                    f" ({match['class_name']})" if match.get("class_name") else ""
                )
                print(
                    f"🔧 {async_prefix}{match['highlighted_name']} ({match['file']}:L{match['line_start']}-{match['line_end']}) - {func_type}{class_info}"
                )
        else:
            print(f"❌ No function matches found for '{args.search_functions}'")

    elif args.search_classes:
        matches = analyzer.search_combined(args.search_classes, "classes")
        if matches:
            print(
                f"\n🏗️ Found {len(matches)} class matches for '{args.search_classes}':"
            )
            for match in matches:
                base_info = (
                    f" extends {', '.join(match['base_classes'])}"
                    if match.get("base_classes")
                    else ""
                )
                print(
                    f"🏗️  {match['highlighted_name']} ({match['file']}:L{match['line_start']}-{match['line_end']}) - {match['methods_count']} methods{base_info}"
                )
        else:
            print(f"❌ No class matches found for '{args.search_classes}'")

    elif args.preview:
        analyzer.preview_method(args.preview)

    elif args.list_functions:
        analyzer.list_functions(show_all=not args.summary)

    elif args.list_classes:
        analyzer.list_classes(show_all=not args.summary)

    else:
        analyzer.print_summary()

    return 0


if __name__ == "__main__":
    if not DULWICH_AVAILABLE:
        print("❌ dulwich required: pip install dulwich")
        sys.exit(1)

    # Starting main execution
    sys.exit(main())
