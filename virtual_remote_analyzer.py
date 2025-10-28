#!/usr/bin/env python3
"""
Virtual Remote Repository Analyzer

This analyzer downloads and analyzes remote repositories entirely in memory
without creating temporary files on disk. It supports GitHub, GitLab, and
other Git hosting services.

Features:
- In-memory repository analysis
- GitHub API integration
- Direct ZIP archive processing
- Combined search and preview functionality
- Multiple repository formats support

Usage:
    python virtual_remote_analyzer.py --repo https://github.com/user/repo
    python virtual_remote_analyzer.py --repo user/repo --search "async.*"
    python virtual_remote_analyzer.py --github-url https://github.com/user/repo --preview "main"
"""

import os
import sys
import json
import argparse
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Union
from dataclasses import dataclass, asdict
import time
import re
import fnmatch
import zipfile
import io
from urllib.parse import urlparse, urljoin
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
import ssl
import base64

# Try to import our existing analyzer
try:
    from combined_cli_analyzer import CombinedAnalyzer, get_exclusion_preset

    COMBINED_ANALYZER_AVAILABLE = True
except ImportError:
    print("⚠️  Combined analyzer not found. Limited functionality available.")
    COMBINED_ANALYZER_AVAILABLE = False


@dataclass
class VirtualFile:
    """Represents a file in memory"""

    path: str
    content: bytes
    encoding: str = "utf-8"

    @property
    def text_content(self) -> str:
        """Get text content with proper encoding"""
        try:
            return self.content.decode(self.encoding)
        except UnicodeDecodeError:
            # Try common encodings
            for enc in ["utf-8", "latin-1", "cp1252"]:
                try:
                    return self.content.decode(enc)
                except UnicodeDecodeError:
                    continue
            # Fallback with error handling
            return self.content.decode("utf-8", errors="replace")


@dataclass
class RepositoryInfo:
    """Information about a remote repository"""

    url: str
    platform: str  # github, gitlab, bitbucket, etc.
    owner: str
    repo: str
    branch: str = "main"
    commit_sha: Optional[str] = None
    download_url: Optional[str] = None


