#!/usr/bin/env python3
"""
Combined Python Code Analyzer CLI

This script provides a unified interface for both Tree-sitter and Call Graph analysis
of Python codebases. It can perform structural analysis, function call analysis,
and provide detailed reports.

Installation:
    pip install tree-sitter tree-sitter-python

Usage:
    python combined_cli_analyzer.py --help
    python combined_cli_analyzer.py --treesitter                    # Tree-sitter analysis only
    python combined_cli_analyzer.py --callgraph                     # Call graph analysis only
    python combined_cli_analyzer.py --both                          # Both analyses (default)
    python combined_cli_analyzer.py --function main --verbose       # Detailed function analysis
    python combined_cli_analyzer.py --export-formats json,dot       # Export results
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, asdict
import time
import re
import fnmatch
import glob

# Import our existing analyzers
try:
    from treesitter_analyzer import TreeSitterPythonAnalyzer, find_python_files
    from call_graph_analyzer import CallGraphAnalyzer

    ANALYZERS_AVAILABLE = True
except ImportError as e:
    print(f"❌ Error importing analyzers: {e}")
    print(
        "Make sure treesitter_analyzer.py and call_graph_analyzer.py are in the same directory"
    )
    sys.exit(1)


def get_exclusion_preset(preset_name: str) -> List[str]:
    """Get predefined exclusion patterns for common use cases"""
    presets = {
        "minimal": [
            "__pycache__",
            "*.pyc",
            ".git",
        ],
        "dev": [
            "test*",
            "__pycache__",
            "*.pyc",
            ".git",
            ".venv",
            "venv",
            "build",
            "dist",
        ],
        "comprehensive": [
            "test*",
            "*test*",
            ".*test*",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".coverage",
            ".git",
            ".svn",
            ".hg",
            ".venv",
            "venv",
            "env",
            "*/site-packages/*",
            "build",
            "dist",
            "*.egg-info",
            "docs",
            "examples",
            "scripts",
            "tools",
            ".vscode",
            ".idea",
            "*.sublime-*",
            "*.pyc",
            "*.pyo",
            "*.pyd",
            "*.so",
            "*.log",
            "logs",
            "*/logs/*",
            "node_modules",
            "bower_components",
        ],
        "library": [
            "*/tests/**",
            "test_*",
            "*_test.py",
            "setup.py",
            "setup.cfg",
            "pyproject.toml",
            "tox.ini",
            "pytest.ini",
            "conftest.py",
            "docs",
            "examples",
            "benchmarks",
            "__pycache__",
            "build",
            "dist",
            ".git",
            ".github",
            ".gitlab",
        ],
    }
    return presets.get(preset_name, [])


@dataclass
class AnalysisResults:
    """Combined results from both analyzers"""

    treesitter_results: Optional[Dict[str, Any]] = None
    callgraph_results: Optional[Dict[str, Any]] = None
    analysis_time: float = 0.0
    files_analyzed: int = 0
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class CombinedAnalyzer:
    """Combined analyzer that orchestrates both Tree-sitter and Call Graph analysis"""

    def __init__(
        self,
        verbose: bool = False,
        show_full_paths: bool = True,
        exclude_patterns: List[str] = None,
    ):
        self.verbose = verbose
        self.show_full_paths = show_full_paths
        self.exclude_patterns = exclude_patterns or []
        self.treesitter_analyzer = None
        self.callgraph_analyzer = None

    def _log(self, message: str, force: bool = False):
        """Log message if verbose mode is enabled or force is True"""
        if self.verbose or force:
            print(message)

    def _init_analyzers(self) -> bool:
        """Initialize both analyzers"""
        try:
            self.treesitter_analyzer = TreeSitterPythonAnalyzer(verbose=self.verbose)
            self.callgraph_analyzer = CallGraphAnalyzer(verbose=self.verbose)

            return True
        except Exception as e:
            self._log(f"❌ Failed to initialize analyzers: {e}", force=True)
            return False

    def analyze_directory(
        self,
        directory: str,
        recursive: bool = True,
        run_treesitter: bool = True,
        run_callgraph: bool = True,
    ) -> AnalysisResults:
        """Run combined analysis on a directory"""
        start_time = time.time()
        results = AnalysisResults()

        if not self._init_analyzers():
            results.errors.append("Failed to initialize analyzers")
            return results

        self._log(f"🔍 Starting combined analysis of: {directory}")
        self._log(
            f"📊 Tree-sitter: {'✅' if run_treesitter else '❌'}, Call Graph: {'✅' if run_callgraph else '❌'}"
        )

        # Count Python files
        python_files = self._find_python_files(directory, recursive)
        results.files_analyzed = len(python_files)
        self._log(f"📁 Found {len(python_files)} Python files")

        # Run Tree-sitter analysis
        if run_treesitter:
            try:
                self._log("🌳 Running Tree-sitter analysis...")

                # Find Python files with exclusions
                python_files = self._find_python_files(directory, recursive)

                if not self.verbose:
                    # Temporarily redirect stdout to suppress non-verbose output
                    import io

                    old_stdout = sys.stdout
                    sys.stdout = io.StringIO()

                # Analyze all files
                ts_analyses = []
                for file_path in python_files:
                    if self.verbose:
                        self._log(f"   🔍 Analyzing {Path(file_path).name}...")
                    analysis = self.treesitter_analyzer.analyze_file(file_path)
                    ts_analyses.append(analysis)

                if not self.verbose:
                    sys.stdout = old_stdout

                # Convert results to serializable format
                results.treesitter_results = {
                    "summary": {
                        "files_analyzed": len(ts_analyses),
                        "total_classes": sum(
                            len(analysis.classes) for analysis in ts_analyses
                        ),
                        "total_functions": sum(
                            len(analysis.functions) for analysis in ts_analyses
                        ),
                        "total_imports": sum(
                            len(analysis.imports) for analysis in ts_analyses
                        ),
                    },
                    "files": {
                        str(Path(analysis.file_path).name): asdict(analysis)
                        for analysis in ts_analyses
                    },
                }
                # Store results for class search functionality
                self._treesitter_results = results.treesitter_results
                self._log("✅ Tree-sitter analysis completed")
            except Exception as e:
                error_msg = f"Tree-sitter analysis failed: {e}"
                self._log(f"❌ {error_msg}")
                results.errors.append(error_msg)

        # Run Call Graph analysis
        if run_callgraph:
            try:
                self._log("🔗 Running Call Graph analysis...")

                # Find Python files with exclusions for call graph too
                python_files_cg = self._find_python_files(directory, recursive)

                if not self.verbose:
                    # Temporarily redirect stdout to suppress non-verbose output
                    import io
                    import contextlib

                    old_stdout = sys.stdout
                    sys.stdout = io.StringIO()
                    try:
                        # Analyze each file individually with exclusions
                        for file_path in python_files_cg:
                            self.callgraph_analyzer.analyze_file(str(file_path))
                    finally:
                        sys.stdout = old_stdout
                else:
                    # Analyze each file individually with exclusions
                    for file_path in python_files_cg:
                        self._log(f"   🔍 Analyzing {Path(file_path).name}...")
                        self.callgraph_analyzer.analyze_file(str(file_path))

                # Extract results
                results.callgraph_results = {
                    "summary": {
                        "functions_found": len(self.callgraph_analyzer.functions),
                        "modules_imported": len(self.callgraph_analyzer.modules),
                        "call_relationships": sum(
                            len(callees)
                            for callees in self.callgraph_analyzer.call_graph.values()
                        ),
                    },
                    "functions": {
                        name: {
                            "file": str(Path(func.file_path).name),
                            "line": func.line,
                            "is_method": func.is_method,
                            "class_name": func.class_name,
                        }
                        for name, func in self.callgraph_analyzer.functions.items()
                    },
                    "modules": {
                        name: {
                            "import_count": len(module.import_locations),
                            "usage_count": len(module.usage_locations),
                        }
                        for name, module in self.callgraph_analyzer.modules.items()
                    },
                    "call_graph": dict(self.callgraph_analyzer.call_graph),
                    "reverse_call_graph": dict(
                        self.callgraph_analyzer.reverse_call_graph
                    ),
                }
                self._log("✅ Call Graph analysis completed")
            except Exception as e:
                error_msg = f"Call Graph analysis failed: {e}"
                self._log(f"❌ {error_msg}")
                results.errors.append(error_msg)

        results.analysis_time = time.time() - start_time
        self._log(f"⏱️  Total analysis time: {results.analysis_time:.2f} seconds")

        return results

    def _find_python_files(self, directory: str, recursive: bool) -> List[Path]:
        """Find all Python files in directory, excluding files/directories matching patterns"""
        path = Path(directory)

        if recursive:
            python_files = list(path.rglob("*.py"))
        else:
            python_files = list(path.glob("*.py"))

        # Filter out excluded patterns
        if self.exclude_patterns:
            filtered_files = []
            for file_path in python_files:
                should_exclude = False
                file_path_str = str(file_path)

                for exclude_pattern in self.exclude_patterns:
                    # Convert relative pattern to absolute if needed
                    if exclude_pattern.startswith("./"):
                        exclude_pattern = exclude_pattern[2:]

                    # Check different matching strategies
                    if self._matches_exclude_pattern(file_path, exclude_pattern):
                        should_exclude = True
                        break

                if not should_exclude:
                    filtered_files.append(file_path)

            if self.verbose:
                excluded_count = len(python_files) - len(filtered_files)
                if excluded_count > 0:
                    self._log(
                        f"🚫 Excluded {excluded_count} files matching patterns {self.exclude_patterns}"
                    )
                    # Show some examples of excluded files
                    excluded_files = [
                        f for f in python_files if f not in filtered_files
                    ]
                    for i, excluded_file in enumerate(excluded_files[:5]):
                        self._log(f"   - {excluded_file}")
                    if len(excluded_files) > 5:
                        self._log(f"   ... and {len(excluded_files) - 5} more")

                    # Debug: Show what patterns matched
                    if self.verbose:
                        self._log(
                            f"   🔍 Debug: Testing exclusion patterns on sample files:"
                        )
                        for test_file in python_files[:3]:
                            for pattern in self.exclude_patterns:
                                matches = self._matches_exclude_pattern(
                                    test_file, pattern
                                )
                                self._log(f"   - {test_file} vs '{pattern}': {matches}")

            return filtered_files

        return python_files

    def _matches_exclude_pattern(self, file_path: Path, pattern: str) -> bool:
        """Check if file path matches exclusion pattern using various strategies"""
        file_path_str = str(file_path)
        file_path_posix = file_path.as_posix()

        # Debug logging
        if self.verbose:
            self._log(f"   🔍 Matching '{file_path_posix}' against pattern '{pattern}'")

        # Strategy 1: Direct glob pattern matching on full path
        if fnmatch.fnmatch(file_path_posix, pattern) or fnmatch.fnmatch(
            file_path_str, pattern
        ):
            if self.verbose:
                self._log(f"   ✅ Match: Direct path match")
            return True

        # Strategy 2: Check if any directory in path matches pattern exactly
        path_parts = file_path.parts
        for part in path_parts:
            if fnmatch.fnmatch(part, pattern):
                if self.verbose:
                    self._log(f"   ✅ Match: Directory part '{part}' matches pattern")
                return True

        # Strategy 3: Pattern with wildcards - check if path contains matching directory
        if fnmatch.fnmatch(file_path_posix, f"*/{pattern}/*") or fnmatch.fnmatch(
            file_path_posix, f"*/{pattern}"
        ):
            if self.verbose:
                self._log(f"   ✅ Match: Wildcard directory match")
            return True

        # Strategy 4: Check if file is inside a directory matching pattern
        for i, part in enumerate(path_parts[:-1]):  # Exclude filename
            if fnmatch.fnmatch(part, pattern):
                if self.verbose:
                    self._log(
                        f"   ✅ Match: Inside directory '{part}' that matches pattern"
                    )
                return True
            # Also check if the pattern matches the path up to this point
            partial_path = "/".join(path_parts[: i + 1])
            if fnmatch.fnmatch(partial_path, pattern):
                if self.verbose:
                    self._log(
                        f"   ✅ Match: Partial path '{partial_path}' matches pattern"
                    )
                return True

        # Strategy 5: Directory with contents (pattern ending with /*)
        if pattern.endswith("/*"):
            dir_pattern = pattern[:-2]  # Remove /*
            for part in path_parts[:-1]:  # Exclude filename
                if fnmatch.fnmatch(part, dir_pattern):
                    if self.verbose:
                        self._log(
                            f"   ✅ Match: Directory contents pattern matches '{part}'"
                        )
                    return True

        # Strategy 6: Relative path matching from root
        try:
            if len(path_parts) > 0:
                for i in range(len(path_parts)):
                    relative_path = "/".join(path_parts[i:])
                    if fnmatch.fnmatch(relative_path, pattern):
                        if self.verbose:
                            self._log(
                                f"   ✅ Match: Relative path '{relative_path}' matches pattern"
                            )
                        return True
        except:
            pass

        if self.verbose:
            self._log(f"   ❌ No match for '{file_path_posix}' against '{pattern}'")
        return False

    def preview_method(self, identifier: str) -> None:
        """Preview method/function content by name or location (filename:start-end)"""
        if ":" in identifier and "-" in identifier:
            # Format: filename:start-end
            parts = identifier.split(":")
            if len(parts) == 2:
                filename, line_range = parts
                if "-" in line_range:
                    try:
                        start_line, end_line = map(int, line_range.split("-"))
                        self._preview_by_location(filename, start_line, end_line)
                        return
                    except ValueError:
                        pass

        # Search by name
        self._preview_by_name(identifier)

    def _preview_by_name(self, name: str) -> None:
        """Preview method/function by name"""
        matches = []

        # Search in functions
        if self.callgraph_analyzer and self.callgraph_analyzer.functions:
            for func_name, func_def in self.callgraph_analyzer.functions.items():
                if name.lower() in func_name.lower():
                    end_line = self._get_function_end_line(
                        func_def.file_path, func_def.line
                    )
                    matches.append(
                        {
                            "name": func_name,
                            "file_path": func_def.file_path,
                            "start_line": func_def.line,
                            "end_line": end_line,
                            "type": "Method" if func_def.is_method else "Function",
                            "class_name": func_def.class_name,
                        }
                    )

        if not matches:
            print(f"❌ No functions found matching '{name}'")
            return

        if len(matches) == 1:
            match = matches[0]
            self._show_method_content(
                match["file_path"],
                match["start_line"],
                match["end_line"],
                match["name"],
                match["type"],
            )
        else:
            print(f"🔍 Multiple matches found for '{name}':")
            for i, match in enumerate(matches, 1):
                file_display = (
                    match["file_path"]
                    if self.show_full_paths
                    else Path(match["file_path"]).name
                )
                class_info = (
                    f" ({match['class_name']})" if match.get("class_name") else ""
                )
                print(
                    f"   {i}. {match['name']} in {file_display} (L{match['start_line']}-{match['end_line']}) - {match['type']}{class_info}"
                )

            print(
                f"\n💡 Use specific location format: filename:{matches[0]['start_line']}-{matches[0]['end_line']}"
            )

    def _preview_by_location(
        self, filename: str, start_line: int, end_line: int
    ) -> None:
        """Preview method/function by file location"""
        # Find the full path
        file_path = None
        if self.callgraph_analyzer:
            for func_def in self.callgraph_analyzer.functions.values():
                if filename in func_def.file_path:
                    file_path = func_def.file_path
                    break

        if not file_path:
            # Try to find file in current directory
            from pathlib import Path

            potential_paths = list(Path(".").rglob(f"*{filename}*"))
            if potential_paths:
                file_path = str(potential_paths[0])
            else:
                print(f"❌ File '{filename}' not found")
                return

        self._show_method_content(
            file_path, start_line, end_line, f"{filename}:{start_line}-{end_line}"
        )

    def _show_method_content(
        self,
        file_path: str,
        start_line: int,
        end_line: int,
        name: str = "",
        method_type: str = "Code",
    ) -> None:
        """Show the actual content of a method/function"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Adjust for 0-based indexing
            start_idx = max(0, start_line - 1)
            end_idx = min(len(lines), end_line)

            file_display = file_path if self.show_full_paths else Path(file_path).name
            print(f"\n📖 {method_type}: {name}")
            print(f"📄 File: {file_display}")
            print(f"📍 Lines: {start_line}-{end_line}")
            print("=" * 80)

            for i in range(start_idx, end_idx):
                line_num = i + 1
                line_content = lines[i].rstrip()
                print(f"{line_num:4d} | {line_content}")

            print("=" * 80)
            print(f"📊 Total lines: {end_idx - start_idx}")

        except FileNotFoundError:
            print(f"❌ File not found: {file_path}")
        except Exception as e:
            print(f"❌ Error reading file: {e}")

    def print_summary(self, results: AnalysisResults, detailed: bool = False):
        """Print analysis summary"""
        print(f"\n📊 COMBINED ANALYSIS SUMMARY")
        print(f"{'=' * 50}")
        print(f"📁 Files analyzed: {results.files_analyzed}")
        print(f"⏱️  Analysis time: {results.analysis_time:.2f} seconds")

        if results.errors:
            print(f"\n❌ Errors ({len(results.errors)}):")
            for error in results.errors:
                print(f"   {error}")

        # Tree-sitter summary
        if results.treesitter_results:
            ts_summary = results.treesitter_results["summary"]
            print(f"\n🌳 TREE-SITTER RESULTS:")
            print(f"   📦 Classes: {ts_summary['total_classes']}")
            print(f"   🔧 Functions: {ts_summary['total_functions']}")
            print(f"   📥 Imports: {ts_summary['total_imports']}")

            # Detailed tree-sitter output
            if detailed and "files" in results.treesitter_results:
                print(f"\n📂 DETAILED TREE-SITTER ANALYSIS:")
                print(f"{'=' * 50}")
                self._print_detailed_treesitter(results.treesitter_results["files"])

        # Call graph summary
        if results.callgraph_results:
            cg_summary = results.callgraph_results["summary"]
            print(f"\n🔗 CALL GRAPH RESULTS:")
            print(f"   🔧 Functions: {cg_summary['functions_found']}")
            print(f"   📦 Modules: {cg_summary['modules_imported']}")
            print(f"   🔗 Relationships: {cg_summary['call_relationships']}")

            # Detailed call graph output
            if detailed and "functions" in results.callgraph_results:
                print(f"\n🔧 DETAILED CALL GRAPH ANALYSIS:")
                print(f"{'=' * 50}")
                self._print_detailed_callgraph(results.callgraph_results)

    def analyze_function(self, function_name: str = None) -> Dict[str, Any]:
        """Analyze a specific function using both analyzers"""
        if not self.callgraph_analyzer:
            return {"error": "Call graph analyzer not initialized"}

        # If no function name provided, list available functions
        if not function_name:
            self.list_available_functions()
            return {"status": "listed_functions"}

        # Use call graph analyzer's improved function search
        # Temporarily enable debug mode for function details
        old_verbose = self.verbose
        if not self.verbose:
            # Redirect stdout to capture the output
            import io

            old_stdout = sys.stdout
            sys.stdout = io.StringIO()

        try:
            self.callgraph_analyzer.print_function_details(function_name)
            if not old_verbose:
                output = sys.stdout.getvalue()
                sys.stdout = old_stdout
                if "Function" in output and "not found" not in output:
                    print(output)  # Print the captured output
                else:
                    print(output)  # Print error message too
        finally:
            if not old_verbose and "old_stdout" in locals():
                sys.stdout = old_stdout

        return {"status": "completed"}

    def list_available_functions(self, limit: int = 20) -> None:
        """List available functions in the analyzed codebase"""
        if not self.callgraph_analyzer or not self.callgraph_analyzer.functions:
            print("❌ No functions found. Run analysis first.")
            return

        functions = list(self.callgraph_analyzer.functions.keys())
        total_count = len(functions)

        print(f"📋 Available Functions ({total_count} found):")
        print("=" * 50)

        # Group by file for better organization
        by_file = {}
        for func_name, func_def in self.callgraph_analyzer.functions.items():
            file_display = (
                func_def.file_path
                if self.show_full_paths
                else Path(func_def.file_path).name
            )
            if file_display not in by_file:
                by_file[file_display] = []
            by_file[file_display].append((func_name, func_def))

        shown_count = 0
        for file_display in sorted(by_file.keys()):
            if shown_count >= limit:
                break
            print(f"\n📄 {file_display}:")
            file_functions = sorted(by_file[file_display], key=lambda x: x[1].line)
            for func_name, func_def in file_functions:
                if shown_count >= limit:
                    break
                func_type = "Method" if func_def.is_method else "Function"
                class_info = f" ({func_def.class_name})" if func_def.class_name else ""
                print(f"   🔧 {func_name} (L{func_def.line}) - {func_type}{class_info}")
                shown_count += 1

        if total_count > limit:
            print(f"\n... and {total_count - limit} more functions")
            print(f"💡 Use --function <name> to analyze a specific function")

    def search_combined(
        self, pattern: str, limit: int = 50, search_type: str = "both"
    ) -> None:
        """Search for functions and/or classes matching a regex pattern"""
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            print(f"❌ Invalid regex pattern '{pattern}': {e}")
            return

        all_matches = []

        # Search functions if requested
        if (
            search_type in ["both", "functions"]
            and self.callgraph_analyzer
            and self.callgraph_analyzer.functions
        ):
            for func_name, func_def in self.callgraph_analyzer.functions.items():
                if regex.search(func_name):
                    # Get start/end line numbers from source if possible
                    end_line = self._get_function_end_line(
                        func_def.file_path, func_def.line
                    )
                    all_matches.append(
                        {
                            "type": "function",
                            "name": func_name,
                            "file_path": func_def.file_path,
                            "line_start": func_def.line,
                            "line_end": end_line,
                            "is_method": func_def.is_method,
                            "class_name": func_def.class_name,
                            "highlighted_name": regex.sub(
                                lambda m: f"[{m.group()}]", func_name
                            ),
                        }
                    )

        # Search classes if requested
        if (
            search_type in ["both", "classes"]
            and hasattr(self, "_treesitter_results")
            and self._treesitter_results
        ):
            for file_name, file_analysis in self._treesitter_results.get(
                "files", {}
            ).items():
                for cls in file_analysis.get("classes", []):
                    if regex.search(cls["name"]):
                        line_start = (
                            cls.get("range", {}).get("start", {}).get("line", "?")
                        )
                        line_end = cls.get("range", {}).get("end", {}).get("line", "?")
                        all_matches.append(
                            {
                                "type": "class",
                                "name": cls["name"],
                                "file_path": file_name,
                                "line_start": line_start,
                                "line_end": line_end,
                                "methods_count": len(cls.get("methods", [])),
                                "base_classes": cls.get("base_classes", []),
                                "highlighted_name": regex.sub(
                                    lambda m: f"[{m.group()}]", cls["name"]
                                ),
                            }
                        )

        if not all_matches:
            print(f"❌ No functions or classes match pattern '{pattern}'")
            print("💡 Try a simpler pattern or run analysis first")
            return

        print(
            f"🔍 Functions and Classes matching '{pattern}' ({len(all_matches)} found):"
        )
        print("=" * 50)

        # Group by file for better organization
        by_file = {}
        for match in all_matches:
            file_display = (
                match["file_path"]
                if self.show_full_paths
                else Path(match["file_path"]).name
            )
            if file_display not in by_file:
                by_file[file_display] = []
            by_file[file_display].append(match)

        shown_count = 0
        for file_display in sorted(by_file.keys()):
            if shown_count >= limit:
                break
            print(f"\n📄 {file_display}:")
            file_matches = sorted(by_file[file_display], key=lambda x: x["line_start"])
            for match in file_matches:
                if shown_count >= limit:
                    break

                if match["type"] == "function":
                    func_type = "Method" if match["is_method"] else "Function"
                    class_info = (
                        f" ({match['class_name']})" if match["class_name"] else ""
                    )
                    line_info = f"L{match['line_start']}"
                    if match["line_end"] and match["line_end"] != match["line_start"]:
                        line_info += f"-{match['line_end']}"
                    print(
                        f"   🔧 {match['highlighted_name']} ({line_info}) - {func_type}{class_info}"
                    )
                else:  # class
                    line_info = f"L{match['line_start']}"
                    if match["line_end"] and match["line_end"] != match["line_start"]:
                        line_info += f"-{match['line_end']}"
                    base_info = (
                        f" extends {', '.join(match['base_classes'])}"
                        if match["base_classes"]
                        else ""
                    )
                    print(
                        f"   🏗️  {match['highlighted_name']} ({line_info}) - {match['methods_count']} methods{base_info}"
                    )

                shown_count += 1

        if len(all_matches) > limit:
            print(f"\n... and {len(all_matches) - limit} more matches")
            print(f"💡 Use --preview to see method content")

    def _get_function_end_line(self, file_path: str, start_line: int) -> int:
        """Try to determine the end line of a function by parsing the source"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Simple heuristic: find the next function/class definition or end of file
            current_indent = None
            for i in range(start_line, len(lines)):
                line = lines[i].rstrip()
                if not line:
                    continue

                # Get indentation of the first non-empty line after function def
                if current_indent is None and not line.strip().endswith(":"):
                    current_indent = len(line) - len(line.lstrip())

                # If we find a line with same or less indentation that's not empty,
                # and it's not a decorator or comment, it's probably the end
                if current_indent is not None:
                    line_indent = len(line) - len(line.lstrip())
                    if (
                        line_indent <= current_indent
                        and line.strip()
                        and not line.strip().startswith("#")
                        and not line.strip().startswith("@")
                        and i > start_line + 1
                    ):  # Give some buffer
                        return i

            return len(lines)  # End of file
        except:
            return start_line

    def search_functions(self, pattern: str, limit: int = 50) -> None:
        """Search for functions matching a regex pattern (legacy method)"""
        return self.search_combined(pattern, limit, "functions")

    def search_classes(self, pattern: str, limit: int = 50) -> None:
        """Search for classes matching a regex pattern"""
        if not self.treesitter_analyzer or not hasattr(self, "_treesitter_results"):
            print("❌ No treesitter analysis results. Run --treesitter analysis first.")
            return

        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            print(f"❌ Invalid regex pattern '{pattern}': {e}")
            return

        # Find matching classes from treesitter results
        matches = []
        if hasattr(self, "_treesitter_results") and self._treesitter_results:
            for file_name, file_analysis in self._treesitter_results.get(
                "files", {}
            ).items():
                for cls in file_analysis.get("classes", []):
                    if regex.search(cls["name"]):
                        matches.append((cls, file_name))

        if not matches:
            print(f"❌ No classes match pattern '{pattern}'")
            print("💡 Try a simpler pattern or run analysis with --treesitter first")
            return

        print(f"🔍 Classes matching '{pattern}' ({len(matches)} found):")
        print("=" * 50)

        # Group by file
        by_file = {}
        for cls, file_name in matches:
            file_display = file_name if self.show_full_paths else Path(file_name).name
            if file_display not in by_file:
                by_file[file_display] = []
            by_file[file_display].append(cls)

        shown_count = 0
        for file_display in sorted(by_file.keys()):
            if shown_count >= limit:
                break
            print(f"\n📄 {file_display}:")
            file_classes = sorted(
                by_file[file_display],
                key=lambda x: x.get("range", {}).get("start", {}).get("line", 0),
            )
            for cls in file_classes:
                if shown_count >= limit:
                    break
                # Get line info, ensuring it's always present
                line_info = "L?"
                if (
                    cls.get("range")
                    and cls["range"].get("start")
                    and cls["range"]["start"].get("line")
                ):
                    line_info = f"L{cls['range']['start']['line']}"

                methods_count = len(cls.get("methods", []))
                base_classes = cls.get("base_classes", [])
                base_info = (
                    f" extends {', '.join(base_classes)}" if base_classes else ""
                )
                # Highlight the matching part
                highlighted_name = regex.sub(lambda m: f"[{m.group()}]", cls["name"])
                print(
                    f"   🏗️  {highlighted_name} ({line_info}) - {methods_count} methods{base_info}"
                )
                shown_count += 1

        if len(matches) > limit:
            print(f"\n... and {len(matches) - limit} more matches")

    def list_available_classes(self, limit: int = 20) -> None:
        """List available classes in the analyzed codebase"""
        if not hasattr(self, "_treesitter_results") or not self._treesitter_results:
            print("❌ No treesitter analysis results. Run --treesitter analysis first.")
            return

        # Count all classes
        all_classes = []
        for file_name, file_analysis in self._treesitter_results.get(
            "files", {}
        ).items():
            for cls in file_analysis.get("classes", []):
                all_classes.append((cls, file_name))

        if not all_classes:
            print("❌ No classes found in the analyzed code.")
            return

        total_count = len(all_classes)
        print(f"📋 Available Classes ({total_count} found):")
        print("=" * 50)

        # Group by file
        by_file = {}
        for cls, file_name in all_classes:
            file_display = file_name if self.show_full_paths else Path(file_name).name
            if file_display not in by_file:
                by_file[file_display] = []
            by_file[file_display].append(cls)

        shown_count = 0
        for file_display in sorted(by_file.keys()):
            if shown_count >= limit:
                break
            print(f"\n📄 {file_display}:")
            file_classes = sorted(
                by_file[file_display],
                key=lambda x: x.get("range", {}).get("start", {}).get("line", 0),
            )
            for cls in file_classes:
                if shown_count >= limit:
                    break
                # Get line info, ensuring it's always present
                line_info = "L?"
                if (
                    cls.get("range")
                    and cls["range"].get("start")
                    and cls["range"]["start"].get("line")
                ):
                    line_info = f"L{cls['range']['start']['line']}"

                methods_count = len(cls.get("methods", []))
                base_classes = cls.get("base_classes", [])
                base_info = (
                    f" extends {', '.join(base_classes)}" if base_classes else ""
                )
                print(
                    f"   🏗️  {cls['name']} ({line_info}) - {methods_count} methods{base_info}"
                )
                shown_count += 1

        if total_count > limit:
            print(f"\n... and {total_count - limit} more classes")
            print(f"💡 Use --search-classes <pattern> to search for specific classes")

    def _print_detailed_treesitter(self, files_data: dict, max_files: int = 10):
        """Print detailed tree-sitter analysis results"""
        shown_files = 0
        for file_name, file_analysis in sorted(files_data.items()):
            if shown_files >= max_files:
                print(f"\n... and {len(files_data) - max_files} more files")
                print("💡 Use --export json to see all results")
                break

            print(f"\n📄 {file_name}:")

            # Classes
            if file_analysis.get("classes"):
                print(f"  🏗️  Classes ({len(file_analysis['classes'])}):")
                for cls in file_analysis["classes"][:5]:  # Limit to 5 per file
                    # Get line info, ensuring it's always present
                    line_info = "L?"
                    if (
                        cls.get("range")
                        and cls["range"].get("start")
                        and cls["range"]["start"].get("line")
                    ):
                        line_info = f"L{cls['range']['start']['line']}"

                    methods_count = len(cls.get("methods", []))
                    base_classes = cls.get("base_classes", [])
                    base_info = (
                        f" extends {', '.join(base_classes)}" if base_classes else ""
                    )
                    print(
                        f"     🏗️  {cls['name']} ({line_info}) - {methods_count} methods{base_info}"
                    )

            # Functions
            if file_analysis.get("functions"):
                print(f"  🔧 Functions ({len(file_analysis['functions'])}):")
                for func in file_analysis["functions"][:10]:  # Limit to 10 per file
                    # Get line info, ensuring it's always present
                    line_info = "L?"
                    if (
                        func.get("range")
                        and func["range"].get("start")
                        and func["range"]["start"].get("line")
                    ):
                        line_info = f"L{func['range']['start']['line']}"

                    params_count = len(func.get("parameters", []))
                    complexity = func.get("complexity", "N/A")
                    print(
                        f"     🔧 {func['name']}({params_count}) ({line_info}) - complexity: {complexity}"
                    )

            # Imports
            if file_analysis.get("imports"):
                print(f"  📥 Imports ({len(file_analysis['imports'])}):")
                for imp in file_analysis["imports"][:5]:  # Limit to 5 per file
                    imp_type = imp.get("type", "import")
                    module = imp.get("module", "unknown")
                    print(f"     📥 {imp_type} {module}")

            shown_files += 1

    def _print_detailed_callgraph(self, callgraph_data: dict, max_functions: int = 20):
        """Print detailed call graph analysis results"""
        functions = callgraph_data.get("functions", {})
        call_graph = callgraph_data.get("call_graph", {})

        print(f"🔧 Top Functions by Call Count:")
        # Sort functions by how many times they're called
        function_call_counts = []
        reverse_calls = callgraph_data.get("reverse_call_graph", {})

        for func_name, func_info in functions.items():
            call_count = len(reverse_calls.get(func_name, []))
            function_call_counts.append((func_name, func_info, call_count))

        function_call_counts.sort(key=lambda x: x[2], reverse=True)

        shown_count = 0
        for func_name, func_info, call_count in function_call_counts:
            if shown_count >= max_functions:
                print(f"\n... and {len(functions) - max_functions} more functions")
                break

            func_type = "Method" if func_info.get("is_method") else "Function"
            class_info = (
                f" ({func_info['class_name']})" if func_info.get("class_name") else ""
            )
            calls_out = len(call_graph.get(func_name, []))

            file_display = (
                func_info["file"]
                if self.show_full_paths
                else Path(func_info["file"]).name
            )
            print(f"  🔧 {func_name} ({file_display}:L{func_info['line']})")
            print(f"     Type: {func_type}{class_info}")
            print(
                f"     Called by: {call_count} functions, Calls: {calls_out} functions"
            )
            shown_count += 1

    def export_results(
        self,
        results: AnalysisResults,
        formats: List[str],
        output_prefix: str = "analysis",
    ):
        """Export results in various formats"""
        for format_type in formats:
            if format_type.lower() == "json":
                self._export_json(results, f"{output_prefix}.json")
            elif format_type.lower() == "dot" and results.callgraph_results:
                self._export_dot(f"{output_prefix}.dot")
            else:
                self._log(f"⚠️  Unknown export format: {format_type}")

    def _export_json(self, results: AnalysisResults, filename: str):
        """Export results as JSON"""
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(asdict(results), f, indent=2, default=str)
            print(f"📄 Results exported to: {filename}")
        except Exception as e:
            print(f"❌ Failed to export JSON: {e}")

    def _export_dot(self, filename: str):
        """Export call graph as DOT file"""
        if self.callgraph_analyzer:
            try:
                self.callgraph_analyzer.export_dot_graph(filename)
                print(f"🔗 Call graph exported to: {filename}")
            except Exception as e:
                print(f"❌ Failed to export DOT: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Combined Python Code Analyzer (Tree-sitter + Call Graph)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python combined_cli_analyzer.py                                    # Run both analyses
    python combined_cli_analyzer.py --treesitter                       # Tree-sitter only
    python combined_cli_analyzer.py --callgraph                        # Call graph only
    python combined_cli_analyzer.py --function main --verbose          # Analyze main function
    python combined_cli_analyzer.py --export json,dot                  # Export results
    python combined_cli_analyzer.py --exclude-preset dev               # Exclude dev files
    python combined_cli_analyzer.py --exclude "test*" "__pycache__"    # Custom exclusions
    python combined_cli_analyzer.py --search "async.*"                 # Search functions & classes
    python combined_cli_analyzer.py --search-functions "handle.*"      # Search functions only
    python combined_cli_analyzer.py --search-classes ".*Manager$"      # Search classes only
    python combined_cli_analyzer.py --preview "main"                   # Preview method content
    python combined_cli_analyzer.py --preview "main.py:25-50"          # Preview specific lines
        """,
    )

    # Analysis options
    analysis_group = parser.add_mutually_exclusive_group()
    analysis_group.add_argument(
        "--treesitter", action="store_true", help="Run Tree-sitter analysis only"
    )
    analysis_group.add_argument(
        "--callgraph", action="store_true", help="Run Call Graph analysis only"
    )
    analysis_group.add_argument(
        "--both", action="store_true", default=True, help="Run both analyses (default)"
    )

    # Directory and file options
    parser.add_argument(
        "--directory", "-d", default=".", help="Directory to analyze (default: current)"
    )
    parser.add_argument(
        "--recursive",
        "-r",
        action="store_true",
        default=True,
        help="Analyze directories recursively (default: True)",
    )
    parser.add_argument(
        "--non-recursive",
        action="store_true",
        help="Analyze only the specified directory",
    )
    parser.add_argument(
        "--exclude",
        nargs="+",
        help="Exclude files/directories matching these glob patterns. Examples: 'test*' (starts with test), '.git' (hidden dirs), '*/build/*' (build dirs anywhere), '__pycache__' (cache dirs), '*.pyc' (compiled files)",
    )
    parser.add_argument(
        "--exclude-dirs",
        nargs="+",
        help="Legacy: same as --exclude (deprecated, use --exclude instead)",
    )
    parser.add_argument(
        "--exclude-preset",
        choices=["dev", "minimal", "comprehensive", "library"],
        help="Use predefined exclusion patterns: 'minimal' (cache/git), 'dev' (tests/cache/git), 'comprehensive' (all dev files), 'library' (package dev files)",
    )
    parser.add_argument(
        "--short-paths",
        action="store_true",
        help="Show only filenames instead of complete paths",
    )

    # Function-specific analysis
    parser.add_argument(
        "--function",
        "-f",
        nargs="?",
        const="",
        help="Analyze specific function or list all functions if no name given",
    )
    parser.add_argument(
        "--module", "-m", help="Analyze specific module (requires --callgraph)"
    )
    parser.add_argument(
        "--list-functions",
        action="store_true",
        help="List all available functions (same as --function without argument)",
    )
    parser.add_argument(
        "--search",
        help="Search both functions and classes using regex pattern",
    )
    parser.add_argument(
        "--search-functions",
        help="Search functions using regex pattern (requires --callgraph)",
    )
    parser.add_argument(
        "--search-classes",
        help="Search classes using regex pattern (requires --treesitter)",
    )
    parser.add_argument(
        "--preview",
        help="Preview method/function content by name or 'filename:start-end'",
    )
    parser.add_argument(
        "--list-classes",
        action="store_true",
        help="List all available classes (requires --treesitter)",
    )

    # Output options
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose/debug output"
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true", help="Suppress summary output"
    )
    parser.add_argument(
        "--detailed", action="store_true", help="Show detailed analysis results"
    )
    parser.add_argument("--export", help="Export formats (comma-separated): json,dot")
    parser.add_argument(
        "--output-prefix", default="analysis", help="Prefix for output files"
    )

    args = parser.parse_args()

    # Handle mutually exclusive options
    if args.non_recursive:
        args.recursive = False

    # Determine which analyses to run
    run_treesitter = args.treesitter or args.both
    run_callgraph = args.callgraph or args.both

    # If user explicitly chose one analysis, disable the other
    if args.treesitter:
        run_callgraph = False
        args.both = False
    elif args.callgraph:
        run_treesitter = False
        args.both = False

    print("🔬 Combined Python Code Analyzer")
    print("=" * 50)

    # Combine exclude patterns from all sources
    exclude_patterns = []
    if args.exclude:
        exclude_patterns.extend(args.exclude)
    if args.exclude_dirs:
        exclude_patterns.extend(args.exclude_dirs)

    # Add preset patterns
    if args.exclude_preset:
        preset_patterns = get_exclusion_preset(args.exclude_preset)
        exclude_patterns.extend(preset_patterns)
        if args.verbose:
            print(f"📋 Using '{args.exclude_preset}' preset: {preset_patterns}")

    # Initialize analyzer
    analyzer = CombinedAnalyzer(
        verbose=args.verbose,
        show_full_paths=not args.short_paths,  # Full paths by default, short if flag set
        exclude_patterns=exclude_patterns,
    )

    # Function-specific analysis
    # Combined search functionality
    if args.search:
        print(f"🔍 Searching functions and classes with pattern: {args.search}")
        # Need both analyzers for combined search
        results = analyzer.analyze_directory(
            args.directory, args.recursive, run_treesitter=True, run_callgraph=True
        )
        if results.errors:
            print("❌ Analysis failed:")
            for error in results.errors:
                print(f"   {error}")
            return 1
        analyzer.search_combined(args.search)
        return 0

    if args.function is not None or args.list_functions or args.search_functions:
        if not run_callgraph:
            # Automatically enable call graph for function analysis
            print("💡 Function analysis requires call graph - enabling automatically")
            run_callgraph = True
            run_treesitter = False

        # Need to run call graph analysis first
        if args.function == "":
            print("📋 Listing available functions...")
        elif args.search_functions:
            print(f"🔍 Searching functions with pattern: {args.search_functions}")
        else:
            print(f"🔍 Analyzing function: {args.function}")

        results = analyzer.analyze_directory(
            args.directory, args.recursive, run_treesitter=False, run_callgraph=True
        )
        if results.errors:
            print("❌ Analysis failed:")
            for error in results.errors:
                print(f"   {error}")
            return 1

        # Handle function analysis, listing, or search
        if args.function == "" or args.list_functions:
            analyzer.analyze_function(None)  # List functions
        elif args.search_functions:
            analyzer.search_functions(args.search_functions)
        else:
            analyzer.analyze_function(args.function)
        return 0

    # Class-specific analysis
    if args.list_classes or args.search_classes:
        if not run_treesitter:
            # Automatically enable treesitter for class analysis
            print("💡 Class analysis requires treesitter - enabling automatically")
            run_treesitter = True
            run_callgraph = False

        if args.search_classes:
            print(f"🔍 Searching classes with pattern: {args.search_classes}")
        else:
            print("📋 Listing available classes...")

        results = analyzer.analyze_directory(
            args.directory, args.recursive, run_treesitter=True, run_callgraph=False
        )
        if results.errors:
            print("❌ Analysis failed:")
            for error in results.errors:
                print(f"   {error}")
            return 1

        # Handle class listing or search
        if args.search_classes:
            analyzer.search_classes(args.search_classes)
        else:
            analyzer.list_available_classes()
        return 0

    # Method/function preview functionality
    if args.preview:
        print(f"📖 Previewing: {args.preview}")
        # Need both analyzers for comprehensive preview
        results = analyzer.analyze_directory(
            args.directory, args.recursive, run_treesitter=True, run_callgraph=True
        )
        if results.errors:
            print("❌ Analysis failed:")
            for error in results.errors:
                print(f"   {error}")
            return 1
        analyzer.preview_method(args.preview)
        return 0

    # Full directory analysis
    results = analyzer.analyze_directory(
        args.directory, args.recursive, run_treesitter, run_callgraph
    )

    # Print summary unless quiet mode
    if not args.quiet:
        analyzer.print_summary(results, detailed=args.detailed)

    # Export results if requested
    if args.export:
        formats = [f.strip() for f in args.export.split(",")]
        analyzer.export_results(results, formats, args.output_prefix)

    # Module-specific analysis (for call graph)
    if args.module and run_callgraph:
        if analyzer.callgraph_analyzer:
            analyzer.callgraph_analyzer.print_module_details(args.module)

    # Return error code if there were errors
    return 1 if results.errors else 0


if __name__ == "__main__":
    sys.exit(main())
