#!/usr/bin/env python3
"""
Call Graph Analyzer using Tree-sitter

This script analyzes Python files to build call graphs, find module references,
and track function/method dependencies using Tree-sitter parsing.

Features:
- Find all module imports and their usage locations
- Build call graphs showing function dependencies
- Track method calls within classes
- Find references to external modules
- Export call graphs in various formats

Installation:
    pip install tree-sitter tree-sitter-python

Usage:
    python call_graph_analyzer.py
    python call_graph_analyzer.py --module requests
    python call_graph_analyzer.py --function main --export-dot
"""

import os
import json
import argparse
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict

try:
    import tree_sitter_python as tspython
    from tree_sitter import Language, Parser, Query

    TREE_SITTER_AVAILABLE = True
except ImportError:
    print(
        "❌ Tree-sitter not installed. Run: pip install tree-sitter tree-sitter-python"
    )
    exit(1)


@dataclass
class Reference:
    """A reference to a function, method, or module"""

    name: str
    file_path: str
    line: int
    column: int
    context: str  # The line of code containing the reference
    reference_type: str  # 'call', 'import', 'attribute'


@dataclass
class FunctionDef:
    """A function or method definition"""

    name: str
    file_path: str
    line: int
    is_method: bool = False
    class_name: Optional[str] = None
    parameters: List[str] = field(default_factory=list)
    calls: List[Reference] = field(default_factory=list)  # Functions this calls


@dataclass
class ModuleInfo:
    """Information about a module and its usage"""

    name: str
    import_locations: List[Reference] = field(default_factory=list)
    usage_locations: List[Reference] = field(default_factory=list)
    imported_names: Set[str] = field(default_factory=set)


