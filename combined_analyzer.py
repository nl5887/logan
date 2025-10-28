#!/usr/bin/env python3
"""
Combined Code Analysis Pipeline

This script combines LSP (pylsp) and Tree-sitter analysis to provide
comprehensive codebase analysis including:
- Compilation errors and type checking (LSP)
- Code structure and statistics (Tree-sitter)
- Call graphs and module dependencies
- Export results for CI/CD integration

Installation:
    pip install python-lsp-server tree-sitter tree-sitter-python

Usage:
    python combined_analyzer.py
    python combined_analyzer.py --directory /path/to/code
    python combined_analyzer.py --quick-check  # Errors only
    python combined_analyzer.py --full-report  # Complete analysis
"""

import asyncio
import json
import sys
import argparse
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class CombinedResults:
    """Combined analysis results from both LSP and Tree-sitter"""

    # LSP Results
    compilation_errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    type_errors: List[Dict[str, Any]] = field(default_factory=list)

    # Tree-sitter Results
    files_analyzed: int = 0
    total_lines: int = 0
    classes_found: int = 0
    functions_found: int = 0
    methods_found: int = 0
    complexity_score: int = 0

    # Combined Analysis
    module_dependencies: Dict[str, List[str]] = field(default_factory=dict)
    call_graph_entries: int = 0
    most_complex_functions: List[Dict[str, Any]] = field(default_factory=list)
    error_hotspots: List[Dict[str, Any]] = field(default_factory=list)

    # Summary
    analysis_duration: float = 0.0
    success: bool = True
    errors: List[str] = field(default_factory=list)


