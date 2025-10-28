#!/usr/bin/env python3
"""
Create Proper Git Patch Script

This script creates properly formatted git patches for specific line changes,
particularly useful for fixing NameError issues like 'log' -> 'logger' replacements.
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path


def create_patch_for_line_changes(file_path, changes, branch_name, commit_message):
    """
    Create a proper git patch for specific line changes

    Args:
        file_path: Path to the file to modify
        changes: List of tuples (line_number, old_text, new_text)
        branch_name: Name for the new branch
        commit_message: Commit message for the patch
    """

    print(f"🔧 Creating patch for {file_path}")
    print(f"🌿 Branch: {branch_name}")
    print(f"📝 Changes: {len(changes)} line(s)")

    # Check if we're in a git repository
    try:
        subprocess.run(
            ["git", "rev-parse", "--git-dir"], capture_output=True, check=True
        )
    except subprocess.CalledProcessError:
        print("❌ Error: Not in a git repository")
        return False

    # Get current branch
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    original_branch = result.stdout.strip()
    print(f"📍 Current branch: {original_branch}")

    try:
        # Read the current file
        if not os.path.exists(file_path):
            print(f"❌ Error: File {file_path} not found")
            return False

        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        print(f"📄 File loaded: {len(lines)} lines")

        # Apply changes
        changes_applied = 0
        for line_num, old_text, new_text in changes:
            # Convert to 0-based index
            idx = line_num - 1

            if 0 <= idx < len(lines):
                current_line = lines[idx].rstrip("\n")

                # Check if the old text is in the current line
                if old_text in current_line:
                    # Replace the old text with new text
                    new_line = current_line.replace(old_text, new_text)
                    lines[idx] = new_line + "\n"
                    changes_applied += 1
                    print(f"✅ Line {line_num}: '{old_text}' → '{new_text}'")
                else:
                    print(
                        f"⚠️  Line {line_num}: '{old_text}' not found in: {current_line.strip()}"
                    )
            else:
                print(
                    f"❌ Line {line_num}: Invalid line number (file has {len(lines)} lines)"
                )

        if changes_applied == 0:
            print("❌ No changes were applied")
            return False

        # Create new branch
        try:
            subprocess.run(
                ["git", "checkout", "-b", branch_name], capture_output=True, check=True
            )
            print(f"🌿 Created branch: {branch_name}")
        except subprocess.CalledProcessError:
            # Branch might already exist
            subprocess.run(
                ["git", "checkout", branch_name], capture_output=True, check=True
            )
            print(f"🔄 Switched to existing branch: {branch_name}")

        # Write the modified file
        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        # Stage and commit the changes
        subprocess.run(["git", "add", file_path], check=True)

        result = subprocess.run(
            ["git", "commit", "-m", commit_message],
            capture_output=True,
            text=True,
            check=True,
        )

        # Get commit hash
        commit_result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        )
        commit_hash = commit_result.stdout.strip()[:8]

        print(f"💾 Committed: {commit_hash}")

        # Generate patch file
        patch_file = f"{branch_name.replace('/', '_')}.patch"
        with open(patch_file, "w") as f:
            subprocess.run(
                ["git", "format-patch", "-1", "HEAD", "--stdout"], stdout=f, check=True
            )

        print(f"📋 Patch file created: {patch_file}")

        # Show the patch content
        print(f"\n📦 Patch content:")
        print("=" * 50)
        with open(patch_file, "r") as f:
            patch_content = f.read()
            print(patch_content)

        # Switch back to original branch
        subprocess.run(
            ["git", "checkout", original_branch], capture_output=True, check=True
        )
        print(f"🔙 Returned to: {original_branch}")

        # Show instructions
        print(f"\n💡 To apply this patch elsewhere:")
        print(f"   git apply {patch_file}")
        print(f"\n🍒 To cherry-pick this commit:")
        print(f"   git cherry-pick {commit_hash}")
        print(f"\n🔀 To merge this branch:")
        print(f"   git merge {branch_name}")

        return True

    except Exception as e:
        print(f"❌ Error during patch creation: {e}")
        # Try to return to original branch
        try:
            subprocess.run(["git", "checkout", original_branch], capture_output=True)
        except:
            pass
        return False


def fix_nameerror_log_to_logger():
    """Fix the specific NameError: 'log' -> 'logger' in main.py"""

    print("🚀 Fixing NameError: 'log' -> 'logger' in main.py")
    print("=" * 50)

    # Define the changes to make
    changes = [
        # Line number, old text, new text
        (2605, "log.error(", "logger.error("),
        # Add more changes if needed
    ]

    return create_patch_for_line_changes(
        file_path="main.py",
        changes=changes,
        branch_name="fix/log-undefined-error",
        commit_message="Fix NameError: replace 'log' with 'logger' in UpdateAlerts exception handler\n\n"
        + "- Line 2605: Changed log.error() to logger.error()\n"
        + "- Resolves NameError when handling UpdateAlerts exceptions",
    )


def fix_nameerror_errors_to_error_count():
    """Fix the specific NameError: 'errors' -> 'error_count' in main.py"""

    print("🚀 Fixing NameError: 'errors' -> 'error_count' in main.py")
    print("=" * 50)

    # Define the changes to make
    changes = [
        # Line number, old text, new text
        (2016, "errors += 1", "error_count += 1"),
        # Add more changes if needed
    ]

    return create_patch_for_line_changes(
        file_path="main.py",
        changes=changes,
        branch_name="fix/errors-undefined-variable",
        commit_message="Fix NameError: replace 'errors' with 'error_count' in CreateCaseTasks function\n\n"
        + "- Line 2016: Changed errors += 1 to error_count += 1\n"
        + "- Resolves NameError when incrementing error counter",
    )


def fix_both_nameerrors():
    """Fix both NameError issues in a single patch"""

    print("🚀 Fixing Both NameErrors in main.py")
    print("=" * 50)

    # Define the changes to make
    changes = [
        # Line number, old text, new text
        (2016, "errors += 1", "error_count += 1"),
        (2605, "log.error(", "logger.error("),
    ]

    return create_patch_for_line_changes(
        file_path="main.py",
        changes=changes,
        branch_name="fix/nameerror-logging-and-variables",
        commit_message="Fix NameError issues in main.py - replace 'log' with 'logger' and 'errors' with 'error_count'\n\n"
        + "- Line 2605: Changed log.error() to logger.error() in UpdateAlerts exception handler\n"
        + "- Line 2016: Changed errors += 1 to error_count += 1 in CreateCaseTasks function\n\n"
        + "These fixes resolve the NameError exceptions that were occurring when handling requests.",
    )


def interactive_patch_creator():
    """Interactive mode for creating custom patches"""

    print("🔧 Interactive Patch Creator")
    print("=" * 30)

    # Get file path
    file_path = input("📁 Enter file path (e.g., main.py): ").strip()
    if not file_path:
        file_path = "main.py"

    # Get branch name
    branch_name = input("🌿 Enter branch name (e.g., fix/my-changes): ").strip()
    if not branch_name:
        branch_name = "fix/custom-changes"

    # Get commit message
    commit_message = input("📝 Enter commit message: ").strip()
    if not commit_message:
        commit_message = "Fix issues in " + file_path

    # Get changes
    changes = []
    print("\n🔧 Enter changes (press Enter with empty line number to finish):")

    while True:
        try:
            line_input = input("   Line number: ").strip()
            if not line_input:
                break

            line_num = int(line_input)
            old_text = input("   Old text: ").strip()
            new_text = input("   New text: ").strip()

            changes.append((line_num, old_text, new_text))
            print(f"   ✅ Added: Line {line_num}: '{old_text}' → '{new_text}'")

        except ValueError:
            print("   ❌ Invalid line number")
            continue
        except KeyboardInterrupt:
            print("\n⚠️  Cancelled")
            return False

    if not changes:
        print("❌ No changes specified")
        return False

    return create_patch_for_line_changes(
        file_path, changes, branch_name, commit_message
    )


def main():
    """Main function with menu options"""

    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
    else:
        print("🚀 Proper Git Patch Creator")
        print("=" * 30)
        print("1. Fix log -> logger NameError")
        print("2. Fix errors -> error_count NameError")
        print("3. Fix both NameErrors")
        print("4. Interactive mode")
        print("5. Exit")

        choice = input("\nSelect option (1-5): ").strip()

        mode_map = {
            "1": "log",
            "2": "errors",
            "3": "both",
            "4": "interactive",
            "5": "exit",
        }

        mode = mode_map.get(choice, "exit")

    if mode == "log":
        success = fix_nameerror_log_to_logger()
    elif mode == "errors":
        success = fix_nameerror_errors_to_error_count()
    elif mode == "both":
        success = fix_both_nameerrors()
    elif mode == "interactive":
        success = interactive_patch_creator()
    else:
        print("👋 Goodbye!")
        return

    if success:
        print("\n🎉 Patch created successfully!")
    else:
        print("\n❌ Patch creation failed!")


if __name__ == "__main__":
    main()
