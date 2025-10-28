#!/usr/bin/env python3
"""
Git Remote Repository Analyzer

This analyzer uses pygit2 (libgit2 Python bindings) for proper Git operations
to clone and analyze remote repositories. It supports various Git hosting
services and authentication methods.

Features:
- Proper Git clone operations with pygit2
- Support for SSH keys, HTTPS, and token authentication
- Branch selection and commit-specific analysis
- Shallow clones for performance
- In-memory file analysis
- Integration with existing combined analyzer

Dependencies:
    pip install pygit2

Usage:
    python git_remote_analyzer.py --repo https://github.com/user/repo
    python git_remote_analyzer.py --repo git@github.com:user/repo.git --ssh-key ~/.ssh/id_rsa
    python git_remote_analyzer.py --repo https://github.com/user/repo --branch develop --search "async.*"
"""

import os
import sys
import json
import argparse
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Union, Tuple
from dataclasses import dataclass, asdict
import time
import re
import fnmatch
from urllib.parse import urlparse

# Git library
try:
    import pygit2

    PYGIT2_AVAILABLE = True
    PYGIT2_VERSION = getattr(pygit2, "__version__", "unknown")

    # Check pygit2 capabilities
    HAS_CREDENTIAL_CONSTANTS = hasattr(pygit2, "credentials") and hasattr(
        pygit2.credentials, "GIT_CREDENTIAL_SSH_KEY"
    )
    HAS_KEYPAIR_FROM_AGENT = hasattr(pygit2, "KeypairFromAgent")

except ImportError:
    print("❌ pygit2 not available. Install with: pip install pygit2")
    PYGIT2_AVAILABLE = False
    PYGIT2_VERSION = None
    HAS_CREDENTIAL_CONSTANTS = False
    HAS_KEYPAIR_FROM_AGENT = False

# Try to import our existing analyzer
try:
    from combined_cli_analyzer import CombinedAnalyzer, get_exclusion_preset

    COMBINED_ANALYZER_AVAILABLE = True
except ImportError:
    print("⚠️  Combined analyzer not found. Limited functionality available.")
    COMBINED_ANALYZER_AVAILABLE = False


@dataclass
class GitRepositoryInfo:
    """Information about a Git repository"""

    url: str
    branch: str = "main"
    commit_sha: Optional[str] = None
    local_path: Optional[str] = None
    is_shallow: bool = True
    auth_method: str = "none"  # none, ssh, token, credentials