class CombinedAnalyzer:
    """Combined analyzer using both LSP and Tree-sitter"""

    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root).absolute()
        self.results = CombinedResults()

    def check_dependencies(self) -> bool:
        """Check if required tools are available"""
        missing_deps = []

        # Check pylsp
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pylsp", "--help"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode != 0:
                missing_deps.append("python-lsp-server")
        except:
            missing_deps.append("python-lsp-server")

        # Check tree-sitter
        try:
            import tree_sitter_python
            from tree_sitter import Language, Parser
        except ImportError:
            missing_deps.append("tree-sitter tree-sitter-python")

        if missing_deps:
            print(f"❌ Missing dependencies: {', '.join(missing_deps)}")
            print(f"Install with: pip install {' '.join(missing_deps)}")
            return False

        return True

    async def run_lsp_analysis(self, quick_check: bool = False) -> Dict[str, Any]:
        """Run LSP analysis for compilation errors and type checking"""
        logger.info("🔍 Running LSP analysis...")

        try:
            # Import LSP analyzer
            from lsp_batch_analyzer import LSPBatchAnalyzer

            lsp_analyzer = LSPBatchAnalyzer(str(self.workspace_root))
            await lsp_analyzer.analyze_directory(
                str(self.workspace_root), recursive=True
            )

            # Extract results
            lsp_results = {
                "diagnostics": [],
                "files_analyzed": lsp_analyzer.result.files_analyzed,
                "has_errors": lsp_analyzer.has_compilation_errors(),
            }

            # Process diagnostics
            for diag in lsp_analyzer.result.diagnostics:
                diag_dict = {
                    "file": Path(diag.file_path).name,
                    "line": diag.line,
                    "column": diag.column,
                    "severity": diag.severity,
                    "message": diag.message,
                    "source": diag.source,
                    "code": diag.code,
                }

                if diag.severity == "error":
                    self.results.compilation_errors.append(diag_dict)
                elif diag.severity == "warning":
                    self.results.warnings.append(diag_dict)

                lsp_results["diagnostics"].append(diag_dict)

            logger.info(
                f"✅ LSP analysis complete: {len(self.results.compilation_errors)} errors, {len(self.results.warnings)} warnings"
            )
            return lsp_results

        except Exception as e:
            error_msg = f"LSP analysis failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            self.results.errors.append(error_msg)
            return {"error": error_msg}

    def run_treesitter_analysis(self) -> Dict[str, Any]:
        """Run Tree-sitter analysis for code structure"""
        logger.info("🌳 Running Tree-sitter analysis...")

        try:
            # Import Tree-sitter analyzer
            from treesitter_analyzer import TreeSitterPythonAnalyzer, find_python_files

            # Find Python files
            python_files = find_python_files(str(self.workspace_root), recursive=True)

            if not python_files:
                return {"error": "No Python files found"}

            # Initialize analyzer
            analyzer = TreeSitterPythonAnalyzer()
            analyses = []

            # Analyze each file
            for file_path in python_files:
                try:
                    analysis = analyzer.analyze_file(file_path)
                    analyses.append(analysis)
                except Exception as e:
                    logger.warning(f"⚠️ Failed to analyze {file_path}: {e}")

            # Aggregate results
            self.results.files_analyzed = len(analyses)
            self.results.total_lines = sum(a.total_lines for a in analyses)
            self.results.classes_found = sum(len(a.classes) for a in analyses)
            self.results.functions_found = sum(len(a.functions) for a in analyses)
            self.results.methods_found = sum(
                sum(len(c.methods) for c in a.classes) for a in analyses
            )
            self.results.complexity_score = sum(a.complexity_score for a in analyses)

            # Find most complex functions
            all_functions = []
            for analysis in analyses:
                for func in analysis.functions:
                    all_functions.append(
                        {
                            "name": func.name,
                            "file": Path(analysis.file_path).name,
                            "line": func.range.start.line if func.range else 0,
                            "complexity": func.complexity_score,
                            "is_async": func.is_async,
                        }
                    )

                for cls in analysis.classes:
                    for method in cls.methods:
                        all_functions.append(
                            {
                                "name": f"{cls.name}.{method.name}",
                                "file": Path(analysis.file_path).name,
                                "line": method.range.start.line if method.range else 0,
                                "complexity": method.complexity_score,
                                "is_async": method.is_async,
                            }
                        )

            # Sort by complexity and take top 10
            all_functions.sort(key=lambda x: x["complexity"], reverse=True)
            self.results.most_complex_functions = all_functions[:10]

            # Extract module dependencies
            for analysis in analyses:
                file_name = Path(analysis.file_path).name
                imports = [imp.module for imp in analysis.imports]
                if imports:
                    self.results.module_dependencies[file_name] = imports

            logger.info(
                f"✅ Tree-sitter analysis complete: {self.results.classes_found} classes, {self.results.functions_found} functions"
            )

            return {
                "files_analyzed": self.results.files_analyzed,
                "total_lines": self.results.total_lines,
                "classes": self.results.classes_found,
                "functions": self.results.functions_found,
                "methods": self.results.methods_found,
                "complexity": self.results.complexity_score,
            }

        except Exception as e:
            error_msg = f"Tree-sitter analysis failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            self.results.errors.append(error_msg)
            return {"error": error_msg}

    def analyze_error_hotspots(self):
        """Analyze which files have the most errors"""
        error_counts = {}

        # Count compilation errors by file
        for error in self.results.compilation_errors:
            file_name = error["file"]
            if file_name not in error_counts:
                error_counts[file_name] = {"errors": 0, "warnings": 0, "complexity": 0}
            error_counts[file_name]["errors"] += 1

        # Count warnings by file
        for warning in self.results.warnings:
            file_name = warning["file"]
            if file_name not in error_counts:
                error_counts[file_name] = {"errors": 0, "warnings": 0, "complexity": 0}
            error_counts[file_name]["warnings"] += 1

        # Add complexity scores for files with errors
        for func in self.results.most_complex_functions:
            file_name = func["file"]
            if file_name in error_counts:
                error_counts[file_name]["complexity"] += func["complexity"]

        # Create hotspot list
        for file_name, counts in error_counts.items():
            if (
                counts["errors"] > 0 or counts["warnings"] > 3
            ):  # Files with errors or many warnings
                hotspot_score = (
                    counts["errors"] * 10
                    + counts["warnings"] * 2
                    + counts["complexity"]
                )
                self.results.error_hotspots.append(
                    {
                        "file": file_name,
                        "errors": counts["errors"],
                        "warnings": counts["warnings"],
                        "complexity": counts["complexity"],
                        "hotspot_score": hotspot_score,
                    }
                )

        # Sort by hotspot score
        self.results.error_hotspots.sort(key=lambda x: x["hotspot_score"], reverse=True)

    async def run_combined_analysis(
        self, quick_check: bool = False, full_report: bool = False
    ):
        """Run combined analysis"""
        import time

        start_time = time.time()

        logger.info(f"🚀 Starting combined analysis of {self.workspace_root}")

        # Check dependencies
        if not self.check_dependencies():
            self.results.success = False
            return

        # Run LSP analysis
        lsp_results = await self.run_lsp_analysis(quick_check)

        # Run Tree-sitter analysis (unless quick check and we have errors)
        if not (quick_check and self.results.compilation_errors):
            tree_results = self.run_treesitter_analysis()

        # Analyze error hotspots
        self.analyze_error_hotspots()

        # Set success status
        self.results.success = (
            len(self.results.compilation_errors) == 0 and len(self.results.errors) == 0
        )
        self.results.analysis_duration = time.time() - start_time

        logger.info(
            f"✅ Combined analysis completed in {self.results.analysis_duration:.2f}s"
        )

    def print_summary(self, quick_check: bool = False, full_report: bool = False):
        """Print analysis summary"""
        print(f"\n📊 COMBINED CODE ANALYSIS RESULTS")
        print(f"{'=' * 60}")
        print(f"📁 Files analyzed: {self.results.files_analyzed}")
        print(f"📝 Total lines: {self.results.total_lines:,}")
        print(f"⏱️  Analysis time: {self.results.analysis_duration:.2f}s")

        # Error summary
        error_count = len(self.results.compilation_errors)
        warning_count = len(self.results.warnings)

        if error_count > 0:
            print(f"🔴 Compilation errors: {error_count}")
        else:
            print(f"✅ No compilation errors")

        if warning_count > 0:
            print(f"🟡 Warnings: {warning_count}")

        # Quick check mode - show only errors
        if quick_check:
            if self.results.compilation_errors:
                print(f"\n🔴 COMPILATION ERRORS:")
                for error in self.results.compilation_errors[:10]:
                    print(f"   {error['file']}:{error['line']} - {error['message']}")

                if len(self.results.compilation_errors) > 10:
                    remaining = len(self.results.compilation_errors) - 10
                    print(f"   ... and {remaining} more errors")

            return

        # Standard summary
        print(f"\n📊 CODE STRUCTURE:")
        print(f"   🏗️  Classes: {self.results.classes_found}")
        print(f"   🔧 Functions: {self.results.functions_found}")
        print(f"   ⚙️  Methods: {self.results.methods_found}")
        print(f"   🧮 Complexity: {self.results.complexity_score}")

        # Show most complex functions
        if self.results.most_complex_functions:
            print(f"\n🔥 MOST COMPLEX FUNCTIONS:")
            for func in self.results.most_complex_functions[:5]:
                async_str = "async " if func["is_async"] else ""
                print(
                    f"   {async_str}{func['name']} ({func['file']}:L{func['line']}) - Complexity: {func['complexity']}"
                )

        # Show error hotspots
        if self.results.error_hotspots:
            print(f"\n🎯 ERROR HOTSPOTS:")
            for hotspot in self.results.error_hotspots[:5]:
                print(
                    f"   {hotspot['file']} - {hotspot['errors']} errors, {hotspot['warnings']} warnings, complexity {hotspot['complexity']}"
                )

        # Show compilation errors
        if self.results.compilation_errors:
            print(f"\n🔴 COMPILATION ERRORS:")
            for error in self.results.compilation_errors[:5]:
                print(f"   {error['file']}:{error['line']} - {error['message']}")

            if len(self.results.compilation_errors) > 5:
                remaining = len(self.results.compilation_errors) - 5
                print(f"   ... and {remaining} more errors")

        # Full report additional details
        if full_report:
            print(f"\n📦 MODULE DEPENDENCIES:")
            dep_count = sum(
                len(deps) for deps in self.results.module_dependencies.values()
            )
            print(f"   Total dependencies: {dep_count}")

            # Show files with most dependencies
            dep_files = [
                (file, len(deps))
                for file, deps in self.results.module_dependencies.items()
            ]
            dep_files.sort(key=lambda x: x[1], reverse=True)

            for file, count in dep_files[:5]:
                print(f"   {file}: {count} imports")

    def export_results(self, output_file: str):
        """Export results to JSON"""

        def convert_to_dict(obj):
            if hasattr(obj, "__dict__"):
                return {k: convert_to_dict(v) for k, v in obj.__dict__.items()}
            elif isinstance(obj, list):
                return [convert_to_dict(item) for item in obj]
            elif isinstance(obj, dict):
                return {k: convert_to_dict(v) for k, v in obj.items()}
            return obj

        output_data = {
            "analysis_metadata": {
                "workspace": str(self.workspace_root),
                "timestamp": self.results.analysis_duration,
                "success": self.results.success,
            },
            "results": convert_to_dict(self.results),
        }

        with open(output_file, "w") as f:
            json.dump(output_data, f, indent=2)

        print(f"📄 Results exported to: {output_file}")

    def get_exit_code(self) -> int:
        """Get appropriate exit code for CI/CD"""
        if not self.results.success:
            return 1
        if self.results.compilation_errors:
            return 1
        return 0


