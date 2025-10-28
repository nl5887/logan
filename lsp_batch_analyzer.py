#!/usr/bin/env python3
"""
Batch LSP Analyzer using pylsp

This script uses the Python Language Server (pylsp) in batch mode to analyze
Python codebases automatically. It can find compilation errors, type issues,
build call graphs, and provide comprehensive code analysis.

Features:
- Batch analysis of entire codebases
- Compilation error detection
- Type checking and linting
- Call hierarchy extraction
- Symbol references and definitions
- Export results for CI/CD integration

Installation:
    pip install python-lsp-server python-lsp-jsonrpc

Usage:
    python lsp_batch_analyzer.py
    python lsp_batch_analyzer.py --directory /path/to/code
    python lsp_batch_analyzer.py --check-errors-only
    python lsp_batch_analyzer.py --export-json results.json
"""

import asyncio
import json
import os
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse
import subprocess
import tempfile
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class LSPDiagnostic:
    """LSP diagnostic (error, warning, info)"""

    file_path: str
    line: int
    column: int
    severity: str  # error, warning, info, hint
    message: str
    source: str  # pylsp, flake8, mypy, etc.
    code: Optional[str] = None


@dataclass
class SymbolReference:
    """Symbol reference location"""

    file_path: str
    line: int
    column: int
    symbol_name: str
    context: str


@dataclass
class FunctionCall:
    """Function call information"""

    caller: str
    callee: str
    file_path: str
    line: int
    column: int


@dataclass
class AnalysisResult:
    """Complete analysis result"""

    files_analyzed: int = 0
    diagnostics: List[LSPDiagnostic] = field(default_factory=list)
    symbols: Dict[str, List[SymbolReference]] = field(default_factory=dict)
    call_graph: List[FunctionCall] = field(default_factory=list)
    imports: Dict[str, List[str]] = field(default_factory=dict)  # file -> [imports]
    errors: List[str] = field(default_factory=list)