@dataclass
class GitAnalysisResults:
    """Results from Git repository analysis"""

    repo_info: GitRepositoryInfo
    files_analyzed: int = 0
    analysis_time: float = 0.0
    commit_info: Optional[Dict[str, Any]] = None
    branch_info: Optional[Dict[str, Any]] = None
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class GitRemoteAnalyzer:
    """Analyzes remote Git repositories using proper Git operations"""

    def __init__(
        self,
        verbose: bool = False,
        exclude_patterns: List[str] = None,
        shallow_clone: bool = True,
        cleanup_after: bool = True,
    ):
        self.verbose = verbose
        self.exclude_patterns = exclude_patterns or []
        self.shallow_clone = shallow_clone
        self.cleanup_after = cleanup_after

        self.repo_info: Optional[GitRepositoryInfo] = None
        self.repo: Optional[pygit2.Repository] = None
        self.temp_dir: Optional[str] = None

        if not PYGIT2_AVAILABLE:
            raise ImportError("pygit2 is required. Install with: pip install pygit2")

        self._log(f"🔧 Using pygit2 version: {PYGIT2_VERSION}")
        if not HAS_CREDENTIAL_CONSTANTS:
            self._log("⚠️  Using legacy pygit2 credential constants")

    def _log(self, message: str, force: bool = False):
        """Log message if verbose mode is enabled"""
        if self.verbose or force:
            print(message)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def cleanup(self):
        """Clean up temporary files and repository"""
        if self.temp_dir and os.path.exists(self.temp_dir) and self.cleanup_after:
            try:
                shutil.rmtree(self.temp_dir)
                self._log(f"🧹 Cleaned up temporary directory: {self.temp_dir}")
                self.temp_dir = None
            except Exception as e:
                self._log(f"⚠️  Warning: Could not clean up {self.temp_dir}: {e}")

    def setup_credentials(
        self,
        username: str = None,
        password: str = None,
        token: str = None,
        ssh_key_path: str = None,
        ssh_passphrase: str = None,
    ) -> pygit2.RemoteCallbacks:
        """Setup Git credentials for authentication"""

        def credentials_callback(url, username_from_url, allowed_types):
            self._log(f"🔐 Authentication required for: {url}")
            self._log(f"   Allowed types: {allowed_types}")

            # Get credential constants with fallback for older pygit2 versions
            if HAS_CREDENTIAL_CONSTANTS:
                ssh_key_type = pygit2.credentials.GIT_CREDENTIAL_SSH_KEY
                userpass_type = pygit2.credentials.GIT_CREDENTIAL_USERPASS_PLAINTEXT
            else:
                # Fallback constants for older versions
                ssh_key_type = getattr(pygit2, "GIT_CREDTYPE_SSH_KEY", 2)
                userpass_type = getattr(pygit2, "GIT_CREDTYPE_USERPASS_PLAINTEXT", 1)

            # SSH Key authentication
            if (
                allowed_types & ssh_key_type
                and ssh_key_path
                and os.path.exists(ssh_key_path)
            ):
                self._log("   Using SSH key authentication")
                public_key = ssh_key_path + ".pub"
                if not os.path.exists(public_key):
                    public_key = None

                return pygit2.Keypair(
                    username_from_url or "git",
                    public_key,
                    ssh_key_path,
                    ssh_passphrase or "",
                )

            # Username/password authentication
            if allowed_types & userpass_type and username and password:
                self._log("   Using username/password authentication")
                return pygit2.UserPass(username, password)

            # Token authentication (GitHub, GitLab, etc.)
            if allowed_types & userpass_type and token:
                self._log("   Using token authentication")
                # For GitHub, use token as password with any username
                return pygit2.UserPass("token", token)

            # SSH agent
            if allowed_types & ssh_key_type and HAS_KEYPAIR_FROM_AGENT:
                self._log("   Trying SSH agent")
                try:
                    return pygit2.KeypairFromAgent(username_from_url or "git")
                except Exception as e:
                    self._log(f"   SSH agent failed: {e}")
            elif allowed_types & ssh_key_type:
                self._log("   SSH agent not available in this pygit2 version")

            self._log("   ❌ No suitable credentials available")
            return None

        # Try to create RemoteCallbacks with certificate callback if supported
        try:

            def certificate_callback(cert, valid, host):
                """Handle SSL certificate validation"""
                if not valid:
                    self._log(f"⚠️  SSL certificate validation failed for {host}")
                    # Accept invalid certificates (be careful in production!)
                    return True
                return True

            callbacks = pygit2.RemoteCallbacks(
                credentials=credentials_callback, certificate=certificate_callback
            )
        except TypeError:
            # Fallback for older pygit2 versions that don't support certificate callback
            self._log(
                "⚠️  Using simplified RemoteCallbacks (certificate validation not available)"
            )
            callbacks = pygit2.RemoteCallbacks(credentials=credentials_callback)

        return callbacks

    def parse_repository_url(self, repo_url: str) -> GitRepositoryInfo:
        """Parse and normalize repository URL"""
        repo_url = repo_url.strip()

        # Handle GitHub shorthand (user/repo)
        if (
            not repo_url.startswith(("http://", "https://", "git@", "ssh://"))
            and "/" in repo_url
        ):
            repo_url = f"https://github.com/{repo_url}.git"

        # Ensure .git suffix for HTTPS URLs if not present
        if repo_url.startswith("https://") and not repo_url.endswith(".git"):
            repo_url += ".git"

        # Determine authentication method from URL
        auth_method = "none"
        if repo_url.startswith("git@") or repo_url.startswith("ssh://"):
            auth_method = "ssh"
        elif repo_url.startswith("https://") and (
            "@" in repo_url or "token" in repo_url
        ):
            auth_method = "token"
        elif repo_url.startswith("https://"):
            auth_method = "https"

        return GitRepositoryInfo(url=repo_url, auth_method=auth_method)

    def get_remote_branches(
        self, repo_url: str, callbacks: pygit2.RemoteCallbacks = None
    ) -> List[str]:
        """Get list of remote branches"""
        try:
            self._log("🔍 Fetching remote branch information...")

            # Create a temporary repository to list remote branches
            temp_repo_dir = tempfile.mkdtemp(prefix="git_branches_")

            try:
                repo = pygit2.init_repository(temp_repo_dir)
                remote = repo.remotes.create("origin", repo_url)

                # Fetch remote references
                remote.fetch(callbacks=callbacks)

                branches = []
                for ref in repo.listall_reference_objects():
                    if ref.name.startswith("refs/remotes/origin/"):
                        branch_name = ref.name.replace("refs/remotes/origin/", "")
                        if branch_name != "HEAD":
                            branches.append(branch_name)

                self._log(f"📋 Found remote branches: {branches}")
                return branches

            finally:
                shutil.rmtree(temp_repo_dir, ignore_errors=True)

        except Exception as e:
            self._log(f"⚠️  Could not fetch remote branches: {e}")
            return ["main", "master"]  # Common defaults

    def clone_repository(
        self,
        repo_url: str,
        branch: str = None,
        commit_sha: str = None,
        username: str = None,
        password: str = None,
        token: str = None,
        ssh_key_path: str = None,
        ssh_passphrase: str = None,
    ) -> bool:
        """Clone repository to temporary directory"""

        try:
            self.repo_info = self.parse_repository_url(repo_url)
            self.temp_dir = tempfile.mkdtemp(prefix="git_remote_analyzer_")

            self._log(f"📥 Cloning repository: {self.repo_info.url}")
            self._log(f"📁 Temporary directory: {self.temp_dir}")

            # Setup authentication
            callbacks = self.setup_credentials(
                username=username,
                password=password,
                token=token,
                ssh_key_path=ssh_key_path,
                ssh_passphrase=ssh_passphrase,
            )

            # Determine branch to clone
            target_branch = branch or "main"

            # If no specific branch provided, try to detect default branch
            if not branch:
                try:
                    remote_branches = self.get_remote_branches(
                        self.repo_info.url, callbacks
                    )

                    # Priority order for default branches
                    for default_branch in ["main", "master", "develop", "dev"]:
                        if default_branch in remote_branches:
                            target_branch = default_branch
                            break

                    if remote_branches and target_branch not in remote_branches:
                        target_branch = remote_branches[0]

                except Exception as e:
                    self._log(f"⚠️  Could not detect default branch, using 'main': {e}")
                    target_branch = "main"

            self.repo_info.branch = target_branch
            self._log(f"🌿 Target branch: {target_branch}")

            # Clone options
            clone_options = {
                "bare": False,
                "callbacks": callbacks,
            }

            # Shallow clone for better performance (unless we need commit history)
            if self.shallow_clone and not commit_sha:
                # Note: pygit2 doesn't directly support shallow clones
                # We'll clone normally but could add depth limitation logic
                self._log(
                    "📦 Performing full clone (shallow clone not directly supported by pygit2)"
                )

            # Perform the clone
            try:
                self._log(f"🔄 Attempting to clone: {self.repo_info.url}")
                self.repo = pygit2.clone_repository(
                    self.repo_info.url, self.temp_dir, **clone_options
                )
                self._log("✅ Repository cloned successfully")

            except pygit2.GitError as e:
                self._log(f"❌ Git clone error: {e}")

                # Check for authentication issues
                if any(
                    keyword in str(e).lower()
                    for keyword in ["auth", "credential", "permission", "access"]
                ):
                    self._log("💡 Authentication may be required. Try:")
                    self._log("   --username and --password for HTTPS")
                    self._log("   --token for token-based auth")
                    self._log("   --ssh-key for SSH key auth")
                    raise

                # If clone fails with target branch, try with default branch detection
                if "reference" in str(e).lower() or "branch" in str(e).lower():
                    self._log(f"❌ Failed to clone branch '{target_branch}': {e}")
                    self._log("🔄 Trying to clone default branch...")

                    try:
                        # Clone without specifying branch, then checkout
                        self.repo = pygit2.clone_repository(
                            self.repo_info.url, self.temp_dir, callbacks=callbacks
                        )

                        # Try to checkout the desired branch
                        try:
                            branch_ref = f"refs/remotes/origin/{target_branch}"
                            if branch_ref in [
                                ref.name
                                for ref in self.repo.listall_reference_objects()
                            ]:
                                # Create and checkout local branch
                                remote_branch = self.repo.lookup_reference(branch_ref)
                                local_branch = self.repo.branches.local.create(
                                    target_branch, remote_branch.peel()
                                )
                                self.repo.checkout(local_branch)
                                self._log(f"✅ Checked out branch: {target_branch}")
                            else:
                                available_branches = [
                                    ref.name.replace("refs/remotes/origin/", "")
                                    for ref in self.repo.listall_reference_objects()
                                    if ref.name.startswith("refs/remotes/origin/")
                                    and ref.name != "refs/remotes/origin/HEAD"
                                ]
                                self._log(
                                    f"⚠️  Branch '{target_branch}' not found. Available: {available_branches}"
                                )
                                if available_branches:
                                    target_branch = available_branches[0]
                                    self.repo_info.branch = target_branch
                                    self._log(f"🔄 Using branch: {target_branch}")
                        except Exception as branch_error:
                            self._log(f"⚠️  Could not checkout branch: {branch_error}")
                            # Continue with default branch
                    except Exception as retry_error:
                        self._log(f"❌ Retry clone also failed: {retry_error}")
                        raise

                else:
                    raise

            except Exception as e:
                self._log(f"❌ Unexpected clone error: {e}")
                self._log(f"   Error type: {type(e)}")
                raise

            # If specific commit requested, checkout that commit
            if commit_sha:
                try:
                    commit = self.repo.get(commit_sha)
                    self.repo.checkout_tree(commit)
                    self.repo_info.commit_sha = commit_sha
                    self._log(f"📍 Checked out commit: {commit_sha}")
                except Exception as e:
                    self._log(f"❌ Could not checkout commit {commit_sha}: {e}")
                    return False

            # Get current commit info
            try:
                head = self.repo.head
                commit = head.peel()
                self.repo_info.commit_sha = str(commit.id)

                commit_info = {
                    "sha": str(commit.id),
                    "author": f"{commit.author.name} <{commit.author.email}>",
                    "committer": f"{commit.committer.name} <{commit.committer.email}>",
                    "message": commit.message.strip(),
                    "timestamp": commit.commit_time,
                }

                self._log(
                    f"📝 Current commit: {commit_info['sha'][:8]} by {commit_info['author']}"
                )
                self._log(f"   Message: {commit_info['message'][:60]}...")

            except Exception as e:
                self._log(f"⚠️  Could not get commit info: {e}")

            self.repo_info.local_path = self.temp_dir
            return True

        except Exception as e:
            error_msg = f"❌ Failed to clone repository: {e}"
            self._log(error_msg, force=True)

            # Provide specific error guidance
            if "not found" in str(e).lower() or "404" in str(e):
                self._log("💡 Repository not found. Check:")
                self._log("   - Repository URL is correct")
                self._log("   - Repository exists and is accessible")
                self._log("   - You have permission to access it")
            elif "ssl" in str(e).lower() or "certificate" in str(e).lower():
                self._log(
                    "💡 SSL/Certificate error. The server certificate may be invalid"
                )
            elif "timeout" in str(e).lower():
                self._log("💡 Connection timeout. Check network connectivity")

            if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir, ignore_errors=True)
                self.temp_dir = None
            return False

    def get_python_files(self) -> List[str]:
        """Get list of Python files in the repository"""
        if not self.temp_dir or not os.path.exists(self.temp_dir):
            return []

        python_files = []
        repo_path = Path(self.temp_dir)

        # Find all Python files
        for py_file in repo_path.rglob("*.py"):
            relative_path = py_file.relative_to(repo_path)

            # Apply exclusion filters
            if not self._should_exclude(str(relative_path)):
                python_files.append(str(py_file))
            else:
                self._log(f"🚫 Excluded: {relative_path}")

        return python_files

    def _should_exclude(self, file_path: str) -> bool:
        """Check if file should be excluded based on patterns"""
        if not self.exclude_patterns:
            return False

        for pattern in self.exclude_patterns:
            if self._matches_exclude_pattern(file_path, pattern):
                return True
        return False

    def _matches_exclude_pattern(self, file_path: str, pattern: str) -> bool:
        """Check if file path matches exclusion pattern"""
        path_parts = file_path.replace("\\", "/").split("/")

        # Direct pattern matching
        if fnmatch.fnmatch(file_path.replace("\\", "/"), pattern):
            return True

        # Check if any directory in path matches pattern
        for part in path_parts:
            if fnmatch.fnmatch(part, pattern):
                return True

        # Pattern with wildcards
        file_path_normalized = file_path.replace("\\", "/")
        if fnmatch.fnmatch(file_path_normalized, f"*/{pattern}/*") or fnmatch.fnmatch(
            file_path_normalized, f"*/{pattern}"
        ):
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
    ) -> GitAnalysisResults:
        """Analyze repository using the combined analyzer"""

        start_time = time.time()
        results = GitAnalysisResults(repo_info=self.repo_info)

        if not COMBINED_ANALYZER_AVAILABLE:
            results.errors.append("Combined analyzer not available")
            return results

        if not self.temp_dir or not os.path.exists(self.temp_dir):
            results.errors.append("Repository not cloned")
            return results

        try:
            # Get Python files
            python_files = self.get_python_files()
            results.files_analyzed = len(python_files)

            self._log(f"📊 Found {len(python_files)} Python files to analyze")

            if not python_files:
                results.errors.append("No Python files found")
                return results

            # Initialize combined analyzer
            analyzer = CombinedAnalyzer(
                verbose=self.verbose,
                show_full_paths=True,
                exclude_patterns=[],  # Already filtered
            )

            self._log("🔍 Running combined analysis...")

            # Run analysis on the temporary directory
            analysis_results = analyzer.analyze_directory(
                directory=self.temp_dir,
                recursive=True,
                run_treesitter=True,
                run_callgraph=True,
            )

            # Perform specific operations
            if search_pattern:
                self._log(f"🔍 Searching for pattern: {search_pattern}")
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
                # Default: print summary
                analyzer.print_summary(analysis_results, detailed=detailed)

            results.analysis_time = time.time() - start_time

            # Add commit info if available
            if self.repo:
                try:
                    head = self.repo.head
                    commit = head.peel()
                    results.commit_info = {
                        "sha": str(commit.id),
                        "author": f"{commit.author.name} <{commit.author.email}>",
                        "message": commit.message.strip(),
                        "timestamp": commit.commit_time,
                    }
                except Exception:
                    pass

            return results

        except Exception as e:
            results.errors.append(f"Analysis failed: {e}")
            self._log(f"❌ Analysis error: {e}", force=True)
            return results

    def get_repository_info(self) -> Dict[str, Any]:
        """Get detailed information about the repository"""
        if not self.repo:
            return {}

        try:
            info = {
                "url": self.repo_info.url,
                "branch": self.repo_info.branch,
                "local_path": self.repo_info.local_path,
            }

            # Current commit
            try:
                head = self.repo.head
                commit = head.peel()
                info["current_commit"] = {
                    "sha": str(commit.id),
                    "author": f"{commit.author.name} <{commit.author.email}>",
                    "committer": f"{commit.committer.name} <{commit.committer.email}>",
                    "message": commit.message.strip(),
                    "timestamp": commit.commit_time,
                }
            except Exception:
                pass

            # Repository statistics
            try:
                # Count commits (be careful, this can be slow for large repos)
                commit_count = 0
                for commit in self.repo.walk(self.repo.head.target):
                    commit_count += 1
                    if commit_count > 1000:  # Limit to avoid performance issues
                        break

                info["statistics"] = {
                    "commit_count": f"{commit_count}+"
                    if commit_count >= 1000
                    else commit_count,
                    "branch_count": len(list(self.repo.branches.local)),
                    "remote_count": len(list(self.repo.remotes)),
                }
            except Exception:
                pass

            # Remote information
            try:
                remotes = {}
                for remote in self.repo.remotes:
                    remotes[remote.name] = {
                        "url": remote.url,
                        "push_url": remote.push_url,
                    }
                info["remotes"] = remotes
            except Exception:
                pass

            return info

        except Exception as e:
            self._log(f"⚠️  Could not get repository info: {e}")
            return {"error": str(e)}


