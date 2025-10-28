#!/usr/bin/env python3
"""
Post-Patch Validation System

This module provides comprehensive validation checks after applying patches to code.
Supports syntax checking, linting, type checking, and test execution for multiple languages.
"""

import os
import sys
import subprocess
import json
import tempfile
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a validation check"""

    check_type: str
    success: bool
    messages: List[str]
    warnings: List[str] = None
    errors: List[str] = None
    execution_time: float = 0.0
    details: Dict[str, Any] = None
    changed_lines_only: bool = False

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.errors is None:
            self.errors = []
        if self.details is None:
            self.details = {}


@dataclass
class ValidationSummary:
    """Summary of all validation results"""

    total_checks: int
    passed_checks: int
    failed_checks: int
    warnings_count: int
    errors_count: int
    results: List[ValidationResult]
    overall_success: bool = False

    def __post_init__(self):
        self.overall_success = self.failed_checks == 0


class ValidationCheck(ABC):
    """Abstract base class for validation checks"""

    def __init__(self, name: str, description: str, required: bool = True):
        self.name = name
        self.description = description
        self.required = required

    @abstractmethod
    def can_validate(self, file_path: str) -> bool:
        """Check if this validator can handle the given file"""
        pass

    @abstractmethod
    def validate(
        self, file_path: str, content: str = None, changed_lines: List[int] = None
    ) -> ValidationResult:
        """Perform the validation check"""
        pass

    def _is_relevant_to_changes(
        self, line_number: int, changed_lines: List[int] = None
    ) -> bool:
        """Check if an error/warning on a given line is relevant to the changes made"""
        if not changed_lines:
            return True  # If no changed lines specified, show all issues

        # Allow some tolerance around changed lines to catch related issues
        tolerance = 2
        for changed_line in changed_lines:
            if abs(line_number - changed_line) <= tolerance:
                return True
        return False

    def _extract_line_number(self, error_message: str) -> Optional[int]:
        """Extract line number from error/warning message"""
        import re

        # Common patterns for line numbers in various tools
        patterns = [
            r":(\d+):",  # file.py:123: error
            r"line (\d+)",  # line 123
            r"\((\d+)\)",  # (123)
            r"@(\d+)",  # @123
        ]

        for pattern in patterns:
            match = re.search(pattern, error_message)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    continue

        return None

    def _filter_issues_by_changed_lines(
        self, issues: List[str], changed_lines: List[int] = None
    ) -> List[str]:
        """Filter issues to only include those related to changed lines"""
        if not changed_lines or not issues:
            return issues

        filtered_issues = []
        for issue in issues:
            line_num = self._extract_line_number(issue)
            if line_num is None or self._is_relevant_to_changes(
                line_num, changed_lines
            ):
                filtered_issues.append(issue)

        return filtered_issues

    def _run_command(
        self, cmd: List[str], cwd: str = None, input_data: str = None
    ) -> Tuple[int, str, str]:
        """Run a command and return exit code, stdout, stderr"""
        try:
            process = subprocess.run(
                cmd,
                cwd=cwd,
                input=input_data,
                text=True,
                capture_output=True,
                timeout=30,
            )
            return process.returncode, process.stdout, process.stderr
        except subprocess.TimeoutExpired:
            return 1, "", "Command timed out after 30 seconds"
        except FileNotFoundError:
            return 1, "", f"Command not found: {cmd[0]}"
        except Exception as e:
            return 1, "", f"Error running command: {e}"


class PythonSyntaxCheck(ValidationCheck):
    """Python syntax validation using ast module"""

    def __init__(self):
        super().__init__("python_syntax", "Python syntax validation", required=True)

    def can_validate(self, file_path: str) -> bool:
        return file_path.endswith(".py")

    def validate(
        self, file_path: str, content: str = None, changed_lines: List[int] = None
    ) -> ValidationResult:
        import ast
        import time

        start_time = time.time()

        try:
            if content is None:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

            # Parse the syntax
            ast.parse(content, filename=file_path)

            execution_time = time.time() - start_time
            return ValidationResult(
                check_type=self.name,
                success=True,
                messages=[f"✅ Python syntax is valid"],
                execution_time=execution_time,
            )

        except SyntaxError as e:
            execution_time = time.time() - start_time
            error_msg = f"Syntax error at line {e.lineno}: {e.msg}"
            return ValidationResult(
                check_type=self.name,
                success=False,
                messages=[f"❌ Python syntax error"],
                errors=[error_msg],
                execution_time=execution_time,
                details={"line": e.lineno, "column": e.offset, "error": e.msg},
            )
        except Exception as e:
            execution_time = time.time() - start_time
            return ValidationResult(
                check_type=self.name,
                success=False,
                messages=[f"❌ Python syntax check failed"],
                errors=[str(e)],
                execution_time=execution_time,
            )


class PythonCompileCheck(ValidationCheck):
    """Python compilation check using py_compile"""

    def __init__(self):
        super().__init__("python_compile", "Python compilation check", required=True)

    def can_validate(self, file_path: str) -> bool:
        return file_path.endswith(".py")

    def validate(
        self, file_path: str, content: str = None, changed_lines: List[int] = None
    ) -> ValidationResult:
        import py_compile
        import time

        start_time = time.time()

        try:
            if content is not None:
                # Write content to temporary file for compilation
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".py", delete=False
                ) as tmp_file:
                    tmp_file.write(content)
                    temp_path = tmp_file.name

                try:
                    py_compile.compile(temp_path, doraise=True)
                    success = True
                    messages = ["✅ Python code compiles successfully"]
                    errors = []
                finally:
                    os.unlink(temp_path)
            else:
                py_compile.compile(file_path, doraise=True)
                success = True
                messages = ["✅ Python code compiles successfully"]
                errors = []

            execution_time = time.time() - start_time
            return ValidationResult(
                check_type=self.name,
                success=success,
                messages=messages,
                errors=errors,
                execution_time=execution_time,
            )

        except py_compile.PyCompileError as e:
            execution_time = time.time() - start_time
            return ValidationResult(
                check_type=self.name,
                success=False,
                messages=["❌ Python compilation failed"],
                errors=[str(e)],
                execution_time=execution_time,
            )


class PythonFlake8Check(ValidationCheck):
    """Python linting using flake8"""

    def __init__(self):
        super().__init__("python_flake8", "Python linting with flake8", required=False)

    def can_validate(self, file_path: str) -> bool:
        return file_path.endswith(".py")

    def validate(
        self, file_path: str, content: str = None, changed_lines: List[int] = None
    ) -> ValidationResult:
        import time

        start_time = time.time()

        if content is not None:
            # Use stdin for content
            exit_code, stdout, stderr = self._run_command(
                ["flake8", "--stdin-display-name", file_path, "-"], input_data=content
            )
        else:
            exit_code, stdout, stderr = self._run_command(["flake8", file_path])

        execution_time = time.time() - start_time

        if exit_code == 1 and "command not found" in stderr:
            return ValidationResult(
                check_type=self.name,
                success=True,
                messages=["⚠️ flake8 not available - skipping lint check"],
                warnings=["Install flake8 for Python linting: pip install flake8"],
                execution_time=execution_time,
            )

        if exit_code == 0:
            return ValidationResult(
                check_type=self.name,
                success=True,
                messages=["✅ No linting issues found"],
                execution_time=execution_time,
            )
        else:
            issues = stdout.strip().split("\n") if stdout.strip() else []
            warnings = [
                issue for issue in issues if any(code in issue for code in ["W", "C"])
            ]
            errors = [
                issue for issue in issues if any(code in issue for code in ["E", "F"])
            ]

            # Filter issues by changed lines
            filtered_warnings = self._filter_issues_by_changed_lines(
                warnings, changed_lines
            )
            filtered_errors = self._filter_issues_by_changed_lines(
                errors, changed_lines
            )

            return ValidationResult(
                check_type=self.name,
                success=len(filtered_errors) == 0,
                messages=[
                    f"{'✅' if len(filtered_errors) == 0 else '❌'} Flake8 linting completed"
                ],
                warnings=filtered_warnings,
                errors=filtered_errors,
                execution_time=execution_time,
                details={
                    "issues_count": len(issues),
                    "filtered_count": len(filtered_warnings) + len(filtered_errors),
                    "changed_lines_only": changed_lines is not None,
                },
                changed_lines_only=changed_lines is not None,
            )


class PythonMypyCheck(ValidationCheck):
    """Python type checking using mypy"""

    def __init__(self):
        super().__init__(
            "python_mypy", "Python type checking with mypy", required=False
        )

    def can_validate(self, file_path: str) -> bool:
        return file_path.endswith(".py")

    def validate(
        self, file_path: str, content: str = None, changed_lines: List[int] = None
    ) -> ValidationResult:
        import time

        start_time = time.time()

        if content is not None:
            # Write to temp file for mypy
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False
            ) as tmp_file:
                tmp_file.write(content)
                temp_path = tmp_file.name

            try:
                exit_code, stdout, stderr = self._run_command(
                    ["mypy", "--ignore-missing-imports", temp_path]
                )
            finally:
                os.unlink(temp_path)
        else:
            exit_code, stdout, stderr = self._run_command(
                ["mypy", "--ignore-missing-imports", file_path]
            )

        execution_time = time.time() - start_time

        if exit_code == 1 and "command not found" in stderr:
            return ValidationResult(
                check_type=self.name,
                success=True,
                messages=["⚠️ mypy not available - skipping type check"],
                warnings=["Install mypy for Python type checking: pip install mypy"],
                execution_time=execution_time,
            )

        if exit_code == 0:
            return ValidationResult(
                check_type=self.name,
                success=True,
                messages=["✅ No type checking issues found"],
                execution_time=execution_time,
            )
        else:
            issues = stdout.strip().split("\n") if stdout.strip() else []
            # Filter issues by changed lines
            filtered_errors = self._filter_issues_by_changed_lines(
                issues, changed_lines
            )

            return ValidationResult(
                check_type=self.name,
                success=len(filtered_errors) == 0,
                messages=[
                    f"{'✅' if len(filtered_errors) == 0 else '❌'} Type checking completed"
                ],
                errors=filtered_errors,
                execution_time=execution_time,
                details={
                    "issues_count": len(issues),
                    "filtered_count": len(filtered_errors),
                    "changed_lines_only": changed_lines is not None,
                },
                changed_lines_only=changed_lines is not None,
            )


class PythonTestRunner(ValidationCheck):
    """Python test runner for pytest/unittest"""

    def __init__(self):
        super().__init__("python_tests", "Python test execution", required=False)

    def can_validate(self, file_path: str) -> bool:
        return file_path.endswith(".py") and (
            "test_" in file_path or file_path.endswith("_test.py")
        )

    def validate(
        self, file_path: str, content: str = None, changed_lines: List[int] = None
    ) -> ValidationResult:
        import time

        start_time = time.time()

        # Try pytest first, then unittest
        for test_cmd in [["pytest", "-v"], ["python", "-m", "unittest", "-v"]]:
            if content is not None:
                # For content-based testing, write to temp file
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".py", delete=False
                ) as tmp_file:
                    tmp_file.write(content)
                    temp_path = tmp_file.name

                try:
                    if test_cmd[0] == "pytest":
                        exit_code, stdout, stderr = self._run_command(
                            test_cmd + [temp_path]
                        )
                    else:
                        # Extract test module name for unittest
                        module_name = os.path.splitext(os.path.basename(temp_path))[0]
                        exit_code, stdout, stderr = self._run_command(
                            ["python", "-m", "unittest", module_name],
                            cwd=os.path.dirname(temp_path),
                        )
                finally:
                    os.unlink(temp_path)
            else:
                if test_cmd[0] == "pytest":
                    exit_code, stdout, stderr = self._run_command(
                        test_cmd + [file_path]
                    )
                else:
                    # Convert file path to module for unittest
                    module_name = os.path.splitext(os.path.basename(file_path))[0]
                    exit_code, stdout, stderr = self._run_command(
                        ["python", "-m", "unittest", module_name],
                        cwd=os.path.dirname(file_path),
                    )

            execution_time = time.time() - start_time

            if exit_code == 1 and "command not found" in stderr:
                continue  # Try next test runner

            if exit_code == 0:
                return ValidationResult(
                    check_type=self.name,
                    success=True,
                    messages=[f"✅ All tests passed using {test_cmd[0]}"],
                    execution_time=execution_time,
                    details={"test_runner": test_cmd[0], "output": stdout},
                )
            else:
                return ValidationResult(
                    check_type=self.name,
                    success=False,
                    messages=[f"❌ Tests failed using {test_cmd[0]}"],
                    errors=[stderr] if stderr else [stdout],
                    execution_time=execution_time,
                    details={"test_runner": test_cmd[0]},
                )

        # No test runners available
        execution_time = time.time() - start_time
        return ValidationResult(
            check_type=self.name,
            success=True,
            messages=["⚠️ No test runners available - skipping tests"],
            warnings=["Install pytest or ensure unittest is available"],
            execution_time=execution_time,
        )


class ValidationEngine:
    """Main validation engine that coordinates all checks"""

    def __init__(self):
        self.validators: List[ValidationCheck] = []
        self._register_default_validators()

    def _register_default_validators(self):
        """Register default validators for different languages"""
        # Python validators
        self.validators.extend(
            [
                PythonSyntaxCheck(),
                PythonCompileCheck(),
                PythonFlake8Check(),
                PythonMypyCheck(),
                PythonTestRunner(),
            ]
        )

    def add_validator(self, validator: ValidationCheck):
        """Add a custom validator"""
        self.validators.append(validator)

    def get_applicable_validators(self, file_path: str) -> List[ValidationCheck]:
        """Get validators that can handle the given file"""
        return [v for v in self.validators if v.can_validate(file_path)]

    def validate_file(
        self,
        file_path: str,
        content: str = None,
        required_only: bool = False,
        changed_lines: List[int] = None,
    ) -> ValidationSummary:
        """Validate a single file using all applicable validators"""
        applicable_validators = self.get_applicable_validators(file_path)

        if required_only:
            applicable_validators = [v for v in applicable_validators if v.required]

        if not applicable_validators:
            return ValidationSummary(
                total_checks=0,
                passed_checks=0,
                failed_checks=0,
                warnings_count=0,
                errors_count=0,
                results=[],
                overall_success=True,
            )

        results = []
        for validator in applicable_validators:
            try:
                result = validator.validate(file_path, content, changed_lines)
                results.append(result)
            except Exception as e:
                # Create error result if validator fails
                results.append(
                    ValidationResult(
                        check_type=validator.name,
                        success=False,
                        messages=[f"❌ Validator {validator.name} failed"],
                        errors=[f"Internal error: {e}"],
                    )
                )

        # Calculate summary
        passed = sum(1 for r in results if r.success)
        failed = len(results) - passed
        total_warnings = sum(len(r.warnings) for r in results)
        total_errors = sum(len(r.errors) for r in results)

        return ValidationSummary(
            total_checks=len(results),
            passed_checks=passed,
            failed_checks=failed,
            warnings_count=total_warnings,
            errors_count=total_errors,
            results=results,
        )

    def validate_files(
        self,
        file_paths: List[str],
        contents: Dict[str, str] = None,
        required_only: bool = False,
        changed_lines_map: Dict[str, List[int]] = None,
    ) -> Dict[str, ValidationSummary]:
        """Validate multiple files"""
        results = {}
        for file_path in file_paths:
            content = contents.get(file_path) if contents else None
            changed_lines = (
                changed_lines_map.get(file_path) if changed_lines_map else None
            )
            results[file_path] = self.validate_file(
                file_path, content, required_only, changed_lines
            )
        return results

    def format_results(self, results: ValidationSummary, verbose: bool = False) -> str:
        """Format validation results for display"""
        output = []

        if results.total_checks == 0:
            return "ℹ️ No applicable validation checks found"

        # Summary
        status_icon = "✅" if results.overall_success else "❌"
        output.append(
            f"{status_icon} Validation Summary: {results.passed_checks}/{results.total_checks} checks passed"
        )

        if results.warnings_count > 0:
            output.append(f"⚠️ Warnings: {results.warnings_count}")

        if results.errors_count > 0:
            output.append(f"❌ Errors: {results.errors_count}")

        # Detailed results
        if verbose or not results.overall_success:
            output.append("\n📋 Detailed Results:")
            for result in results.results:
                output.append(f"\n🔧 {result.check_type}:")
                for message in result.messages:
                    output.append(f"   {message}")

                if result.warnings:
                    for warning in result.warnings:
                        output.append(f"   ⚠️ {warning}")

                if result.errors:
                    for error in result.errors:
                        output.append(f"   ❌ {error}")

                if result.execution_time > 0:
                    output.append(f"   ⏱️ Execution time: {result.execution_time:.2f}s")

        return "\n".join(output)


# Convenience functions for integration with Logan
def validate_python_file(
    file_path: str,
    content: str = None,
    required_only: bool = False,
    changed_lines: List[int] = None,
) -> ValidationSummary:
    """Validate a Python file - convenience function"""
    engine = ValidationEngine()
    return engine.validate_file(file_path, content, required_only, changed_lines)


def validate_patched_files(
    file_paths: List[str],
    contents: Dict[str, str] = None,
    required_only: bool = True,
    changed_lines_map: Dict[str, List[int]] = None,
) -> Dict[str, ValidationSummary]:
    """Validate multiple files after patching - main integration point for Logan"""
    engine = ValidationEngine()
    return engine.validate_files(file_paths, contents, required_only, changed_lines_map)


if __name__ == "__main__":
    # Example usage
    import argparse

    parser = argparse.ArgumentParser(description="Validate code files")
    parser.add_argument("files", nargs="+", help="Files to validate")
    parser.add_argument(
        "--required-only", action="store_true", help="Run only required checks"
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    engine = ValidationEngine()

    for file_path in args.files:
        if os.path.exists(file_path):
            print(f"\n🔍 Validating: {file_path}")
            print("=" * 50)

            summary = engine.validate_file(file_path, required_only=args.required_only)
            print(engine.format_results(summary, verbose=args.verbose))
        else:
            print(f"❌ File not found: {file_path}")
