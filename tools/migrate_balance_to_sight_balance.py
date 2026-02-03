#!/usr/bin/env python3
"""
AST-based migration tool to rename 'balance' to 'sight_balance' for consistency.

This tool systematically updates Python source code to use the standardized
'sight_balance' naming convention instead of the legacy 'balance' name.
"""

import ast
import sys
import argparse
from pathlib import Path
from typing import Set, List, Tuple, Optional
import tokenize
from io import BytesIO

from logger import log

class BalanceToSightBalanceTransformer(ast.NodeTransformer):
    """AST transformer that renames 'balance' references to 'sight_balance'."""

    def __init__(self):
        self.modified = False
        # Track context to avoid false positives
        self.in_function_def = False
        self.in_class_def = False
        self.current_class_name = None
        self.current_function_name = None

    def visit_ClassDef(self, node):
        """Track when we're inside a class definition."""
        self.in_class_def = True
        self.current_class_name = node.name
        self.generic_visit(node)
        self.in_class_def = False
        self.current_class_name = None
        return node

    def visit_FunctionDef(self, node):
        """Track when we're inside a function definition."""
        self.in_function_def = True
        self.current_function_name = node.name
        self.generic_visit(node)
        self.in_function_def = False
        self.current_function_name = None
        return node

    def visit_Name(self, node):
        """Rename 'balance' identifiers to 'sight_balance'."""
        # Skip if we're in specific contexts where 'balance' might be intentional
        if node.id == 'balance':
            # Don't rename if it's a method definition (like def balance(self))
            if (self.in_class_def and self.in_function_def and
                self.current_function_name == 'balance'):
                return node

            # Don't rename if it's a class definition
            if self.in_class_def and self.current_class_name == 'balance':
                return node

            # Rename the identifier
            node.id = 'sight_balance'
            self.modified = True

        return node

    def visit_Attribute(self, node):
        """Rename attribute access like obj.balance to obj.sight_balance."""
        if node.attr == 'balance':
            # Don't rename if it's a method call (like obj.balance())
            # We'll handle this in the call visitor
            if not isinstance(node.ctx, ast.Load):
                return node

            # Rename the attribute
            node.attr = 'sight_balance'
            self.modified = True

        return node

    def visit_Call(self, node):
        """Handle method calls - don't rename method names."""
        # If this is a method call like obj.balance(), don't rename it
        if (isinstance(node.func, ast.Attribute) and
            node.func.attr == 'balance'):
            # This is a method call, don't rename
            return node

        return self.generic_visit(node)

    def visit_arg(self, node):
        """Rename function arguments named 'balance'."""
        if node.arg == 'balance':
            node.arg = 'sight_balance'
            self.modified = True
        return node

    def visit_Assign(self, node):
        """Handle assignment targets."""
        # Check if we're assigning to a variable named 'balance'
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == 'balance':
                target.id = 'sight_balance'
                self.modified = True
        return self.generic_visit(node)

class StringLiteralUpdater:
    """Update string literals containing 'balance' references."""

    def __init__(self):
        self.modified = False

    def update_string_literals(self, source_code: str) -> str:
        """Update string literals in the source code."""
        # Common patterns to update in strings
        patterns = [
            ('"balance"', '"sight_balance"'),
            ("'balance'", "'sight_balance'"),
            ('"balance":', '"sight_balance":'),
            ("'balance':", "'sight_balance':"),
            ('balance=', 'sight_balance='),
            ('balance,', 'sight_balance,'),
            ('balance,', 'sight_balance,'),
            ('balance,', 'sight_balance,'),
        ]

        result = source_code
        for old, new in patterns:
            if old in result:
                result = result.replace(old, new)
                self.modified = True

        return result