class LSPBatchAnalyzer:
    """Batch analyzer using pylsp"""

    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root).absolute()
        self.result = AnalysisResult()
        self.lsp_process = None
        self.request_id = 0

    async def start_lsp_server(self):
        """Start the pylsp server process"""
        try:
            # Start pylsp process
            self.lsp_process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "pylsp",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            logger.info("✅ LSP server started")

            # Initialize the server
            await self._send_initialize()

        except Exception as e:
            logger.error(f"❌ Failed to start LSP server: {e}")
            raise

    async def _send_initialize(self):
        """Send initialize request to LSP server"""
        self.request_id += 1

        init_request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": "initialize",
            "params": {
                "processId": os.getpid(),
                "rootUri": f"file://{self.workspace_root}",
                "capabilities": {
                    "workspace": {"workspaceFolders": True, "configuration": True},
                    "textDocument": {
                        "definition": {"linkSupport": True},
                        "references": {"context": True},
                        "hover": {"contentFormat": ["markdown", "plaintext"]},
                        "documentSymbol": {"hierarchicalDocumentSymbolSupport": True},
                        "publishDiagnostics": {"relatedInformation": True},
                    },
                },
                "initializationOptions": {
                    "settings": {
                        "pylsp": {
                            "plugins": {
                                "flake8": {"enabled": True},
                                "mypy": {"enabled": True},
                                "pylint": {"enabled": True},
                                "pycodestyle": {"enabled": True},
                                "pydocstyle": {"enabled": True},
                            }
                        }
                    }
                },
            },
        }

        await self._send_request(init_request)

        # Send initialized notification
        initialized = {"jsonrpc": "2.0", "method": "initialized", "params": {}}

        await self._send_notification(initialized)

    async def _send_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send request to LSP server and get response"""
        if not self.lsp_process:
            return None

        request_json = json.dumps(request) + "\n"
        content_length = len(request_json.encode("utf-8"))

        message = f"Content-Length: {content_length}\r\n\r\n{request_json}"

        try:
            self.lsp_process.stdin.write(message.encode("utf-8"))
            await self.lsp_process.stdin.drain()

            # Read response
            response = await self._read_lsp_response()
            return response

        except Exception as e:
            logger.error(f"❌ Error sending LSP request: {e}")
            return None

    async def _send_notification(self, notification: Dict[str, Any]):
        """Send notification to LSP server (no response expected)"""
        if not self.lsp_process:
            return

        request_json = json.dumps(notification) + "\n"
        content_length = len(request_json.encode("utf-8"))

        message = f"Content-Length: {content_length}\r\n\r\n{request_json}"

        try:
            self.lsp_process.stdin.write(message.encode("utf-8"))
            await self.lsp_process.stdin.drain()
        except Exception as e:
            logger.error(f"❌ Error sending LSP notification: {e}")

    async def _read_lsp_response(self) -> Optional[Dict[str, Any]]:
        """Read response from LSP server"""
        try:
            # Read headers
            headers = {}
            while True:
                line = await self.lsp_process.stdout.readline()
                line = line.decode("utf-8").strip()

                if not line:  # Empty line indicates end of headers
                    break

                if ":" in line:
                    key, value = line.split(":", 1)
                    headers[key.strip()] = value.strip()

            # Read content
            content_length = int(headers.get("Content-Length", 0))
            if content_length > 0:
                content = await self.lsp_process.stdout.read(content_length)
                content = content.decode("utf-8")
                return json.loads(content)

        except Exception as e:
            logger.error(f"❌ Error reading LSP response: {e}")

        return None

    async def analyze_file(self, file_path: Path):
        """Analyze a single Python file"""
        logger.info(f"🔍 Analyzing {file_path}")

        try:
            # Read file content
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            file_uri = f"file://{file_path}"

            # Send textDocument/didOpen
            self.request_id += 1
            did_open = {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {
                        "uri": file_uri,
                        "languageId": "python",
                        "version": 1,
                        "text": content,
                    }
                },
            }

            await self._send_notification(did_open)

            # Wait a bit for diagnostics
            await asyncio.sleep(0.5)

            # Get diagnostics
            await self._get_diagnostics(file_path, file_uri)

            # Get document symbols
            await self._get_document_symbols(file_path, file_uri)

            # Get references for functions
            await self._get_function_references(file_path, file_uri, content)

            self.result.files_analyzed += 1

        except Exception as e:
            error_msg = f"Error analyzing {file_path}: {str(e)}"
            logger.error(f"❌ {error_msg}")
            self.result.errors.append(error_msg)

    async def _get_diagnostics(self, file_path: Path, file_uri: str):
        """Get diagnostics for a file"""
        # Request diagnostics
        self.request_id += 1
        diagnostics_request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": "textDocument/diagnostic",
            "params": {"textDocument": {"uri": file_uri}},
        }

        response = await self._send_request(diagnostics_request)

        if response and "result" in response:
            items = response["result"].get("items", [])

            for item in items:
                diagnostic = LSPDiagnostic(
                    file_path=str(file_path),
                    line=item["range"]["start"]["line"] + 1,
                    column=item["range"]["start"]["character"] + 1,
                    severity=self._severity_to_string(item.get("severity", 1)),
                    message=item["message"],
                    source=item.get("source", "pylsp"),
                    code=str(item.get("code", "")) if item.get("code") else None,
                )

                self.result.diagnostics.append(diagnostic)

    async def _get_document_symbols(self, file_path: Path, file_uri: str):
        """Get document symbols (functions, classes, etc.)"""
        self.request_id += 1
        symbols_request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": "textDocument/documentSymbol",
            "params": {"textDocument": {"uri": file_uri}},
        }

        response = await self._send_request(symbols_request)

        if response and "result" in response:
            symbols = response["result"]
            self._process_symbols(str(file_path), symbols)

    def _process_symbols(self, file_path: str, symbols: List[Dict[str, Any]]):
        """Process document symbols recursively"""
        for symbol in symbols:
            symbol_name = symbol["name"]
            symbol_kind = symbol["kind"]  # Function=12, Class=5, Method=6, etc.

            location = symbol["range"]["start"]
            line = location["line"] + 1
            column = location["character"] + 1

            # Create symbol reference
            ref = SymbolReference(
                file_path=file_path,
                line=line,
                column=column,
                symbol_name=symbol_name,
                context=f"Kind: {symbol_kind}",
            )

            if symbol_name not in self.result.symbols:
                self.result.symbols[symbol_name] = []
            self.result.symbols[symbol_name].append(ref)

            # Process children (methods in classes, etc.)
            if "children" in symbol:
                self._process_symbols(file_path, symbol["children"])

    async def _get_function_references(
        self, file_path: Path, file_uri: str, content: str
    ):
        """Get references for functions in the file"""
        lines = content.split("\n")

        for line_num, line in enumerate(lines):
            # Simple pattern to find function calls
            import re

            function_calls = re.findall(r"(\w+)\s*\(", line)

            for call in function_calls:
                # Get references for this symbol
                self.request_id += 1
                refs_request = {
                    "jsonrpc": "2.0",
                    "id": self.request_id,
                    "method": "textDocument/references",
                    "params": {
                        "textDocument": {"uri": file_uri},
                        "position": {"line": line_num, "character": line.find(call)},
                        "context": {"includeDeclaration": True},
                    },
                }

                response = await self._send_request(refs_request)

                if response and "result" in response:
                    references = response["result"]

                    for ref in references:
                        ref_uri = ref["uri"]
                        ref_path = ref_uri.replace("file://", "")
                        ref_line = ref["range"]["start"]["line"] + 1
                        ref_col = ref["range"]["start"]["character"] + 1

                        # Create call graph entry
                        call_entry = FunctionCall(
                            caller=f"{file_path.name}:function",  # Simplified
                            callee=call,
                            file_path=ref_path,
                            line=ref_line,
                            column=ref_col,
                        )

                        self.result.call_graph.append(call_entry)

    def _severity_to_string(self, severity: int) -> str:
        """Convert LSP severity number to string"""
        severity_map = {1: "error", 2: "warning", 3: "info", 4: "hint"}
        return severity_map.get(severity, "info")

    async def analyze_directory(self, directory: str, recursive: bool = False):
        """Analyze all Python files in directory"""
        path = Path(directory)

        if recursive:
            python_files = list(path.rglob("*.py"))
        else:
            python_files = list(path.glob("*.py"))

        logger.info(f"🔍 Found {len(python_files)} Python files to analyze")

        # Start LSP server
        await self.start_lsp_server()

        try:
            # Analyze each file
            for file_path in python_files:
                await self.analyze_file(file_path)

        finally:
            await self.stop_lsp_server()

    async def stop_lsp_server(self):
        """Stop the LSP server"""
        if self.lsp_process:
            try:
                # Send shutdown request
                self.request_id += 1
                shutdown_request = {
                    "jsonrpc": "2.0",
                    "id": self.request_id,
                    "method": "shutdown",
                    "params": None,
                }

                await self._send_request(shutdown_request)

                # Send exit notification
                exit_notification = {"jsonrpc": "2.0", "method": "exit", "params": None}

                await self._send_notification(exit_notification)

                # Wait for process to terminate
                await asyncio.wait_for(self.lsp_process.wait(), timeout=5.0)
                logger.info("✅ LSP server stopped")

            except asyncio.TimeoutError:
                logger.warning("⚠️ LSP server didn't stop gracefully, terminating")
                self.lsp_process.terminate()
                await self.lsp_process.wait()
            except Exception as e:
                logger.error(f"❌ Error stopping LSP server: {e}")

    def print_results(self, errors_only: bool = False):
        """Print analysis results"""
        print(f"\n📊 LSP BATCH ANALYSIS RESULTS")
        print(f"{'=' * 50}")
        print(f"📁 Files analyzed: {self.result.files_analyzed}")
        print(f"🔍 Total diagnostics: {len(self.result.diagnostics)}")
        print(
            f"📦 Symbols found: {sum(len(refs) for refs in self.result.symbols.values())}"
        )
        print(f"🔗 Call graph entries: {len(self.result.call_graph)}")

        if self.result.errors:
            print(f"❌ Analysis errors: {len(self.result.errors)}")

        # Group diagnostics by severity
        diagnostics_by_severity = {}
        for diag in self.result.diagnostics:
            if diag.severity not in diagnostics_by_severity:
                diagnostics_by_severity[diag.severity] = []
            diagnostics_by_severity[diag.severity].append(diag)

        # Print diagnostics summary
        for severity in ["error", "warning", "info", "hint"]:
            if severity in diagnostics_by_severity:
                count = len(diagnostics_by_severity[severity])
                icon = {"error": "🔴", "warning": "🟡", "info": "🔵", "hint": "⚪"}.get(
                    severity, "📍"
                )
                print(f"{icon} {severity.title()}s: {count}")

        # Show errors (compilation issues)
        if "error" in diagnostics_by_severity:
            print(f"\n🔴 COMPILATION ERRORS:")
            for diag in diagnostics_by_severity["error"][:10]:  # Show first 10
                file_name = Path(diag.file_path).name
                print(f"   {file_name}:{diag.line}:{diag.column} - {diag.message}")
                if diag.source != "pylsp":
                    print(f"      Source: {diag.source}")

            if len(diagnostics_by_severity["error"]) > 10:
                remaining = len(diagnostics_by_severity["error"]) - 10
                print(f"   ... and {remaining} more errors")

        # Show warnings if not errors-only mode
        if not errors_only and "warning" in diagnostics_by_severity:
            print(f"\n🟡 WARNINGS:")
            for diag in diagnostics_by_severity["warning"][:5]:  # Show first 5
                file_name = Path(diag.file_path).name
                print(f"   {file_name}:{diag.line}:{diag.column} - {diag.message}")

            if len(diagnostics_by_severity["warning"]) > 5:
                remaining = len(diagnostics_by_severity["warning"]) - 5
                print(f"   ... and {remaining} more warnings")

        # Show most common symbols
        if not errors_only and self.result.symbols:
            print(f"\n📦 MOST COMMON SYMBOLS:")
            symbol_counts = [
                (name, len(refs)) for name, refs in self.result.symbols.items()
            ]
            symbol_counts.sort(key=lambda x: x[1], reverse=True)

            for symbol_name, count in symbol_counts[:5]:
                print(f"   {symbol_name}: {count} occurrences")

    def export_json(self, output_file: str):
        """Export results to JSON"""

        def convert_to_dict(obj):
            """Convert dataclass to dict"""
            if hasattr(obj, "__dict__"):
                result = {}
                for key, value in obj.__dict__.items():
                    if isinstance(value, list):
                        result[key] = [convert_to_dict(item) for item in value]
                    elif isinstance(value, dict):
                        result[key] = {k: convert_to_dict(v) for k, v in value.items()}
                    elif hasattr(value, "__dict__"):
                        result[key] = convert_to_dict(value)
                    else:
                        result[key] = value
                return result
            return obj

        output_data = convert_to_dict(self.result)

        with open(output_file, "w") as f:
            json.dump(output_data, f, indent=2)

        print(f"📄 Results exported to: {output_file}")

    def has_compilation_errors(self) -> bool:
        """Check if there are any compilation errors"""
        return any(diag.severity == "error" for diag in self.result.diagnostics)


async def main():
    parser = argparse.ArgumentParser(
        description="Batch LSP Analyzer using pylsp",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python lsp_batch_analyzer.py                    # Analyze current directory
    python lsp_batch_analyzer.py --recursive        # Analyze recursively
    python lsp_batch_analyzer.py --check-errors     # Only show compilation errors
    python lsp_batch_analyzer.py --export results.json  # Export to JSON
    python lsp_batch_analyzer.py --directory /path/to/code  # Analyze specific directory
        """,
    )

    parser.add_argument("--directory", "-d", default=".", help="Directory to analyze")
    parser.add_argument(
        "--recursive", "-r", action="store_true", help="Analyze recursively"
    )
    parser.add_argument(
        "--check-errors", action="store_true", help="Only show compilation errors"
    )
    parser.add_argument("--export", "-o", help="Export results to JSON file")
    parser.add_argument(
        "--quiet", "-q", action="store_true", help="Reduce output verbosity"
    )

    args = parser.parse_args()

    if args.quiet:
        logger.setLevel(logging.WARNING)

    print("📡 LSP Batch Analyzer")
    print("Using pylsp for comprehensive code analysis")
    print("=" * 50)

    # Check if pylsp is available
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pylsp", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            print("❌ pylsp not found. Install with: pip install python-lsp-server")
            return 1
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("❌ pylsp not found. Install with: pip install python-lsp-server")
        return 1

    print("✅ pylsp found and available")

    # Initialize analyzer
    analyzer = LSPBatchAnalyzer(args.directory)

    try:
        # Run analysis
        await analyzer.analyze_directory(args.directory, args.recursive)

        # Print results
        analyzer.print_results(errors_only=args.check_errors)

        # Export if requested
        if args.export:
            analyzer.export_json(args.export)

        # Return exit code based on compilation errors
        if analyzer.has_compilation_errors():
            print(f"\n❌ Analysis completed with compilation errors")
            return 1
        else:
            print(f"\n✅ Analysis completed successfully")
            return 0

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
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Fatal error: {e}")
        sys.exit(1)