async def main():
    parser = argparse.ArgumentParser(
        description="Combined Code Analysis Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python combined_analyzer.py                      # Standard analysis
    python combined_analyzer.py --quick-check        # Errors only (fast)
    python combined_analyzer.py --full-report        # Detailed analysis
    python combined_analyzer.py --export results.json # Export results
    python combined_analyzer.py --directory /path    # Specific directory
        """,
    )

    parser.add_argument(
        "--directory", "-d", default=".", help="Directory to analyze (default: current)"
    )
    parser.add_argument(
        "--quick-check",
        action="store_true",
        help="Quick check for compilation errors only",
    )
    parser.add_argument(
        "--full-report", action="store_true", help="Generate detailed full report"
    )
    parser.add_argument("--export", "-o", help="Export results to JSON file")
    parser.add_argument(
        "--quiet", "-q", action="store_true", help="Reduce output verbosity"
    )

    args = parser.parse_args()

    if args.quiet:
        logger.setLevel(logging.WARNING)

    # Header
    print("🔬 Combined Code Analysis Pipeline")
    print("Using LSP (pylsp) + Tree-sitter for comprehensive analysis")
    print("=" * 60)

    # Initialize analyzer
    analyzer = CombinedAnalyzer(args.directory)

    try:
        # Run analysis
        await analyzer.run_combined_analysis(
            quick_check=args.quick_check, full_report=args.full_report
        )

        # Print results
        analyzer.print_summary(
            quick_check=args.quick_check, full_report=args.full_report
        )

        # Export if requested
        if args.export:
            analyzer.export_results(args.export)

        # Print final status
        if analyzer.results.success:
            print(f"\n✅ Analysis completed successfully")
        else:
            print(f"\n❌ Analysis completed with issues")

        return analyzer.get_exit_code()

    except KeyboardInterrupt:
        print("\n👋 Analysis interrupted by user")
        return 1
    except Exception as e:
        print(f"\n💥 Error: {e}")
        logger.exception("Detailed error:")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        sys.exit(1)
