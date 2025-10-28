#!/usr/bin/env python3
"""
Tree-sitter Python Code Analyzer

This script uses Tree-sitter to analyze Python files in the current directory,
extracting detailed information about classes, methods, functions, imports,
and other code structures.

Installation:
    pip install tree-sitter tree-sitter-python

Usage:
    python treesitter_analyzer.py
    python treesitter_analyzer.py --recursive
    python treesitter_analyzer.py --output analysis.json
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
import ast
import inspect

try:
    import tree_sitter_python as tspython
    from tree_sitter import Language, Parser, Query

    print(f"✅ Tree-sitter version: {getattr(tspython, '__version__', 'unknown')}")
    TREE_SITTER_AVAILABLE = True
except ImportError as e:
    print(f"❌ Tree-sitter not installed: {e}")
    print("Run: pip install tree-sitter tree-sitter-python")
    exit(1)
except Exception as e:
    print(f"❌ Error importing Tree-sitter: {e}")
    exit(1)


@dataclass
class Position:
    """Code position information"""

    line: int
    column: int


@dataclass
class Range:
    """Code range information"""

    start: Position
    end: Position


@dataclass
class Parameter:
    """Function/method parameter information"""

    name: str
    type_annotation: Optional[str] = None
    default_value: Optional[str] = None
    is_vararg: bool = False
    is_kwarg: bool = False


@dataclass
class FunctionInfo:
    """Function or method information"""

    name: str
    parameters: List[Parameter] = field(default_factory=list)
    return_type: Optional[str] = None
    docstring: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    is_async: bool = False
    is_method: bool = False
    is_classmethod: bool = False
    is_staticmethod: bool = False
    is_property: bool = False
    visibility: str = "public"  # public, private, protected
    range: Optional[Range] = None
    complexity_score: int = 0


@dataclass
class ClassInfo:
    """Class information"""

    name: str
    base_classes: List[str] = field(default_factory=list)
    methods: List[FunctionInfo] = field(default_factory=list)
    properties: List[str] = field(default_factory=list)
    class_variables: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    visibility: str = "public"
    range: Optional[Range] = None
    is_abstract: bool = False
    is_dataclass: bool = False


@dataclass
class ImportInfo:
    """Import statement information"""

    module: str
    names: List[str] = field(default_factory=list)  # for 'from x import y'
    alias: Optional[str] = None
    is_relative: bool = False
    level: int = 0  # for relative imports


@dataclass
class VariableInfo:
    """Variable/assignment information"""

    name: str
    type_annotation: Optional[str] = None
    value: Optional[str] = None
    is_global: bool = False
    is_constant: bool = False
    range: Optional[Range] = None


@dataclass
class FileAnalysis:
    """Complete file analysis"""

    file_path: str
    classes: List[ClassInfo] = field(default_factory=list)
    functions: List[FunctionInfo] = field(default_factory=list)
    imports: List[ImportInfo] = field(default_factory=list)
    variables: List[VariableInfo] = field(default_factory=list)
    docstring: Optional[str] = None
    total_lines: int = 0
    blank_lines: int = 0
    comment_lines: int = 0
    complexity_score: int = 0
    errors: List[str] = field(default_factory=list)


class TreeSitterPythonAnalyzer:
    """Tree-sitter based Python code analyzer"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        # Initialize Tree-sitter with compatibility handling
        try:
            if self.verbose:
                print("🔧 Initializing Tree-sitter...")

            # Try different initialization methods based on version
            try:
                # Method 1: New API (tree-sitter-python >= 0.20)
                if self.verbose:
                    print("   Trying new Tree-sitter API...")
                self.language = Language(tspython.language())
                if self.verbose:
                    print("   ✅ New API successful")
            except (TypeError, AttributeError) as e:
                print(f"   ❌ New API failed: {e}")
                try:
                    # Method 2: Old API with language name
                    print("   Trying old Tree-sitter API with language name...")
                    self.language = Language(tspython.language(), "python")
                    print("   ✅ Old API with name successful")
                except Exception as e2:
                    print(f"   ❌ Old API with name failed: {e2}")
                    try:
                        # Method 3: Direct language object
                        print("   Trying direct language object...")
                        lang_obj = tspython.language()
                        if hasattr(lang_obj, "query"):
                            self.language = lang_obj
                            print("   ✅ Direct language object successful")
                        else:
                            self.language = Language(lang_obj)
                            print("   ✅ Wrapped language object successful")
                    except Exception as e3:
                        print(f"   ❌ Direct language object failed: {e3}")
                        raise Exception(
                            f"All Tree-sitter initialization methods failed: {e}, {e2}, {e3}"
                        )

            self.parser = Parser()
            # Try different methods to set language
            try:
                self.parser.set_language(self.language)
                print("✅ Tree-sitter parser initialized successfully")
            except AttributeError:
                # Newer API uses language property
                try:
                    self.parser.language = self.language
                    print("✅ Tree-sitter parser initialized with new API")
                except Exception as e3:
                    print(f"❌ Failed to set language: {e3}")
                    raise

        except Exception as e:
            print(f"❌ Failed to initialize Tree-sitter: {e}")
            print(
                f"Tree-sitter Python version: {getattr(tspython, '__version__', 'unknown')}"
            )
            print("Try:")
            print("  pip uninstall tree-sitter tree-sitter-python")
            print("  pip install tree-sitter==0.20.4 tree-sitter-python==0.20.4")
            raise

        # Query patterns for different code constructs
        try:
            self.queries = self._init_queries()
            print(f"✅ Initialized {len(self.queries)} query patterns")
        except Exception as e:
            print(f"❌ Failed to initialize queries: {e}")
            raise

    def _init_queries(self) -> Dict[str, Any]:
        """Initialize Tree-sitter queries for different code patterns"""
        queries = {}

        try:
            # Class definitions
            print("   Initializing class query...")
            queries["classes"] = Query(
                self.language,
                """
                (class_definition
                    name: (identifier) @class_name
                    superclasses: (argument_list)? @base_classes
                    body: (block) @class_body
                ) @class_def
            """,
            )
        except Exception as e:
            print(f"   ❌ Failed to create class query: {e}")
            # Fallback to simpler query
            try:
                queries["classes"] = Query(
                    self.language, "(class_definition) @class_def"
                )
                print("   ✅ Using simplified class query")
            except Exception as e2:
                print(f"   ❌ Even simple class query failed: {e2}")
                # Skip this query if it fails
                pass

        # Function definitions
        try:
            print("   Initializing function query...")
            queries["functions"] = Query(
                self.language,
                """
                (function_definition
                    name: (identifier) @func_name
                    parameters: (parameters) @func_params
                    return_type: (type)? @return_type
                    body: (block) @func_body
                ) @func_def
            """,
            )
        except Exception as e:
            print(f"   ❌ Failed to create function query: {e}")
            try:
                queries["functions"] = Query(
                    self.language, "(function_definition) @func_def"
                )
                print("   ✅ Using simplified function query")
            except:
                pass

        # Skip complex queries for now to avoid errors
        print("   Skipping complex queries for compatibility...")

        # Simple queries for basic functionality
        try:
            queries["imports"] = Query(self.language, "(import_statement) @import")
            queries["from_imports"] = Query(
                self.language, "(import_from_statement) @from_import"
            )
            queries["assignments"] = Query(self.language, "(assignment) @assignment")
            print("   ✅ Basic queries initialized")
        except Exception as e:
            print(f"   ❌ Failed to initialize basic queries: {e}")
            # Continue without queries - we'll use basic parsing

        return queries

    def _traverse_for_classes(self, node, captures, source_bytes):
        """Fallback method to find classes by traversing nodes"""
        if node.type == "class_definition":
            captures.append((node, "class_def"))
        for child in node.children:
            self._traverse_for_classes(child, captures, source_bytes)

    def _traverse_for_functions(self, node, captures, source_bytes, depth=0):
        """Fallback method to find functions by traversing nodes"""
        if node.type == "function_definition":
            captures.append((node, "func_def"))
        for child in node.children:
            self._traverse_for_functions(child, captures, source_bytes, depth + 1)

    def _get_node_text(self, node, source_bytes: bytes) -> str:
        """Extract text from a tree-sitter node"""
        return source_bytes[node.start_byte : node.end_byte].decode(
            "utf-8", errors="replace"
        )

    def _get_range(self, node) -> Range:
        """Convert tree-sitter node to Range object"""
        return Range(
            start=Position(node.start_point[0] + 1, node.start_point[1]),
            end=Position(node.end_point[0] + 1, node.end_point[1]),
        )

    def _analyze_parameters(self, params_node, source_bytes: bytes) -> List[Parameter]:
        """Analyze function parameters"""
        parameters = []

        if not params_node:
            return parameters

        for child in params_node.children:
            if child.type == "identifier":
                param = Parameter(name=self._get_node_text(child, source_bytes))
                parameters.append(param)
            elif child.type == "default_parameter":
                name_node = child.child_by_field_name("name")
                value_node = child.child_by_field_name("value")

                if name_node:
                    param = Parameter(
                        name=self._get_node_text(name_node, source_bytes),
                        default_value=self._get_node_text(value_node, source_bytes)
                        if value_node
                        else None,
                    )
                    parameters.append(param)
            elif child.type == "typed_parameter":
                name_node = child.child_by_field_name("name")
                type_node = child.child_by_field_name("type")

                if name_node:
                    param = Parameter(
                        name=self._get_node_text(name_node, source_bytes),
                        type_annotation=self._get_node_text(type_node, source_bytes)
                        if type_node
                        else None,
                    )
                    parameters.append(param)
            elif child.type == "list_splat_pattern":
                # *args
                name_node = child.children[1] if len(child.children) > 1 else None
                if name_node:
                    param = Parameter(
                        name=self._get_node_text(name_node, source_bytes),
                        is_vararg=True,
                    )
                    parameters.append(param)
            elif child.type == "dictionary_splat_pattern":
                # **kwargs
                name_node = child.children[1] if len(child.children) > 1 else None
                if name_node:
                    param = Parameter(
                        name=self._get_node_text(name_node, source_bytes), is_kwarg=True
                    )
                    parameters.append(param)

        return parameters

    def _get_visibility(self, name: str) -> str:
        """Determine visibility based on naming convention"""
        if name.startswith("__") and name.endswith("__"):
            return "magic"
        elif name.startswith("__"):
            return "private"
        elif name.startswith("_"):
            return "protected"
        else:
            return "public"

    def _calculate_complexity(self, node, source_bytes: bytes) -> int:
        """Calculate cyclomatic complexity of a function"""
        complexity = 1  # Base complexity

        def traverse_node(n):
            nonlocal complexity

            # Decision points that increase complexity
            if n.type in [
                "if_statement",
                "elif_clause",
                "while_statement",
                "for_statement",
                "try_statement",
                "except_clause",
                "with_statement",
                "match_statement",
                "case_clause",
            ]:
                complexity += 1

            # Logical operators
            elif n.type in ["and", "or"]:
                complexity += 1

            # Recursively check children
            for child in n.children:
                traverse_node(child)

        traverse_node(node)
        return complexity

    def _extract_docstring(self, body_node, source_bytes: bytes) -> Optional[str]:
        """Extract docstring from function/class body"""
        if not body_node or len(body_node.children) < 2:
            return None

        # Look for string literal as first statement
        first_stmt = body_node.children[1]  # Skip colon
        if first_stmt.type == "expression_statement":
            expr = first_stmt.children[0]
            if expr.type == "string":
                docstring = self._get_node_text(expr, source_bytes)
                # Clean up the docstring
                return docstring.strip("\"'").strip()

        return None

    def _analyze_decorators(self, node, source_bytes: bytes) -> List[str]:
        """Extract decorators from a decorated definition"""
        decorators = []

        if node.type == "decorated_definition":
            for child in node.children:
                if child.type == "decorator":
                    decorator_text = self._get_node_text(child, source_bytes).strip("@")
                    decorators.append(decorator_text)

        return decorators

    def analyze_file(self, file_path: str) -> FileAnalysis:
        """Analyze a single Python file"""
        analysis = FileAnalysis(file_path=file_path)

        try:
            with open(file_path, "rb") as f:
                source_bytes = f.read()

            # Parse the file
            tree = self.parser.parse(source_bytes)
            root_node = tree.root_node

            # Count lines
            source_text = source_bytes.decode("utf-8", errors="replace")
            lines = source_text.split("\n")
            analysis.total_lines = len(lines)
            analysis.blank_lines = sum(1 for line in lines if not line.strip())
            analysis.comment_lines = sum(
                1 for line in lines if line.strip().startswith("#")
            )

            # Extract module-level docstring
            analysis.docstring = self._extract_docstring(root_node, source_bytes)

            # Analyze classes
            self._analyze_classes(root_node, source_bytes, analysis)

            # Analyze functions (non-methods)
            self._analyze_functions(root_node, source_bytes, analysis)

            # Analyze imports
            self._analyze_imports(root_node, source_bytes, analysis)

            # Analyze variables
            self._analyze_variables(root_node, source_bytes, analysis)

            # Calculate overall complexity
            analysis.complexity_score = sum(
                f.complexity_score for f in analysis.functions
            )
            analysis.complexity_score += sum(
                sum(m.complexity_score for m in c.methods) for c in analysis.classes
            )

        except Exception as e:
            analysis.errors.append(f"Error analyzing {file_path}: {str(e)}")

        return analysis

    def _analyze_classes(self, root_node, source_bytes: bytes, analysis: FileAnalysis):
        """Analyze all classes in the file"""
        if "classes" not in self.queries:
            return
        try:
            # Try different methods to execute the query
            if hasattr(self.queries["classes"], "captures"):
                captures = self.queries["classes"].captures(root_node)
            elif hasattr(self.queries["classes"], "matches"):
                captures = []
                for match in self.queries["classes"].matches(root_node):
                    for capture in match[1]:
                        captures.append((capture[0], capture[1]))
            else:
                # Fallback - traverse nodes manually
                captures = []
                self._traverse_for_classes(root_node, captures, source_bytes)
        except Exception as e:
            print(f"   ❌ Error executing class query: {e}")
            return

        if not captures:
            return

        class_nodes = {}
        for node, capture_name in captures:
            if capture_name == "class_def" or node.type == "class_definition":
                class_info = ClassInfo(name="", range=self._get_range(node))
                class_nodes[node] = class_info

                # Extract class name directly
                name_node = node.child_by_field_name("name")
                if name_node:
                    class_info.name = self._get_node_text(name_node, source_bytes)
                    class_info.visibility = self._get_visibility(class_info.name)
            elif capture_name == "class_name":
                # Find the corresponding class_def
                for class_node, class_info in class_nodes.items():
                    if class_node.start_byte <= node.start_byte <= class_node.end_byte:
                        class_info.name = self._get_node_text(node, source_bytes)
                        class_info.visibility = self._get_visibility(class_info.name)
                        break

        # Analyze methods for each class
        for class_node, class_info in class_nodes.items():
            self._analyze_class_methods(class_node, source_bytes, class_info)
            self._analyze_class_attributes(class_node, source_bytes, class_info)

            # Extract class docstring
            body_node = class_node.child_by_field_name("body")
            class_info.docstring = self._extract_docstring(body_node, source_bytes)

            # Check for decorators
            parent = class_node.parent
            if parent and parent.type == "decorated_definition":
                class_info.decorators = self._analyze_decorators(parent, source_bytes)
                class_info.is_dataclass = any(
                    "dataclass" in dec for dec in class_info.decorators
                )

            analysis.classes.append(class_info)

    def _analyze_class_methods(
        self, class_node, source_bytes: bytes, class_info: ClassInfo
    ):
        """Analyze methods within a class"""

        def traverse_for_functions(node, depth=0):
            if (
                node.type == "function_definition" and depth == 2
            ):  # Direct child of class body
                method_info = self._analyze_single_function(node, source_bytes)
                method_info.is_method = True

                # Check for special method types
                if method_info.decorators:
                    if "classmethod" in method_info.decorators:
                        method_info.is_classmethod = True
                    elif "staticmethod" in method_info.decorators:
                        method_info.is_staticmethod = True
                    elif "property" in method_info.decorators:
                        method_info.is_property = True
                        class_info.properties.append(method_info.name)

                class_info.methods.append(method_info)

            for child in node.children:
                traverse_for_functions(child, depth + 1)

        traverse_for_functions(class_node)

    def _analyze_class_attributes(
        self, class_node, source_bytes: bytes, class_info: ClassInfo
    ):
        """Analyze class attributes/variables"""
        body_node = class_node.child_by_field_name("body")
        if not body_node:
            return

        for child in body_node.children:
            if child.type == "assignment":
                left_node = child.child_by_field_name("left")
                if left_node and left_node.type == "identifier":
                    attr_name = self._get_node_text(left_node, source_bytes)
                    class_info.class_variables.append(attr_name)

    def _analyze_functions(
        self, root_node, source_bytes: bytes, analysis: FileAnalysis
    ):
        """Analyze top-level functions (not methods)"""
        if "functions" not in self.queries:
            # Fallback to manual traversal
            def traverse_for_functions(node, depth=0):
                if (
                    node.type == "function_definition" and depth == 0
                ):  # Top-level function
                    func_info = self._analyze_single_function(node, source_bytes)
                    analysis.functions.append(func_info)
                elif node.type != "class_definition":  # Don't traverse into classes
                    for child in node.children:
                        traverse_for_functions(child, depth)

            traverse_for_functions(root_node)
            return

        try:
            # Try different methods to execute the query
            if hasattr(self.queries["functions"], "captures"):
                captures = self.queries["functions"].captures(root_node)
            elif hasattr(self.queries["functions"], "matches"):
                captures = []
                for match in self.queries["functions"].matches(root_node):
                    for capture in match[1]:
                        captures.append((capture[0], capture[1]))
            else:
                # Fallback - traverse nodes manually
                captures = []
                self._traverse_for_functions(root_node, captures, source_bytes)
        except Exception as e:
            print(f"   ❌ Error executing function query: {e}")
            return

        for node, capture_name in captures:
            if capture_name == "func_def" or node.type == "function_definition":
                # Check if it's a top-level function (not inside a class)
                parent = node.parent
                while parent and parent.type != "module":
                    if parent.type == "class_definition":
                        break  # Skip methods
                    parent = parent.parent
                else:
                    func_info = self._analyze_single_function(node, source_bytes)
                    analysis.functions.append(func_info)

    def _analyze_single_function(self, func_node, source_bytes: bytes) -> FunctionInfo:
        """Analyze a single function definition"""
        name_node = func_node.child_by_field_name("name")
        params_node = func_node.child_by_field_name("parameters")
        return_type_node = func_node.child_by_field_name("return_type")
        body_node = func_node.child_by_field_name("body")

        func_info = FunctionInfo(
            name=self._get_node_text(name_node, source_bytes)
            if name_node
            else "unknown",
            range=self._get_range(func_node),
        )

        # Analyze parameters
        if params_node:
            func_info.parameters = self._analyze_parameters(params_node, source_bytes)

        # Return type annotation
        if return_type_node:
            func_info.return_type = self._get_node_text(return_type_node, source_bytes)

        # Docstring
        func_info.docstring = self._extract_docstring(body_node, source_bytes)

        # Check if async
        if func_node.children[0].type == "async":
            func_info.is_async = True

        # Visibility
        func_info.visibility = self._get_visibility(func_info.name)

        # Complexity
        func_info.complexity_score = (
            self._calculate_complexity(body_node, source_bytes) if body_node else 1
        )

        # Check for decorators
        parent = func_node.parent
        if parent and parent.type == "decorated_definition":
            func_info.decorators = self._analyze_decorators(parent, source_bytes)

        return func_info

    def _analyze_imports(self, root_node, source_bytes: bytes, analysis: FileAnalysis):
        """Analyze import statements"""

        def traverse_for_imports(node):
            if node.type == "import_statement":
                # Simple import: import module
                module_node = node.children[1]  # Skip 'import' keyword
                if module_node.type == "dotted_name":
                    module_name = self._get_node_text(module_node, source_bytes)
                    analysis.imports.append(ImportInfo(module=module_name))
                elif module_node.type == "aliased_import":
                    name_node = module_node.children[0]
                    alias_node = module_node.children[2]  # Skip 'as'
                    module_name = self._get_node_text(name_node, source_bytes)
                    alias = self._get_node_text(alias_node, source_bytes)
                    analysis.imports.append(ImportInfo(module=module_name, alias=alias))

            elif node.type == "import_from_statement":
                # From import: from module import names
                module_node = node.child_by_field_name("module_name")
                names_node = node.child_by_field_name("name")

                if module_node:
                    module_name = self._get_node_text(module_node, source_bytes)
                    names = []

                    if names_node and names_node.type == "import_list":
                        for child in names_node.children:
                            if child.type == "identifier":
                                names.append(self._get_node_text(child, source_bytes))
                            elif child.type == "aliased_import":
                                name_node = child.children[0]
                                names.append(
                                    self._get_node_text(name_node, source_bytes)
                                )

                    analysis.imports.append(ImportInfo(module=module_name, names=names))

            for child in node.children:
                traverse_for_imports(child)

        traverse_for_imports(root_node)

    def _analyze_variables(
        self, root_node, source_bytes: bytes, analysis: FileAnalysis
    ):
        """Analyze top-level variable assignments"""

        def traverse_for_assignments(node, depth=0):
            if node.type == "assignment" and depth == 0:  # Top-level assignment
                left_node = node.child_by_field_name("left")
                right_node = node.child_by_field_name("right")
                type_node = node.child_by_field_name("type")

                if left_node and left_node.type == "identifier":
                    var_name = self._get_node_text(left_node, source_bytes)
                    var_info = VariableInfo(
                        name=var_name,
                        type_annotation=self._get_node_text(type_node, source_bytes)
                        if type_node
                        else None,
                        value=self._get_node_text(right_node, source_bytes)[:100]
                        if right_node
                        else None,  # Truncate long values
                        is_constant=var_name.isupper(),
                        range=self._get_range(node),
                    )
                    analysis.variables.append(var_info)
            elif node.type not in ["class_definition", "function_definition"]:
                for child in node.children:
                    traverse_for_assignments(child, depth)

        traverse_for_assignments(root_node)