class VirtualRemoteAnalyzer:
    """Analyzes remote repositories entirely in memory"""

    def __init__(
        self,
        verbose: bool = False,
        exclude_patterns: List[str] = None,
        username: str = None,
        password: str = None,
        token: str = None,
    ):
        self.verbose = verbose
        self.exclude_patterns = exclude_patterns or []
        self.virtual_files: Dict[str, VirtualFile] = {}
        self.repo_info: Optional[RepositoryInfo] = None
        self.username = username
        self.password = password
        self.token = token

        # SSL context for HTTPS requests
        self.ssl_context = ssl.create_default_context()

    def _log(self, message: str, force: bool = False):
        """Log message if verbose mode is enabled"""
        if self.verbose or force:
            print(message)

    def parse_repository_url(self, repo_url: str) -> RepositoryInfo:
        """Parse repository URL and extract information"""
        # Clean up the URL
        repo_url = repo_url.strip()
        if not repo_url.startswith(("http://", "https://")):
            # Assume GitHub shorthand: user/repo
            if "/" in repo_url and not repo_url.startswith("."):
                repo_url = f"https://github.com/{repo_url}"
            else:
                raise ValueError(f"Invalid repository URL: {repo_url}")

        parsed = urlparse(repo_url)
        hostname = parsed.hostname.lower() if parsed.hostname else ""
        path_parts = [p for p in parsed.path.split("/") if p]

        # Handle different URL formats
        if "github.com" in hostname:
            if len(path_parts) < 2:
                raise ValueError(f"Invalid GitHub repository path: {parsed.path}")
            platform = "github"
            owner = path_parts[0]
            repo = path_parts[1]
            if repo.endswith(".git"):
                repo = repo[:-4]
            branch = "main"
            download_url = (
                f"https://github.com/{owner}/{repo}/archive/refs/heads/{branch}.zip"
            )

        elif "gitlab.com" in hostname:
            if len(path_parts) < 2:
                raise ValueError(f"Invalid GitLab repository path: {parsed.path}")
            platform = "gitlab"
            owner = path_parts[0]
            repo = path_parts[1]
            if repo.endswith(".git"):
                repo = repo[:-4]
            branch = "main"
            download_url = f"https://gitlab.com/{owner}/{repo}/-/archive/{branch}/{repo}-{branch}.zip"

        elif "bitbucket.org" in hostname:
            if len(path_parts) < 2:
                raise ValueError(f"Invalid Bitbucket repository path: {parsed.path}")
            platform = "bitbucket"
            owner = path_parts[0]
            repo = path_parts[1]
            if repo.endswith(".git"):
                repo = repo[:-4]
            branch = "master"
            download_url = f"https://bitbucket.org/{owner}/{repo}/get/{branch}.zip"

        else:
            # Generic Git server (like your custom Git server)
            platform = "generic"

            # For URLs like https://git.example.com/PROJECT_ID
            if len(path_parts) == 1:
                # Single path component - use as repo identifier
                owner = "unknown"
                repo = path_parts[0]
            elif len(path_parts) >= 2:
                # Multiple path components - last one is repo
                owner = "/".join(path_parts[:-1])
                repo = path_parts[-1]
            else:
                raise ValueError(f"Invalid repository path: {parsed.path}")

            if repo.endswith(".git"):
                repo = repo[:-4]

            branch = "main"
            # For generic servers, try multiple common archive URL patterns
            base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if base_url.endswith(".git"):
                base_url = base_url[:-4]

            # Primary download URL (GitLab-style)
            download_url = f"{base_url}/-/archive/{branch}/{repo}-{branch}.zip"

        return RepositoryInfo(
            url=repo_url,
            platform=platform,
            owner=owner,
            repo=repo,
            branch=branch,
            download_url=download_url,
        )

    def _try_different_branches(self, repo_info: RepositoryInfo) -> Optional[str]:
        """Try different common branch names to find the default branch"""
        common_branches = ["main", "master", "develop", "dev"]

        # For generic servers, try multiple URL patterns
        if repo_info.platform == "generic":
            base_url = repo_info.url
            if base_url.endswith(".git"):
                base_url = base_url[:-4]

            url_patterns = [
                f"{base_url}/-/archive/{{branch}}/{repo_info.repo}-{{branch}}.zip",  # GitLab-style
                f"{base_url}/archive/{{branch}}.zip",  # Simple archive
                f"{base_url}/repository/archive.zip?ref={{branch}}",  # GitLab API-style
                f"{base_url}/+archive/{{branch}}.tar.gz",  # Gitiles-style (we'll convert to zip)
            ]
        else:
            url_patterns = []

        for branch in common_branches:
            if repo_info.platform == "github":
                download_url = f"https://github.com/{repo_info.owner}/{repo_info.repo}/archive/refs/heads/{branch}.zip"
                urls_to_try = [download_url]
            elif repo_info.platform == "gitlab":
                download_url = f"https://gitlab.com/{repo_info.owner}/{repo_info.repo}/-/archive/{branch}/{repo_info.repo}-{branch}.zip"
                urls_to_try = [download_url]
            elif repo_info.platform == "bitbucket":
                download_url = f"https://bitbucket.org/{repo_info.owner}/{repo_info.repo}/get/{branch}.zip"
                urls_to_try = [download_url]
            elif repo_info.platform == "generic":
                urls_to_try = [
                    pattern.format(branch=branch) for pattern in url_patterns
                ]
            else:
                continue

            for url in urls_to_try:
                try:
                    self._log(f"   Trying branch '{branch}' with URL: {url}")
                    request = self._create_authenticated_request(url)
                    with urlopen(
                        request, context=self.ssl_context, timeout=10
                    ) as response:
                        if response.status == 200:
                            self._log(f"   ✅ Found branch: {branch}")
                            return url
                except (URLError, HTTPError) as e:
                    self._log(f"   Failed: {e}")
                    continue

        return None

    def _create_authenticated_request(self, url: str) -> Request:
        """Create HTTP request with authentication if provided"""
        request = Request(url)

        # Add User-Agent to avoid blocking
        request.add_header("User-Agent", "VirtualRemoteAnalyzer/1.0")

        # Add authentication headers
        if self.token:
            # Token-based authentication (GitHub, GitLab, etc.)
            if "github.com" in url:
                request.add_header("Authorization", f"token {self.token}")
            elif "gitlab.com" in url:
                request.add_header("Authorization", f"Bearer {self.token}")
            else:
                # Generic token auth
                request.add_header("Authorization", f"Bearer {self.token}")
        elif self.username and self.password:
            # Basic authentication
            credentials = f"{self.username}:{self.password}"
            encoded_credentials = base64.b64encode(credentials.encode("utf-8")).decode(
                "ascii"
            )
            request.add_header("Authorization", f"Basic {encoded_credentials}")

        return request

    def download_repository(self, repo_url: str) -> bool:
        """Download repository archive into memory"""
        try:
            self.repo_info = self.parse_repository_url(repo_url)
            self._log(
                f"📥 Downloading repository: {self.repo_info.owner}/{self.repo_info.repo}"
            )
            self._log(f"🔗 Platform: {self.repo_info.platform}")

            download_url = self.repo_info.download_url

            # Try to download with the default branch
            try:
                self._log(f"🔄 Attempting download from: {download_url}")
                request = self._create_authenticated_request(download_url)

                with urlopen(request, context=self.ssl_context, timeout=30) as response:
                    if response.status == 200:
                        zip_data = response.read()
                        self._log(f"✅ Downloaded {len(zip_data)} bytes")
                    else:
                        raise HTTPError(
                            download_url, response.status, "Download failed", None, None
                        )

            except (URLError, HTTPError) as e:
                self._log(f"❌ Download failed with {self.repo_info.branch}: {e}")
                self._log("🔄 Trying alternative branches and URL patterns...")

                # Try different branches
                alternative_url = self._try_different_branches(self.repo_info)
                if not alternative_url:
                    self._log("❌ Could not find accessible branch or URL pattern")
                    self._log(
                        "💡 Try providing authentication with --username/--password or --token"
                    )
                    return False

                # Download with alternative branch/URL
                request = self._create_authenticated_request(alternative_url)
                with urlopen(request, context=self.ssl_context, timeout=30) as response:
                    zip_data = response.read()
                    self._log(
                        f"✅ Downloaded {len(zip_data)} bytes from alternative URL"
                    )

            # Extract files into memory
            return self._extract_zip_to_memory(zip_data)

        except Exception as e:
            self._log(f"❌ Error downloading repository: {e}", force=True)
            return False

    def _extract_zip_to_memory(self, zip_data: bytes) -> bool:
        """Extract ZIP archive contents into memory"""
        try:
            self._log("📂 Extracting repository files to memory...")

            with zipfile.ZipFile(io.BytesIO(zip_data), "r") as zip_file:
                file_list = zip_file.namelist()
                self._log(f"📄 Found {len(file_list)} files in archive")

                python_files = []
                for file_path in file_list:
                    # Skip directories
                    if file_path.endswith("/"):
                        continue

                    # Only process Python files for analysis
                    if file_path.endswith(".py"):
                        try:
                            # Read file content
                            file_content = zip_file.read(file_path)

                            # Normalize path (remove archive root directory)
                            normalized_path = self._normalize_archive_path(file_path)

                            # Check exclusion patterns
                            if not self._should_exclude(normalized_path):
                                virtual_file = VirtualFile(
                                    path=normalized_path, content=file_content
                                )
                                self.virtual_files[normalized_path] = virtual_file
                                python_files.append(normalized_path)
                            else:
                                self._log(f"   🚫 Excluded: {normalized_path}")

                        except Exception as e:
                            self._log(f"   ❌ Error reading {file_path}: {e}")
                            continue

                self._log(f"✅ Loaded {len(python_files)} Python files into memory")
                if self.verbose and python_files:
                    self._log("📋 Python files loaded:")
                    for py_file in sorted(python_files)[:10]:  # Show first 10
                        self._log(f"   - {py_file}")
                    if len(python_files) > 10:
                        self._log(f"   ... and {len(python_files) - 10} more")

                return len(python_files) > 0

        except Exception as e:
            self._log(f"❌ Error extracting archive: {e}", force=True)
            return False

    def _normalize_archive_path(self, archive_path: str) -> str:
        """Normalize archive path by removing root directory"""
        path_parts = archive_path.split("/")
        # Most archives have a root directory like "repo-main/"
        if len(path_parts) > 1:
            return "/".join(path_parts[1:])  # Remove first part
        return archive_path

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
        # Convert to Path for easier manipulation
        path_parts = file_path.split("/")

        # Direct pattern matching
        if fnmatch.fnmatch(file_path, pattern):
            return True

        # Check if any directory in path matches pattern
        for part in path_parts:
            if fnmatch.fnmatch(part, pattern):
                return True

        # Pattern with wildcards
        if fnmatch.fnmatch(file_path, f"*/{pattern}/*") or fnmatch.fnmatch(
            file_path, f"*/{pattern}"
        ):
            return True

        return False

    def create_temporary_structure(self) -> Optional[str]:
        """Create temporary directory structure for analysis"""
        if not self.virtual_files:
            return None

        try:
            # Create temporary directory
            temp_dir = tempfile.mkdtemp(prefix="virtual_repo_")
            self._log(f"📁 Creating temporary structure in: {temp_dir}")

            for file_path, virtual_file in self.virtual_files.items():
                # Create full file path
                full_path = os.path.join(temp_dir, file_path)

                # Create directories if needed
                os.makedirs(os.path.dirname(full_path), exist_ok=True)

                # Write file content
                with open(full_path, "wb") as f:
                    f.write(virtual_file.content)

            self._log(
                f"✅ Created {len(self.virtual_files)} files in temporary structure"
            )
            return temp_dir

        except Exception as e:
            self._log(f"❌ Error creating temporary structure: {e}")
            return None

    def analyze_with_combined_analyzer(
        self,
        search_pattern: str = None,
        preview_target: str = None,
        search_type: str = "both",
        list_functions: bool = False,
        list_classes: bool = False,
    ) -> Dict[str, Any]:
        """Analyze repository using the combined analyzer"""
        if not COMBINED_ANALYZER_AVAILABLE:
            return {"error": "Combined analyzer not available"}

        # Create temporary directory structure
        temp_dir = self.create_temporary_structure()
        if not temp_dir:
            return {"error": "Failed to create temporary structure"}

        try:
            # Initialize combined analyzer
            analyzer = CombinedAnalyzer(
                verbose=self.verbose,
                show_full_paths=True,  # Show full paths in temp dir
                exclude_patterns=[],  # Already filtered
            )

            self._log("🔍 Running combined analysis...")

            # Run analysis
            results = analyzer.analyze_directory(
                directory=temp_dir,
                recursive=True,
                run_treesitter=True,
                run_callgraph=True,
            )

            # Perform specific operations
            if search_pattern:
                self._log(f"🔍 Searching for pattern: {search_pattern}")
                print()  # Add spacing
                analyzer.search_combined(search_pattern, search_type=search_type)

            elif preview_target:
                self._log(f"📖 Previewing: {preview_target}")
                print()  # Add spacing
                analyzer.preview_method(preview_target)

            elif list_functions:
                self._log("📋 Listing functions...")
                print()  # Add spacing
                analyzer.list_available_functions()

            elif list_classes:
                self._log("📋 Listing classes...")
                print()  # Add spacing
                analyzer.list_available_classes()

            else:
                # Default: print summary
                analyzer.print_summary(results)

            return asdict(results)

        finally:
            # Clean up temporary directory
            try:
                shutil.rmtree(temp_dir)
                self._log(f"🧹 Cleaned up temporary directory")
            except Exception as e:
                self._log(f"⚠️  Warning: Could not clean up {temp_dir}: {e}")

    def simple_search_in_memory(self, pattern: str) -> List[Dict[str, Any]]:
        """Simple in-memory search without creating temporary files"""
        if not self.virtual_files:
            return []

        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            self._log(f"❌ Invalid regex pattern '{pattern}': {e}")
            return []

        matches = []
        for file_path, virtual_file in self.virtual_files.items():
            try:
                content = virtual_file.text_content
                lines = content.split("\n")

                for line_num, line in enumerate(lines, 1):
                    # Look for function/class definitions
                    if line.strip().startswith(("def ", "class ", "async def ")):
                        # Extract function/class name
                        name_match = re.search(r"(?:def|class)\s+(\w+)", line)
                        if name_match and regex.search(name_match.group(1)):
                            matches.append(
                                {
                                    "file": file_path,
                                    "line": line_num,
                                    "name": name_match.group(1),
                                    "type": "class" if "class " in line else "function",
                                    "content": line.strip(),
                                    "is_async": "async " in line,
                                }
                            )

                    # Also search in line content for broader matches
                    elif regex.search(line):
                        matches.append(
                            {
                                "file": file_path,
                                "line": line_num,
                                "name": "content_match",
                                "type": "content",
                                "content": line.strip(),
                                "is_async": False,
                            }
                        )

            except Exception as e:
                self._log(f"❌ Error searching in {file_path}: {e}")
                continue

        return matches

    def preview_in_memory(
        self, file_path: str, start_line: int, end_line: int
    ) -> Optional[str]:
        """Preview file content directly from memory"""
        if file_path not in self.virtual_files:
            # Try to find partial match
            matching_files = [f for f in self.virtual_files.keys() if file_path in f]
            if len(matching_files) == 1:
                file_path = matching_files[0]
            else:
                return None

        try:
            virtual_file = self.virtual_files[file_path]
            content = virtual_file.text_content
            lines = content.split("\n")

            # Adjust for 0-based indexing
            start_idx = max(0, start_line - 1)
            end_idx = min(len(lines), end_line)

            preview_lines = []
            for i in range(start_idx, end_idx):
                line_num = i + 1
                line_content = lines[i]
                preview_lines.append(f"{line_num:4d} | {line_content}")

            return "\n".join(preview_lines)

        except Exception as e:
            self._log(f"❌ Error previewing {file_path}: {e}")
            return None

    def get_repository_stats(self) -> Dict[str, Any]:
        """Get statistics about the loaded repository"""
        if not self.virtual_files:
            return {}

        stats = {
            "total_files": len(self.virtual_files),
            "total_size": sum(len(vf.content) for vf in self.virtual_files.values()),
            "files_by_directory": {},
            "largest_files": [],
        }

        # Analyze by directory
        for file_path in self.virtual_files.keys():
            directory = "/".join(file_path.split("/")[:-1]) or "root"
            stats["files_by_directory"][directory] = (
                stats["files_by_directory"].get(directory, 0) + 1
            )

        # Find largest files
        file_sizes = [(fp, len(vf.content)) for fp, vf in self.virtual_files.items()]
        file_sizes.sort(key=lambda x: x[1], reverse=True)
        stats["largest_files"] = file_sizes[:10]

        return stats