class CallGraphAnalyzer:
    """Analyzes Python code to build call graphs using Tree-sitter"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

        # Initialize Tree-sitter
        try:
            self.language = Language(tspython.language())
            self.parser = Parser()
            self.parser.language = self.language
        except Exception as e:
            print(f"❌ Failed to initialize Tree-sitter: {e}")
            raise

        # Data structures
        self.functions: Dict[str, FunctionDef] = {}  # function_name -> FunctionDef
        self.modules: Dict[str, ModuleInfo] = {}  # module_name -> ModuleInfo
        self.call_graph: Dict[str, Set[str]] = defaultdict(set)  # caller -> {callees}
        self.reverse_call_graph: Dict[str, Set[str]] = defaultdict(
            set
        )  # callee -> {callers}

        # Initialize queries
        self.queries = self._init_queries()

    def _log(self, message: str, force: bool = False):
        """Log message if verbose mode is enabled or force is True"""
        if self.verbose or force:
            print(message)

    def _init_queries(self) -> Dict[str, Query]:
        """Initialize Tree-sitter queries with proper error handling"""
        queries = {}

        # Function definitions with fallbacks
        try:
            self._log("   Initializing function query...")
            queries["functions"] = Query(
                self.language,
                """
                (function_definition
                    name: (identifier) @func_name
                    parameters: (parameters) @func_params
                    body: (block) @func_body
                ) @func_def
                """,
            )
            self._log("   ✅ Complex function query initialized")
        except Exception as e:
            self._log(f"   ❌ Complex function query failed: {e}")
            try:
                queries["functions"] = Query(
                    self.language, "(function_definition) @func_def"
                )
                self._log("   ✅ Using simplified function query")
            except Exception as e2:
                self._log(f"   ❌ Even simple function query failed: {e2}")

        # Function calls with fallbacks
        try:
            queries["calls"] = Query(self.language, "(call) @call_expr")
            self._log("   ✅ Call query initialized")
        except Exception as e:
            self._log(f"   ❌ Call query failed: {e}")

        # Import statements with fallbacks
        try:
            queries["imports"] = Query(self.language, "(import_statement) @import")
            queries["from_imports"] = Query(
                self.language, "(import_from_statement) @from_import"
            )
            queries["module_access"] = Query(self.language, "(attribute) @module_attr")
            self._log("   ✅ Import queries initialized")
        except Exception as e:
            self._log(f"   ❌ Import queries failed: {e}")

        self._log(f"   📊 Total queries initialized: {len(queries)}")
        return queries

    def _get_node_text(self, node, source_bytes: bytes) -> str:
        """Extract text from Tree-sitter node"""
        return source_bytes[node.start_byte : node.end_byte].decode(
            "utf-8", errors="replace"
        )

    def _get_line_context(self, node, source_bytes: bytes) -> str:
        """Get the full line containing the node"""
        source_text = source_bytes.decode("utf-8", errors="replace")
        lines = source_text.split("\n")
        line_num = node.start_point[0]
        if line_num < len(lines):
            return lines[line_num].strip()
        return ""

    def analyze_file(self, file_path: str) -> None:
        """Analyze a single Python file"""
        try:
            with open(file_path, "rb") as f:
                source_bytes = f.read()

            tree = self.parser.parse(source_bytes)
            root_node = tree.root_node

            # Analyze different constructs
            self._analyze_functions(root_node, source_bytes, file_path)
            self._analyze_calls(root_node, source_bytes, file_path)
            self._analyze_imports(root_node, source_bytes, file_path)
            self._analyze_module_usage(root_node, source_bytes, file_path)

        except Exception as e:
            print(f"❌ Error analyzing {file_path}: {e}")

    def _traverse_for_functions(self, node, captures, source_bytes):
        """Fallback method to find functions by traversing nodes"""
        if node.type == "function_definition":
            captures.append((node, "func_def"))
        for child in node.children:
            self._traverse_for_functions(child, captures, source_bytes)

    def _traverse_for_calls(self, node, captures, source_bytes):
        """Fallback method to find function calls by traversing nodes"""
        if node.type == "call":
            captures.append((node, "call_expr"))
        for child in node.children:
            self._traverse_for_calls(child, captures, source_bytes)

    def _traverse_for_imports(self, node, captures, source_bytes):
        """Fallback method to find imports by traversing nodes"""
        if node.type == "import_statement":
            captures.append((node, "import"))
        elif node.type == "import_from_statement":
            captures.append((node, "from_import"))
        for child in node.children:
            self._traverse_for_imports(child, captures, source_bytes)

    def _traverse_for_attributes(self, node, captures, source_bytes):
        """Fallback method to find attribute access by traversing nodes"""
        if node.type == "attribute":
            captures.append((node, "module_attr"))
        for child in node.children:
            self._traverse_for_attributes(child, captures, source_bytes)

    def _analyze_functions(self, root_node, source_bytes: bytes, file_path: str):
        """Find all function and method definitions"""
        self._log(f"   🔍 Debug: Analyzing functions in {Path(file_path).name}")
        try:
            if hasattr(self.queries["functions"], "captures"):
                captures = self.queries["functions"].captures(root_node)
                self._log(
                    f"   🔍 Debug: Found {len(captures)} captures using .captures()"
                )
            elif hasattr(self.queries["functions"], "matches"):
                captures = []
                for match in self.queries["functions"].matches(root_node):
                    for capture in match[1]:
                        captures.append((capture[0], capture[1]))
                self._log(
                    f"   🔍 Debug: Found {len(captures)} captures using .matches()"
                )
            else:
                # Fallback - traverse nodes manually
                captures = []
                self._traverse_for_functions(root_node, captures, source_bytes)
                self._log(
                    f"   🔍 Debug: Found {len(captures)} captures using fallback traversal"
                )
        except Exception as e:
            self._log(f"   ❌ Debug: Exception in query execution: {e}")
            # Use fallback method
            captures = []
            self._traverse_for_functions(root_node, captures, source_bytes)
            self._log(
                f"   🔍 Debug: Found {len(captures)} captures using fallback after exception"
            )

        self._log(f"   🔍 Debug: Processing {len(captures)} captures")
        for node, name in captures:
            self._log(f"   🔍 Debug: Processing node type: {node.type}")
            if node.type == "function_definition":
                # Get function name
                name_node = node.child_by_field_name("name")
                if not name_node:
                    self._log(f"   ⚠️ Debug: No name node found for function")
                    continue

                func_name = self._get_node_text(name_node, source_bytes)
                line_num = node.start_point[0] + 1
                self._log(
                    f"   ✅ Debug: Found function '{func_name}' at line {line_num}"
                )

                # Check if it's inside a class (method)
                parent = node.parent
                class_name = None
                is_method = False

                while parent:
                    if parent.type == "class_definition":
                        is_method = True
                        # Find class name
                        class_name_node = parent.child_by_field_name("name")
                        if class_name_node:
                            class_name = self._get_node_text(
                                class_name_node, source_bytes
                            )
                        break
                    parent = parent.parent

                full_name = f"{class_name}.{func_name}" if class_name else func_name
                self._log(f"   📝 Debug: Storing function as '{full_name}'")

                self.functions[full_name] = FunctionDef(
                    name=func_name,
                    file_path=file_path,
                    line=line_num,
                    is_method=is_method,
                    class_name=class_name,
                )
            else:
                self._log(
                    f"   ⚠️ Debug: Skipping node type '{node.type}' (expected 'function_definition')"
                )

    def _analyze_calls(self, root_node, source_bytes: bytes, file_path: str):
        """Find all function calls"""
        try:
            if hasattr(self.queries["calls"], "captures"):
                captures = self.queries["calls"].captures(root_node)
            elif hasattr(self.queries["calls"], "matches"):
                captures = []
                for match in self.queries["calls"].matches(root_node):
                    for capture in match[1]:
                        captures.append((capture[0], capture[1]))
            else:
                # Fallback - traverse nodes manually
                captures = []
                self._traverse_for_calls(root_node, captures, source_bytes)
        except Exception:
            # Use fallback method
            captures = []
            self._traverse_for_calls(root_node, captures, source_bytes)

        for node, name in captures:
            if node.type == "call":
                line_num = node.start_point[0] + 1
                context = self._get_line_context(node, source_bytes)

                # Get function being called
                func_node = node.child_by_field_name("function")
                if not func_node:
                    continue

                call_name = None
                reference_type = "call"

                if func_node.type == "identifier":
                    # Simple call: func()
                    call_name = self._get_node_text(func_node, source_bytes)
                elif func_node.type == "attribute":
                    # Attribute call: obj.method()
                    obj_node = func_node.child_by_field_name("object")
                    attr_node = func_node.child_by_field_name("attribute")
                    if obj_node and attr_node:
                        obj_name = self._get_node_text(obj_node, source_bytes)
                        method_name = self._get_node_text(attr_node, source_bytes)
                        call_name = f"{obj_name}.{method_name}"
                        reference_type = "attribute"

                if call_name:
                    ref = Reference(
                        name=call_name,
                        file_path=file_path,
                        line=line_num,
                        column=node.start_point[1],
                        context=context,
                        reference_type=reference_type,
                    )

                    # Find the containing function
                    caller = self._find_containing_function(node, source_bytes)
                    if caller:
                        if caller not in self.functions:
                            # Create function entry if it doesn't exist
                            self.functions[caller] = FunctionDef(
                                name=caller.split(".")[-1], file_path=file_path, line=0
                            )
                        self.functions[caller].calls.append(ref)
                        self.call_graph[caller].add(call_name)
                        self.reverse_call_graph[call_name].add(caller)

    def _analyze_imports(self, root_node, source_bytes: bytes, file_path: str):
        """Find all import statements"""
        # Regular imports: import module
        try:
            if hasattr(self.queries["imports"], "captures"):
                captures = self.queries["imports"].captures(root_node)
            elif hasattr(self.queries["imports"], "matches"):
                captures = []
                for match in self.queries["imports"].matches(root_node):
                    for capture in match[1]:
                        captures.append((capture[0], capture[1]))
            else:
                # Fallback - traverse nodes manually
                captures = []
                self._traverse_for_imports(root_node, captures, source_bytes)
        except Exception:
            # Use fallback method
            captures = []
            self._traverse_for_imports(root_node, captures, source_bytes)

        for node, name in captures:
            if node.type == "import_statement":
                # Find module name
                for child in node.children:
                    if child.type == "dotted_name":
                        module_name = self._get_node_text(child, source_bytes)
                        line_num = node.start_point[0] + 1
                        context = self._get_line_context(node, source_bytes)

                        if module_name not in self.modules:
                            self.modules[module_name] = ModuleInfo(name=module_name)

                        ref = Reference(
                            name=module_name,
                            file_path=file_path,
                            line=line_num,
                            column=node.start_point[1],
                            context=context,
                            reference_type="import",
                        )

                        self.modules[module_name].import_locations.append(ref)

        # From imports: from module import name
        try:
            if hasattr(self.queries["from_imports"], "captures"):
                captures = self.queries["from_imports"].captures(root_node)
            elif hasattr(self.queries["from_imports"], "matches"):
                captures = []
                for match in self.queries["from_imports"].matches(root_node):
                    for capture in match[1]:
                        captures.append((capture[0], capture[1]))
            else:
                # Fallback - traverse nodes manually
                captures = []
                self._traverse_for_imports(root_node, captures, source_bytes)
        except Exception:
            # Use fallback method
            captures = []
            self._traverse_for_imports(root_node, captures, source_bytes)

        for node, name in captures:
            if node.type == "import_from_statement":
                # Find module name
                module_node = node.child_by_field_name("module_name")
                if module_node:
                    module_name = self._get_node_text(module_node, source_bytes)
                    line_num = node.start_point[0] + 1
                    context = self._get_line_context(node, source_bytes)

                    if module_name not in self.modules:
                        self.modules[module_name] = ModuleInfo(name=module_name)

                    ref = Reference(
                        name=module_name,
                        file_path=file_path,
                        line=line_num,
                        column=node.start_point[1],
                        context=context,
                        reference_type="import",
                    )

                    self.modules[module_name].import_locations.append(ref)

    def _analyze_module_usage(self, root_node, source_bytes: bytes, file_path: str):
        """Find usage of imported modules"""
        """Find module usage (attribute access)"""
        try:
            if hasattr(self.queries["module_access"], "captures"):
                captures = self.queries["module_access"].captures(root_node)
            elif hasattr(self.queries["module_access"], "matches"):
                captures = []
                for match in self.queries["module_access"].matches(root_node):
                    for capture in match[1]:
                        captures.append((capture[0], capture[1]))
            else:
                # Fallback - traverse nodes manually
                captures = []
                self._traverse_for_attributes(root_node, captures, source_bytes)
        except Exception:
            # Use fallback method
            captures = []
            self._traverse_for_attributes(root_node, captures, source_bytes)

        for node, name in captures:
            if node.type == "attribute":
                # Get object name (potential module name)
                obj_node = node.child_by_field_name("object")
                if obj_node and obj_node.type == "identifier":
                    module_name = self._get_node_text(obj_node, source_bytes)

                    # Check if this is a known imported module
                    if module_name in self.modules:
                        line_num = node.start_point[0] + 1
                        context = self._get_line_context(node, source_bytes)

                        ref = Reference(
                            name=module_name,
                            file_path=file_path,
                            line=line_num,
                            column=node.start_point[1],
                            context=context,
                            reference_type="usage",
                        )

                        self.modules[module_name].usage_locations.append(ref)

    def _find_containing_function(self, node, source_bytes: bytes) -> Optional[str]:
        """Find the function that contains this node"""
        parent = node.parent
        while parent:
            if parent.type == "function_definition":
                name_node = parent.child_by_field_name("name")
                if name_node:
                    func_name = self._get_node_text(name_node, source_bytes)

                    # Check if it's a method (inside a class)
                    class_parent = parent.parent
                    while class_parent:
                        if class_parent.type == "class_definition":
                            class_name_node = class_parent.child_by_field_name("name")
                            if class_name_node:
                                class_name = self._get_node_text(
                                    class_name_node, source_bytes
                                )
                                return f"{class_name}.{func_name}"
                            break
                        class_parent = class_parent.parent

                    return func_name
            parent = parent.parent
        return None

    def analyze_directory(self, directory: str, recursive: bool = True) -> None:
        """Analyze all Python files in a directory"""
        path = Path(directory)
        if recursive:
            python_files = list(path.rglob("*.py"))
        else:
            python_files = list(path.glob("*.py"))

        self._log(f"🔍 Found {len(python_files)} Python files", force=True)
        for file_path in python_files:
            self._log(f"   Analyzing {file_path.name}...")
            self.analyze_file(str(file_path))

    def find_module_references(self, module_name: str) -> Optional[ModuleInfo]:
        """Find all references to a specific module"""
        return self.modules.get(module_name)

    def find_function_callers(self, function_name: str) -> Set[str]:
        """Find all functions that call the given function"""
        return self.reverse_call_graph.get(function_name, set())

    def find_function_callees(self, function_name: str) -> Set[str]:
        """Find all functions called by the given function"""
        return self.call_graph.get(function_name, set())

    def get_call_chain(self, start_function: str, max_depth: int = 5) -> Dict[str, Any]:
        """Get the call chain starting from a function"""
        visited = set()

        def traverse(func_name: str, depth: int) -> Dict[str, Any]:
            if depth >= max_depth or func_name in visited:
                return {"name": func_name, "calls": []}

            visited.add(func_name)
            calls = []

            for callee in self.call_graph.get(func_name, []):
                calls.append(traverse(callee, depth + 1))

            return {"name": func_name, "calls": calls}

        return traverse(start_function, 0)

    def export_dot_graph(self, output_file: str, max_functions: int = 50):
        """Export call graph as DOT format for Graphviz"""
        with open(output_file, "w") as f:
            f.write("digraph CallGraph {\n")
            f.write("  rankdir=TB;\n")
            f.write("  node [shape=box, style=rounded];\n\n")

            # Limit to most connected functions
            function_scores = {}
            for func in self.functions.keys():
                score = len(self.call_graph.get(func, [])) + len(
                    self.reverse_call_graph.get(func, [])
                )
                function_scores[func] = score

            top_functions = sorted(
                function_scores.items(), key=lambda x: x[1], reverse=True
            )[:max_functions]
            top_function_names = {func[0] for func in top_functions}

            # Add nodes
            for func_name, _ in top_functions:
                func_def = self.functions.get(func_name)
                if func_def:
                    label = f"{func_name}\\n({Path(func_def.file_path).name}:{func_def.line})"
                    color = "lightblue" if func_def.is_method else "lightgreen"
                    f.write(
                        f'  "{func_name}" [label="{label}", fillcolor={color}, style=filled];\n'
                    )

            f.write("\n")

            # Add edges
            for caller in top_function_names:
                for callee in self.call_graph.get(caller, []):
                    if callee in top_function_names:
                        f.write(f'  "{caller}" -> "{callee}";\n')

            f.write("}\n")

        print(f"📊 DOT graph exported to {output_file}")
        print(f"Generate image with: dot -Tpng {output_file} -o callgraph.png")

    def print_summary(self):
        """Print analysis summary"""
        print(f"\n📊 CALL GRAPH ANALYSIS SUMMARY")
        print(f"{'=' * 50}")
        print(f"📁 Functions found: {len(self.functions)}")
        print(f"📦 Modules imported: {len(self.modules)}")
        print(
            f"🔗 Call relationships: {sum(len(callees) for callees in self.call_graph.values())}"
        )

        # Most imported modules
        if self.modules:
            print(f"\n📦 Most Used Modules:")
            module_usage = [
                (name, len(info.usage_locations)) for name, info in self.modules.items()
            ]
            module_usage.sort(key=lambda x: x[1], reverse=True)

            for module_name, usage_count in module_usage[:10]:
                import_count = len(self.modules[module_name].import_locations)
                print(f"   {module_name}: {usage_count} uses, {import_count} imports")

        # Most called functions
        if self.reverse_call_graph:
            print(f"\n🔧 Most Called Functions:")
            function_calls = [
                (name, len(callers))
                for name, callers in self.reverse_call_graph.items()
            ]
            function_calls.sort(key=lambda x: x[1], reverse=True)

            for func_name, call_count in function_calls[:10]:
                print(f"   {func_name}: called {call_count} times")

    def print_module_details(self, module_name: str):
        """Print detailed information about a module"""
        module_info = self.find_module_references(module_name)
        if not module_info:
            print(f"❌ Module '{module_name}' not found")
            return

        print(f"\n📦 MODULE: {module_name}")
        print(f"{'=' * 50}")
        print(f"Import locations: {len(module_info.import_locations)}")
        print(f"Usage locations: {len(module_info.usage_locations)}")
        print(
            f"Imported names: {', '.join(module_info.imported_names) if module_info.imported_names else 'None'}"
        )

        print(f"\n📍 Import Locations:")
        for ref in module_info.import_locations:
            print(f"   {Path(ref.file_path).name}:{ref.line} - {ref.context}")

        if module_info.usage_locations:
            print(f"\n🔍 Usage Locations:")
            for ref in module_info.usage_locations[:20]:  # Limit to 20 for readability
                print(f"   {Path(ref.file_path).name}:{ref.line} - {ref.context}")

            if len(module_info.usage_locations) > 20:
                print(f"   ... and {len(module_info.usage_locations) - 20} more")

    def print_function_details(self, function_name: str):
        """Print detailed information about a function"""
        self._log(f"🔍 Debug: Looking for function '{function_name}'")
        self._log(
            f"🔍 Debug: Available functions ({len(self.functions)}): {list(self.functions.keys())[:20]}{'...' if len(self.functions) > 20 else ''}"
        )

        # Find all functions that match the search term
        exact_matches = [
            name for name in self.functions.keys() if name == function_name
        ]
        partial_matches = [
            name
            for name in self.functions.keys()
            if function_name in name and name != function_name
        ]

        all_matches = exact_matches + partial_matches

        if not all_matches:
            print(f"❌ Function '{function_name}' not found")
            # Suggest similar functions
            suggestions = [
                name
                for name in self.functions.keys()
                if function_name.lower() in name.lower()
            ]
            if suggestions:
                print(f"💡 Did you mean one of these? {suggestions[:5]}")
            return

        print(
            f"🔍 Found {len(all_matches)} function(s) matching '{function_name}':",
            flush=True,
        )

        for i, match in enumerate(all_matches, 1):
            func_def = self.functions[match]
            callers = self.find_function_callers(match)
            callees = self.find_function_callees(match)

            print(f"\n🔧 FUNCTION {i}: {match}")
            print(f"{'=' * 50}")
            print(f"File: {Path(func_def.file_path).name}:{func_def.line}")
            print(f"Type: {'Method' if func_def.is_method else 'Function'}")
            if func_def.class_name:
                print(f"Class: {func_def.class_name}")

            print(f"\n📞 Called by ({len(callers)}):")
            for caller in sorted(callers)[:10]:  # Limit to first 10
                if caller in self.functions:
                    caller_def = self.functions[caller]
                    print(
                        f"   {caller} ({Path(caller_def.file_path).name}:{caller_def.line})"
                    )
                else:
                    print(f"   {caller}")
            if len(callers) > 10:
                print(f"   ... and {len(callers) - 10} more")

            print(f"\n🔗 Calls ({len(callees)}):")
            for callee in sorted(callees)[:10]:  # Limit to first 10
                if callee in self.functions:
                    callee_def = self.functions[callee]
                    print(
                        f"   {callee} ({Path(callee_def.file_path).name}:{callee_def.line})"
                    )
                else:
                    print(f"   {callee} (external or unresolved)")
            if len(callees) > 10:
                print(f"   ... and {len(callees) - 10} more")

            if i < len(all_matches):  # Add separator between functions
                print("\n" + "-" * 50)


def main():
    parser = argparse.ArgumentParser(
        description="Call Graph Analyzer using Tree-sitter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python call_graph_analyzer.py                    # Analyze current directory
    python call_graph_analyzer.py --recursive        # Analyze recursively
    python call_graph_analyzer.py --module requests  # Find all requests usage
    python call_graph_analyzer.py --function main    # Analyze main function
    python call_graph_analyzer.py --export-dot       # Export DOT graph
    python call_graph_analyzer.py --verbose          # Enable debug output
        """,
    )

    parser.add_argument("--directory", "-d", default=".", help="Directory to analyze")
    parser.add_argument(
        "--recursive", "-r", action="store_true", help="Analyze recursively"
    )
    parser.add_argument("--module", "-m", help="Show detailed info for specific module")
    parser.add_argument(
        "--function", "-f", help="Show detailed info for specific function"
    )
    parser.add_argument(
        "--export-dot", action="store_true", help="Export call graph as DOT file"
    )
    parser.add_argument(
        "--max-functions", type=int, default=50, help="Max functions in DOT graph"
    )
    parser.add_argument("--output", "-o", help="Output file for exports")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose/debug output"
    )

    args = parser.parse_args()

    print("📊 Call Graph Analyzer using Tree-sitter")
    print("=" * 50)

    # Initialize analyzer
    analyzer = CallGraphAnalyzer(verbose=args.verbose)

    # Analyze directory
    analyzer.analyze_directory(args.directory, args.recursive)

    # Print summary
    analyzer.print_summary()

    # Module-specific analysis
    if args.module:
        analyzer.print_module_details(args.module)

    # Function-specific analysis
    if args.function:
        analyzer.print_function_details(args.function)

    # Export DOT graph
    if args.export_dot:
        output_file = args.output or "call_graph.dot"
        analyzer.export_dot_graph(output_file, args.max_functions)

    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
        exit(exit_code)
    except KeyboardInterrupt:
        print("\n👋 Analysis interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n💥 Error: {e}")
        exit(1)
