#!/usr/bin/env python3
"""
Dulwich Remote Repository Analyzer

Simple remote Git repository analyzer using dulwich (pure Python Git).
No local clones required - fetches only what's needed for analysis.

Dependencies:
    pip install dulwich

Usage:
    python dulwich_analyzer.py --repo https://github.com/user/repo
    python dulwich_analyzer.py --repo https://git.example.com/project.git --username user --password pass
    python dulwich_analyzer.py --repo git@github.com:user/repo.git --search "async.*"
"""

import os
import sys
import json
import argparse
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, asdict
import time
import re
import fnmatch
from urllib.parse import urlparse

# Dulwich Git library
try:
    from dulwich import porcelain
    from dulwich.repo import Repo
    from dulwich.client import get_transport_and_path, HTTPUnauthorized
    from dulwich.errors import NotGitRepository, GitProtocolError
    import dulwich.client
    from urllib.parse import urlparse, urlunparse

    DULWICH_AVAILABLE = True
except ImportError:
    print("❌ dulwich not available. Install with: pip install dulwich")
    DULWICH_AVAILABLE = False
    sys.exit(1)

# Import combined analyzer
try:
    from combined_cli_analyzer import CombinedAnalyzer, get_exclusion_preset

    COMBINED_ANALYZER_AVAILABLE = True
except ImportError:
    print("⚠️  Combined analyzer not found. Limited functionality available.")
    COMBINED_ANALYZER_AVAILABLE = False


@dataclass
class RemoteRepoInfo:
    """Information about remote repository"""

    url: str
    branch: str = "main"
    commit_sha: Optional[str] = None
    temp_dir: Optional[str] = None