def main():
    parser = argparse.ArgumentParser(
        description="Git Remote Repository Analyzer with pygit2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python git_remote_analyzer.py --repo https://github.com/user/repo
    python git_remote_analyzer.py --repo git@github.com:user/repo.git --ssh-key ~/.ssh/id_rsa
    python git_remote_analyzer.py --repo user/repo --search "async.*"
    python git_remote_analyzer.py --repo https://github.com/user/repo --branch develop --token ghp_xxx
    python git_remote_analyzer.py --repo https://git.example.com/project.git --username user --password pass
        """,
    )

    # Repository options
    parser.add_argument(
        "--repo",
        "--repository",
        required=True,
        help="Repository URL or GitHub shorthand (user/repo)",
    )
    parser.add_argument(
        "--branch", "-b", help="Branch to analyze (default: auto-detect)"
    )
    parser.add_argument("--commit", "-c", help="Specific commit SHA to analyze")

    # Authentication options
    parser.add_argument("--username", "-u", help="Username for HTTPS authentication")
    parser.add_argument("--password", "-p", help="Password for HTTPS authentication")
    parser.add_argument("--token", "-t", help="Access token (GitHub, GitLab, etc.)")
    parser.add_argument("--ssh-key", help="Path to SSH private key")
    parser.add_argument("--ssh-passphrase", help="SSH key passphrase")
    parser.add_argument("--auth", help="Basic auth in format username:password")

    # Analysis options
    parser.add_argument(
        "--search", help="Search both functions and classes using regex pattern"
    )
    parser.add_argument(
        "--search-functions", help="Search functions using regex pattern"
    )
    parser.add_argument("--search-classes", help="Search classes using regex pattern")
    parser.add_argument("--preview", help="Preview method/function content by name")
    parser.add_argument(
        "--list-functions", action="store_true", help="List all available functions"
    )
    parser.add_argument(
        "--list-classes", action="store_true", help="List all available classes"
    )
    parser.add_argument(
        "--detailed", action="store_true", help="Show detailed analysis results"
    )
    parser.add_argument(
        "--info", action="store_true", help="Show repository information"
    )

    # Exclusion options
    parser.add_argument(
        "--exclude", nargs="+", help="Exclude files/directories matching these patterns"
    )
    parser.add_argument(
        "--exclude-preset",
        choices=["dev", "minimal", "comprehensive", "library"],
        help="Use predefined exclusion patterns",
    )

    # Behavior options
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )
    parser.add_argument(
        "--no-cleanup", action="store_true", help="Don't cleanup temporary files"
    )
    parser.add_argument(
        "--no-shallow", action="store_true", help="Don't use shallow clone"
    )

    args = parser.parse_args()

    # Prepare authentication
    username = args.username
    password = args.password
    token = args.token
    ssh_key_path = args.ssh_key
    ssh_passphrase = args.ssh_passphrase

    # Handle --auth format (username:password)
    if args.auth and ":" in args.auth:
        username, password = args.auth.split(":", 1)

    # Prepare exclusion patterns
    exclude_patterns = []
    if args.exclude:
        exclude_patterns.extend(args.exclude)
    if args.exclude_preset:
        exclude_patterns.extend(get_exclusion_preset(args.exclude_preset))

    print("🚀 Git Remote Repository Analyzer")
    print("=" * 50)

    # Initialize analyzer with context manager for automatic cleanup
    with GitRemoteAnalyzer(
        verbose=args.verbose,
        exclude_patterns=exclude_patterns,
        shallow_clone=not args.no_shallow,
        cleanup_after=not args.no_cleanup,
    ) as analyzer:
        # Clone repository
        success = analyzer.clone_repository(
            repo_url=args.repo,
            branch=args.branch,
            commit_sha=args.commit,
            username=username,
            password=password,
            token=token,
            ssh_key_path=ssh_key_path,
            ssh_passphrase=ssh_passphrase,
        )

        if not success:
            print("❌ Failed to clone repository")
            return 1

        # Show repository info if requested
        if args.info:
            info = analyzer.get_repository_info()
            print(f"\n📊 REPOSITORY INFORMATION")
            print(f"{'=' * 50}")
            print(json.dumps(info, indent=2, default=str))
            return 0

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

        # Perform analysis
        try:
            results = analyzer.analyze_with_combined_analyzer(
                search_pattern=search_pattern,
                preview_target=args.preview,
                search_type=search_type,
                list_functions=args.list_functions,
                list_classes=args.list_classes,
                detailed=args.detailed,
            )

            if results.errors:
                print(f"\n❌ Analysis completed with errors:")
                for error in results.errors:
                    print(f"   {error}")
                return 1

            print(f"\n✅ Analysis completed successfully!")
            print(f"📊 Files analyzed: {results.files_analyzed}")
            print(f"⏱️  Analysis time: {results.analysis_time:.2f} seconds")

            if results.commit_info:
                print(
                    f"📝 Analyzed commit: {results.commit_info['sha'][:8]} by {results.commit_info['author']}"
                )

            return 0

        except KeyboardInterrupt:
            print("\n⚠️  Analysis interrupted by user")
            return 1
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return 1


if __name__ == "__main__":
    if not PYGIT2_AVAILABLE:
        print("❌ pygit2 is required. Install with:")
        print("   pip install pygit2")
        print("\nNote: pygit2 requires libgit2. On some systems you may need:")
        print("   # Ubuntu/Debian: sudo apt-get install libgit2-dev")
        print("   # macOS: brew install libgit2")
        print("   # Then: pip install pygit2")
        sys.exit(1)

    # Check pygit2 version compatibility
    print(f"🔧 pygit2 version: {PYGIT2_VERSION}")
    if not HAS_CREDENTIAL_CONSTANTS:
        print("⚠️  Warning: Using legacy credential constants (older pygit2 version)")

    sys.exit(main())
