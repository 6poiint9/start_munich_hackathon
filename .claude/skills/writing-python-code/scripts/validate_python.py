#!/usr/bin/env python3
"""Validate Python syntax and run Pylint when it is available."""

from __future__ import annotations

import argparse
import ast
from collections.abc import Sequence
import pathlib
import shutil
import subprocess
import sys
import tokenize


def _parse_file(file_path: pathlib.Path) -> bool:
    """Parse one Python source file and report actionable errors."""
    try:
        with tokenize.open(file_path) as source_file:
            source = source_file.read()
        ast.parse(source, filename=str(file_path))
    except (OSError, SyntaxError) as error:
        print(f"{file_path}: {error}", file=sys.stderr)
        return False
    return True


def _run_pylint(pylint_path: str, file_paths: Sequence[pathlib.Path]) -> bool:
    """Run Pylint once for all source files."""
    result = subprocess.run(
        [pylint_path, *(str(file_path) for file_path in file_paths)],
        check=False,
    )
    return result.returncode == 0


def main(argv: Sequence[str] | None = None) -> int:
    """Validate the requested Python source files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "files",
        metavar="FILE",
        nargs="+",
        type=pathlib.Path,
        help="Python source file to validate",
    )
    args = parser.parse_args(argv)

    validation_succeeded = True
    existing_files: list[pathlib.Path] = []
    for file_path in args.files:
        if not file_path.is_file():
            print(f"{file_path}: file not found", file=sys.stderr)
            validation_succeeded = False
            continue
        if file_path.suffix not in {".py", ".pyi"}:
            print(f"{file_path}: expected a .py or .pyi file", file=sys.stderr)
            validation_succeeded = False
            continue

        existing_files.append(file_path)
        validation_succeeded = _parse_file(file_path) and validation_succeeded

    pylint_path = shutil.which("pylint")
    if pylint_path is None:
        print(
            "warning: Pylint is unavailable; only syntax was validated",
            file=sys.stderr,
        )
    elif existing_files:
        validation_succeeded = (
            _run_pylint(pylint_path, existing_files) and validation_succeeded
        )

    return 0 if validation_succeeded else 1


if __name__ == "__main__":
    sys.exit(main())