class DulwichAnalyzer:
    """Remote Git repository analyzer using dulwich"""

    def __init__(
        self,
        verbose: bool = False,
        exclude_patterns: List[str] = None,
        username: str = None,
        password: str = None,
    ):
        self.verbose = verbose
        self.exclude_patterns = exclude_patterns or []
        self.username = username
        self.password = password
        self.repo_info: Optional[RemoteRepoInfo] = None
        self.temp_dir: Optional[str] = None

    def _log(self, message: str, force: bool = False):
        """Log message if verbose mode is enabled"""
        if self.verbose or force:
            print(message)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def cleanup(self):
        """Clean up temporary files"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                self._log(f"🧹 Cleaned up: {self.temp_dir}")
                self.temp_dir = None
            except Exception as e:
                self._log(f"⚠️  Cleanup warning: {e}")

    def clone_repository(self, repo_url: str, branch: str = None) -> bool:
        """Clone repository to temporary directory using dulwich"""
        try:
            self.repo_info = RemoteRepoInfo(url=repo_url, branch=branch or "main")
            self.temp_dir = tempfile.mkdtemp(prefix="dulwich_analyzer_")

            self._log(f"📥 Cloning: {repo_url}")
            self._log(f"📁 Target: {self.temp_dir}")
            self._log(f"🌿 Branch: {self.repo_info.branch}")

            # Setup authentication by modifying URL if provided
            clone_url = repo_url
            if self.username and self.password:
                self._log("🔐 Setting up basic authentication")
                parsed = urlparse(repo_url)
                if parsed.scheme in ("http", "https"):
                    # Embed credentials in URL
                    netloc = f"{self.username}:{self.password}@{parsed.hostname}"
                    if parsed.port:
                        netloc += f":{parsed.port}"
                    clone_url = urlunparse(parsed._replace(netloc=netloc))
                    self._log(f"🔐 Authentication configured for {parsed.hostname}")
                    if self.verbose:
                        # Show URL without password
                        safe_netloc = f"{self.username}:***@{parsed.hostname}"
                        if parsed.port:
                            safe_netloc += f":{parsed.port}"
                        safe_url = urlunparse(parsed._replace(netloc=safe_netloc))
                        self._log(f"   Using URL: {safe_url}")
                else:
                    self._log("⚠️  Basic auth only works with HTTP/HTTPS URLs")
            else:
                self._log("ℹ️  No authentication provided - trying anonymous access")

            # Try to clone with specified branch
            try:
                porcelain.clone(
                    source=clone_url,
                    target=self.temp_dir,
                    branch=self.repo_info.branch.encode("utf-8"),
                    depth=1,  # Shallow clone
                )
                self._log("✅ Repository cloned successfully")

            except Exception as e:
                if "branch" in str(e).lower() or "reference" in str(e).lower():
                    self._log(f"❌ Branch '{self.repo_info.branch}' not found: {e}")
                    self._log("🔄 Trying default branches...")

                    # Try common default branches
                    for default_branch in ["main", "master", "develop"]:
                        try:
                            self._log(f"   Trying branch: {default_branch}")
                            # Clean up failed attempt
                            if os.path.exists(self.temp_dir):
                                shutil.rmtree(self.temp_dir)
                            self.temp_dir = tempfile.mkdtemp(prefix="dulwich_analyzer_")

                            porcelain.clone(
                                source=clone_url,
                                target=self.temp_dir,
                                branch=default_branch.encode("utf-8"),
                                depth=1,
                            )
                            self.repo_info.branch = default_branch
                            self._log(
                                f"✅ Successfully cloned branch: {default_branch}"
                            )
                            break

                        except Exception as branch_error:
                            self._log(f"   Failed: {branch_error}")
                            continue
                    else:
                        # If all branches fail, try without specifying branch
                        self._log("🔄 Trying default branch (auto-detect)...")
                        if os.path.exists(self.temp_dir):
                            shutil.rmtree(self.temp_dir)
                        self.temp_dir = tempfile.mkdtemp(prefix="dulwich_analyzer_")

                        porcelain.clone(
                            source=clone_url,
                            target=self.temp_dir,
                            depth=1,
                        )
                        self._log("✅ Repository cloned with default branch")
                else:
                    raise

            # Get current commit info
            try:
                repo = Repo(self.temp_dir)
                head = repo.head()
                commit = repo[head]
                self.repo_info.commit_sha = head.decode("utf-8")

                author_info = f"{commit.author.decode('utf-8', errors='replace')}"
                message = commit.message.decode("utf-8", errors="replace").strip()

                self._log(f"📝 Commit: {self.repo_info.commit_sha[:8]}")
                self._log(f"   Author: {author_info}")
                self._log(f"   Message: {message[:60]}...")

            except Exception as e:
                self._log(f"⚠️  Could not get commit info: {e}")

            self.repo_info.temp_dir = self.temp_dir
            return True

        except Exception as e:
            self._log(f"❌ Clone failed: {e}", force=True)
            self._log(f"   Error type: {type(e).__name__}")

            error_str = str(e).lower()
            if (
                "auth" in error_str
                or "credential" in error_str
                or "unauthorized" in error_str
            ):
                self._log("💡 Authentication failed. Check:")
                self._log("   - Username and password are correct")
                self._log("   - Repository requires authentication")
                self._log("   - Account has access to this repository")
            elif "not found" in error_str or "404" in error_str:
                self._log("💡 Repository not found. Check:")
                self._log("   - Repository URL is correct")
                self._log("   - Repository exists and is accessible")
            elif "ssl" in error_str or "certificate" in error_str:
                self._log("💡 SSL certificate issue with the remote server")
            elif "timeout" in error_str:
                self._log("💡 Connection timeout - check network connectivity")
            elif "no valid credentials" in error_str:
                self._log("💡 Authentication required. Use:")
                self._log("   --username USER --password PASS")
                self._log("   or --auth USER:PASS")

            self.cleanup()
            return False

    def get_python_files(self) -> List[str]:
        """Get list of Python files in the repository"""
        if not self.temp_dir or not os.path.exists(self.temp_dir):
            return []

        python_files = []
        repo_path = Path(self.temp_dir)

        for py_file in repo_path.rglob("*.py"):
            relative_path = py_file.relative_to(repo_path)

            if not self._should_exclude(str(relative_path)):
                python_files.append(str(py_file))
            else:
                self._log(f"🚫 Excluded: {relative_path}")

        return python_files

    def _should_exclude(self, file_path: str) -> bool:
        """Check if file should be excluded"""
        if not self.exclude_patterns:
            return False

        file_path_normalized = file_path.replace("\\", "/")
        path_parts = file_path_normalized.split("/")

        for pattern in self.exclude_patterns:
            # Direct match
            if fnmatch.fnmatch(file_path_normalized, pattern):
                return True
            # Directory match
            for part in path_parts:
                if fnmatch.fnmatch(part, pattern):
                    return True
            # Wildcard patterns
            if fnmatch.fnmatch(
                file_path_normalized, f"*/{pattern}/*"
            ) or fnmatch.fnmatch(file_path_normalized, f"*/{pattern}"):
                return True

        return False

    def analyze_with_combined_analyzer(
        self,
        search_pattern: str = None,
        preview_target: str = None,
        search_type: str = "both",
        list_functions: bool = False,
        list_classes: bool = False,
        detailed: bool = False,
    ) -> Dict[str, Any]:
        """Analyze using combined analyzer"""
        if not COMBINED_ANALYZER_AVAILABLE:
            return {"error": "Combined analyzer not available"}

        if not self.temp_dir or not os.path.exists(self.temp_dir):
            return {"error": "Repository not cloned"}

        try:
            python_files = self.get_python_files()
            self._log(f"📊 Analyzing {len(python_files)} Python files")

            if not python_files:
                return {"error": "No Python files found"}

            # Initialize analyzer
            analyzer = CombinedAnalyzer(
                verbose=self.verbose,
                show_full_paths=True,
                exclude_patterns=[],  # Already filtered
            )

            # Run analysis
            self._log("🔍 Running analysis...")
            results = analyzer.analyze_directory(
                directory=self.temp_dir,
                recursive=True,
                run_treesitter=True,
                run_callgraph=True,
            )

            # Execute specific commands
            if search_pattern:
                self._log(f"🔍 Searching: {search_pattern}")
                print()
                analyzer.search_combined(search_pattern, search_type=search_type)

            elif preview_target:
                self._log(f"📖 Previewing: {preview_target}")
                print()
                analyzer.preview_method(preview_target)

            elif list_functions:
                self._log("📋 Listing functions...")
                print()
                analyzer.list_available_functions()

            elif list_classes:
                self._log("📋 Listing classes...")
                print()
                analyzer.list_available_classes()

            else:
                # Default summary
                analyzer.print_summary(results, detailed=detailed)

            return {
                "success": True,
                "files_analyzed": len(python_files),
                "repo_info": asdict(self.repo_info) if self.repo_info else None,
            }

        except Exception as e:
            error_msg = f"Analysis failed: {e}"
            self._log(error_msg, force=True)
            return {"error": error_msg}


def main():
    parser = argparse.ArgumentParser(
        description="Dulwich Remote Repository Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python dulwich_analyzer.py --repo https://github.com/user/repo
    python dulwich_analyzer.py --repo https://git.example.com/project.git --username user --password pass
    python dulwich_analyzer.py --repo git@github.com:user/repo.git --search "async.*"
    python dulwich_analyzer.py --repo user/repo --list-functions --exclude-preset dev
        """,
    )

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
    parser.add_argument("--detailed", action="store_true", help="Detailed output")

    # Exclusions
    parser.add_argument("--exclude", nargs="+", help="Exclude patterns")
    parser.add_argument(
        "--exclude-preset", choices=["dev", "minimal", "comprehensive", "library"]
    )

    # Options
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Parse auth
    username = args.username
    password = args.password
    if args.auth and ":" in args.auth:
        username, password = args.auth.split(":", 1)

    # Parse exclusions
    exclude_patterns = []
    if args.exclude:
        exclude_patterns.extend(args.exclude)
    if args.exclude_preset:
        exclude_patterns.extend(get_exclusion_preset(args.exclude_preset))

    print("🚀 Dulwich Remote Repository Analyzer")
    print("=" * 50)

    # Analyze
    with DulwichAnalyzer(
        verbose=args.verbose,
        exclude_patterns=exclude_patterns,
        username=username,
        password=password,
    ) as analyzer:
        # Clone repository
        if not analyzer.clone_repository(args.repo, args.branch):
            return 1

        # Determine analysis type
        search_pattern = None
        search_type = "both"

        if args.search:
            search_pattern = args.search
            search_type = "both"
        elif args.search_functions:
            search_pattern = args.search_functions
            search_type = "functions"
        elif args.search_classes:
            search_pattern = args.search_classes
            search_type = "classes"

        # Run analysis
        result = analyzer.analyze_with_combined_analyzer(
            search_pattern=search_pattern,
            preview_target=args.preview,
            search_type=search_type,
            list_functions=args.list_functions,
            list_classes=args.list_classes,
            detailed=args.detailed,
        )

        if "error" in result:
            print(f"❌ {result['error']}")
            return 1

        if result.get("success"):
            print(f"\n✅ Analysis complete!")
            print(f"📊 Files: {result.get('files_analyzed', 0)}")

        return 0


if __name__ == "__main__":
    if not DULWICH_AVAILABLE:
        print("❌ dulwich required: pip install dulwich")
        sys.exit(1)

    sys.exit(main())