def migrate_file(file_path: Path, dry_run: bool = False) -> Tuple[bool, str]:
    """Migrate a single Python file from balance to sight_balance."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source_code = f.read()

        # Parse the AST
        tree = ast.parse(source_code, filename=str(file_path))

        # Apply AST transformations
        transformer = BalanceToSightBalanceTransformer()
        new_tree = transformer.visit(tree)

        # Update string literals
        string_updater = StringLiteralUpdater()
        updated_source = string_updater.update_string_literals(ast.unparse(new_tree))

        # Apply AST changes to the string-updated source
        if transformer.modified or string_updater.modified:
            final_tree = ast.parse(updated_source, filename=str(file_path))
            final_source = ast.unparse(final_tree)

            if dry_run:
                return True, "Would update (dry run)"
            else:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(final_source)
                return True, "Updated successfully"
        else:
            return False, "No changes needed"

    except Exception as e:
        return False, f"Error: {str(e)}"

def scan_file_for_balance_references(file_path: Path) -> List[Tuple[int, str]]:
    """Scan a file for 'balance' references and return line numbers."""
    references = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                if 'balance' in line.lower() and 'sight_balance' not in line:
                    # Skip comments and docstrings
                    stripped = line.strip()
                    if stripped.startswith('#') or stripped.startswith('"') or stripped.startswith("'"):
                        continue
                    references.append((line_num, line.strip()))
    except Exception:
        pass

    return references

def main():
    parser = argparse.ArgumentParser(
        description="Migrate Python code from 'balance' to 'sight_balance' for naming consistency."
    )
    parser.add_argument(
        'files',
        nargs='*',
        help='Python files to migrate'
    )
    parser.add_argument(
        '--directory',
        help='Directory to scan and migrate all Python files'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be changed without making changes'
    )
    parser.add_argument(
        '--scan-only',
        action='store_true',
        help='Only scan for balance references without migrating'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed information'
    )

    args = parser.parse_args()

    files_to_process = []

    # Collect files to process
    if args.directory:
        dir_path = Path(args.directory)
        if dir_path.is_dir():
            files_to_process.extend(dir_path.glob('**/*.py'))
    elif args.files:
        files_to_process.extend(Path(f) for f in args.files)

    # Remove duplicates and filter
    files_to_process = list(set(files_to_process))
    files_to_process = [f for f in files_to_process if f.is_file() and f.suffix == '.py']

    if not files_to_process:
        log("No Python files found to process.", level="INFO")
        return

    total_files = len(files_to_process)
    modified_files = 0
    error_files = 0

    log(f"Processing {total_files} Python files...", level="INFO")

    for file_path in files_to_process:
        if args.scan_only:
            references = scan_file_for_balance_references(file_path)
            if references:
                log(f"File: {file_path}", level="INFO")
                log(f"Found {len(references)} 'balance' references:", level="INFO")
                for line_num, line in references[:10]:  # Show first 10
                    log(f"  {line_num}: {line}", level="INFO")
                if len(references) > 10:
                    log(f"  ... and {len(references) - 10} more", level="INFO")
        else:
            if args.verbose:
                log(f"Processing: {file_path}", level="INFO")

            success, message = migrate_file(file_path, args.dry_run)

            if success and "Updated" in message:
                modified_files += 1
                if args.verbose:
                    log(f"  ✓ {message}", level="INFO")
            elif success and "Would update" in message:
                modified_files += 1
                if args.verbose:
                    log(f"  ✓ {message}", level="INFO")
            elif not success and "Error" in message:
                error_files += 1
                log(f"  ✗ {message}", level="WARNING")
            elif args.verbose:
                log(f"  - {message}", level="INFO")

    log("Migration complete:", level="INFO")
    log(f"  Files processed: {total_files}", level="INFO")
    log(f"  Files modified: {modified_files}", level="INFO")
    log(f"  Errors: {error_files}", level="INFO")

    if args.dry_run:
        log("No changes were made (dry run mode).", level="INFO")
    elif args.scan_only:
        log("Scan complete. Use without --scan-only to migrate.", level="INFO")

if __name__ == "__main__":
    main()