def main():
    parser = argparse.ArgumentParser(
        description="Virtual Remote Repository Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python virtual_remote_analyzer.py --repo https://github.com/user/repo
    python virtual_remote_analyzer.py --repo user/repo --search "async.*"
    python virtual_remote_analyzer.py --github-url https://github.com/user/repo --preview "main"
    python virtual_remote_analyzer.py --repo user/repo --list-functions --exclude-preset dev
    python virtual_remote_analyzer.py --repo user/repo --search-classes ".*Manager$"
        """,
    )

    # Repository options
    parser.add_argument(
        "--repo", "--repository", help="Repository URL or GitHub shorthand (user/repo)"
    )
    parser.add_argument("--github-url", help="Full GitHub repository URL")

    # Authentication options
    parser.add_argument("--username", "-u", help="Username for basic authentication")
    parser.add_argument("--password", "-p", help="Password for basic authentication")
    parser.add_argument(
        "--token", "-t", help="Access token for authentication (GitHub, GitLab, etc.)"
    )
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
        "--stats", action="store_true", help="Show repository statistics"
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

    # Output options
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )
    parser.add_argument(
        "--simple",
        action="store_true",
        help="Use simple in-memory search instead of full analysis",
    )

    args = parser.parse_args()

    # Determine repository URL
    repo_url = args.repo or args.github_url
    if not repo_url:
        print("❌ Error: Repository URL is required")
        print("Use --repo or --github-url to specify the repository")
        return 1

    # Prepare authentication
    username = args.username
    password = args.password
    token = args.token

    # Handle --auth format (username:password)
    if args.auth and ":" in args.auth:
        username, password = args.auth.split(":", 1)

    # Prepare exclusion patterns
    exclude_patterns = []
    if args.exclude:
        exclude_patterns.extend(args.exclude)
    if args.exclude_preset:
        exclude_patterns.extend(get_exclusion_preset(args.exclude_preset))

    print("🚀 Virtual Remote Repository Analyzer")
    print("=" * 50)

    # Initialize analyzer
    analyzer = VirtualRemoteAnalyzer(
        verbose=args.verbose,
        exclude_patterns=exclude_patterns,
        username=username,
        password=password,
        token=token,
    )

    # Download repository
    if not analyzer.download_repository(repo_url):
        print("❌ Failed to download repository")
        return 1

    # Show repository stats if requested
    if args.stats:
        stats = analyzer.get_repository_stats()
        print(f"\n📊 REPOSITORY STATISTICS")
        print(f"{'=' * 50}")
        print(f"📁 Total files: {stats['total_files']}")
        print(f"📏 Total size: {stats['total_size']:,} bytes")
        print(f"📂 Directories: {len(stats['files_by_directory'])}")

        print(f"\n📂 Files by directory:")
        for directory, count in sorted(stats["files_by_directory"].items()):
            print(f"   {directory}: {count} files")

        if stats["largest_files"]:
            print(f"\n📄 Largest files:")
            for file_path, size in stats["largest_files"][:5]:
                print(f"   {file_path}: {size:,} bytes")

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
    if args.simple or not COMBINED_ANALYZER_AVAILABLE:
        # Simple in-memory analysis
        if search_pattern:
            print(f"\n🔍 Simple search for pattern: {search_pattern}")
            matches = analyzer.simple_search_in_memory(search_pattern)

            if matches:
                print(f"Found {len(matches)} matches:")
                for match in matches[:20]:  # Limit output
                    print(f"  📄 {match['file']}:{match['line']}")
                    print(f"     {match['type']}: {match['name']}")
                    print(f"     {match['content']}")
                    print()
            else:
                print("No matches found")
        else:
            print("\n📊 Repository loaded successfully!")
            print("Use --search, --list-functions, or --list-classes for analysis")

    else:
        # Full analysis with combined analyzer
        try:
            result = analyzer.analyze_with_combined_analyzer(
                search_pattern=search_pattern,
                preview_target=args.preview,
                search_type=search_type,
                list_functions=args.list_functions,
                list_classes=args.list_classes,
            )

            if "error" in result:
                print(f"❌ Analysis error: {result['error']}")
                return 1

        except KeyboardInterrupt:
            print("\n⚠️  Analysis interrupted by user")
            return 1
        except Exception as e:
            print(f"❌ Unexpected error during analysis: {e}")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