def find_python_files(directory: str, recursive: bool = False) -> List[str]:
    """Find all Python files in directory"""
    python_files = []
    path = Path(directory)

    if recursive:
        python_files = list(path.rglob("*.py"))
    else:
        python_files = list(path.glob("*.py"))

    return [str(f) for f in python_files]


def print_analysis_summary(analyses: List[FileAnalysis]):
    """Print a summary of all analyses"""
    total_files = len(analyses)
    total_classes = sum(len(a.classes) for a in analyses)
    total_functions = sum(len(a.functions) for a in analyses)
    total_methods = sum(sum(len(c.methods) for c in a.classes) for a in analyses)
    total_lines = sum(a.total_lines for a in analyses)
    total_complexity = sum(a.complexity_score for a in analyses)

    print(f"\n📊 ANALYSIS SUMMARY")
    print(f"{'=' * 60}")
    print(f"📁 Files analyzed: {total_files}")
    print(f"📝 Total lines: {total_lines:,}")
    print(f"🏗️  Classes: {total_classes}")
    print(f"🔧 Functions: {total_functions}")
    print(f"⚙️  Methods: {total_methods}")
    print(f"🧮 Total complexity: {total_complexity}")

    if analyses:
        print(f"\n📈 DETAILED BREAKDOWN")
        print(f"{'=' * 60}")

        for analysis in analyses:
            if analysis.errors:
                print(f"❌ {analysis.file_path}: {analysis.errors[0]}")
                continue

            print(f"\n📄 {Path(analysis.file_path).name}")
            print(
                f"   Lines: {analysis.total_lines}, Classes: {len(analysis.classes)}, Functions: {len(analysis.functions)}"
            )

            # Show classes with lines
            for cls in analysis.classes:
                line_info = (
                    f"L{cls.range.start.line}-{cls.range.end.line}"
                    if cls.range
                    else "L?"
                )
                decorators = (
                    f"@{',@'.join(cls.decorators[:2])}" if cls.decorators else ""
                )
                print(f"   🏗️  {cls.name} ({line_info}) {decorators}")

                # Show all methods
                for method in cls.methods:
                    method_line = (
                        f"L{method.range.start.line}" if method.range else "L?"
                    )
                    async_str = "async " if method.is_async else ""
                    print(
                        f"      🔧 {async_str}{method.name}({len(method.parameters)}) ({method_line})"
                    )

            # Show all functions with lines
            for func in analysis.functions:
                line_info = f"L{func.range.start.line}" if func.range else "L?"
                async_str = "async " if func.is_async else ""
                print(
                    f"   🔧 {async_str}{func.name}({len(func.parameters)}) ({line_info})"
                )


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Tree-sitter Python Code Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python treesitter_analyzer.py                    # Analyze current directory
    python treesitter_analyzer.py --recursive        # Analyze recursively
    python treesitter_analyzer.py --output report.json  # Save detailed JSON report
    python treesitter_analyzer.py --filter-classes   # Show only classes
        """,
    )

    parser.add_argument(
        "--directory",
        "-d",
        default=".",
        help="Directory to analyze (default: current directory)",
    )

    parser.add_argument(
        "--recursive", "-r", action="store_true", help="Analyze files recursively"
    )

    parser.add_argument("--output", "-o", help="Output detailed analysis to JSON file")

    parser.add_argument(
        "--filter-classes",
        action="store_true",
        help="Show detailed class information only",
    )

    parser.add_argument(
        "--filter-functions",
        action="store_true",
        help="Show detailed function information only",
    )

    parser.add_argument(
        "--min-complexity",
        type=int,
        help="Show only functions/methods with complexity >= N",
    )

    args = parser.parse_args()

    print("🌳 Tree-sitter Python Code Analyzer")
    print("=" * 60)

    # Find Python files
    python_files = find_python_files(args.directory, args.recursive)

    if not python_files:
        print(f"❌ No Python files found in {args.directory}")
        return 1

    print(f"📁 Found {len(python_files)} Python file(s)")

    # Initialize analyzer
    try:
        analyzer = TreeSitterPythonAnalyzer()
    except Exception as e:
        print(f"❌ Failed to initialize Tree-sitter analyzer: {e}")
        print("🔄 Falling back to Python AST analyzer...")
        try:
            analyzer = ASTFallbackAnalyzer()
            print("✅ AST fallback analyzer initialized")
        except Exception as e2:
            print(f"❌ AST fallback also failed: {e2}")
            return 1

    # Analyze all files
    analyses = []
    for file_path in python_files:
        print(f"🔍 Analyzing {file_path}...")
        analysis = analyzer.analyze_file(file_path)
        analyses.append(analysis)

    # Print summary
    print_analysis_summary(analyses)

    # Apply filters if requested
    if args.filter_classes:
        print(f"\n🏗️  DETAILED CLASS INFORMATION")
        print(f"{'=' * 60}")
        for analysis in analyses:
            for cls in analysis.classes:
                line_range = (
                    f"L{cls.range.start.line}-{cls.range.end.line}"
                    if cls.range
                    else "L?"
                )
                print(
                    f"\n🏗️  {cls.name} ({line_range}) - {Path(analysis.file_path).name}"
                )
                print(
                    f"   Methods: {len(cls.methods)}, Properties: {len(cls.properties)}"
                )
                if cls.decorators:
                    print(f"   Decorators: {', '.join(cls.decorators)}")
                if cls.base_classes:
                    print(f"   Inherits: {', '.join(cls.base_classes)}")

    if args.filter_functions:
        print(f"\n🔧 DETAILED FUNCTION INFORMATION")
        print(f"{'=' * 60}")
        for analysis in analyses:
            all_functions = analysis.functions.copy()
            for cls in analysis.classes:
                all_functions.extend(cls.methods)

            for func in all_functions:
                if args.min_complexity and func.complexity_score < args.min_complexity:
                    continue

                line_range = (
                    f"L{func.range.start.line}-{func.range.end.line}"
                    if func.range
                    else "L?"
                )
                func_type = "Method" if func.is_method else "Function"
                async_str = "async " if func.is_async else ""
                print(
                    f"\n🔧 {async_str}{func.name}({len(func.parameters)}) ({line_range}) - {Path(analysis.file_path).name}"
                )
                print(f"   Type: {func_type}, Complexity: {func.complexity_score}")
                if func.return_type:
                    print(f"   Returns: {func.return_type}")
                if func.decorators:
                    print(f"   Decorators: {', '.join(func.decorators)}")

    # Save detailed analysis to JSON if requested
    if args.output:
        try:
            # Convert dataclasses to dictionaries for JSON serialization
            def convert_to_dict(obj):
                if hasattr(obj, "__dict__"):
                    result = {}
                    for key, value in obj.__dict__.items():
                        if isinstance(value, list):
                            result[key] = [convert_to_dict(item) for item in value]
                        elif hasattr(value, "__dict__"):
                            result[key] = convert_to_dict(value)
                        else:
                            result[key] = value
                    return result
                return obj

            output_data = {
                "analysis_summary": {
                    "total_files": len(analyses),
                    "total_classes": sum(len(a.classes) for a in analyses),
                    "total_functions": sum(len(a.functions) for a in analyses),
                    "total_methods": sum(
                        sum(len(c.methods) for c in a.classes) for a in analyses
                    ),
                    "total_lines": sum(a.total_lines for a in analyses),
                    "total_complexity": sum(a.complexity_score for a in analyses),
                },
                "files": [convert_to_dict(analysis) for analysis in analyses],
            }

            with open(args.output, "w") as f:
                json.dump(output_data, f, indent=2, default=str)

            print(f"\n💾 Detailed analysis saved to: {args.output}")

        except Exception as e:
            print(f"❌ Error saving to {args.output}: {e}")

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
