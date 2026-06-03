"""Patcher for Open WebUI's vector DB registration files.

Injects SurrealDB support into two files inside the OWUI installation:
    - type.py:    Adds SURREALDB = 'surrealdb' to the VectorType StrEnum
    - factory.py: Adds case VectorType.SURREALDB: branch to the match/case

Both patches are idempotent — safe to run multiple times.

Usage (standalone):
    python -m owui_surrealdb_adapter.patch [--owui-root /path/to/open_webui]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Marker comment used for idempotency detection
SURREALDB_MARKER = "# owui-surrealdb-adapter"

# Default OWUI install path inside the Docker image
DEFAULT_OWUI_ROOT = "/app/backend/open_webui"


def patch_type_py(source: str) -> str:
    """Add SURREALDB member to the VectorType StrEnum.

    Args:
        source: Contents of type.py

    Returns:
        Patched source (unchanged if already patched).
    """
    if SURREALDB_MARKER in source:
        return source

    # Find the last enum member line (pattern: 4-space indent, UPPER = 'value')
    lines = source.splitlines(keepends=True)
    last_member_idx = -1
    for i, line in enumerate(lines):
        if re.match(r"^    [A-Z_]+ = '", line):
            last_member_idx = i

    if last_member_idx == -1:
        raise ValueError("Could not find any enum members in type.py")

    # Insert SURREALDB after the last member
    new_line = f"    SURREALDB = 'surrealdb'  {SURREALDB_MARKER}\n"
    lines.insert(last_member_idx + 1, new_line)

    return "".join(lines)


def patch_factory_py(source: str) -> str:
    """Add case VectorType.SURREALDB branch to the factory match/case.

    Inserts the new case immediately before `case _:` (the default/fallback).

    Args:
        source: Contents of factory.py

    Returns:
        Patched source (unchanged if already patched).

    Raises:
        ValueError: If `case _:` is not found in the source.
    """
    if SURREALDB_MARKER in source:
        return source

    # Find `case _:` line and its indentation
    lines = source.splitlines(keepends=True)
    default_idx = -1
    indent = ""
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("case _:"):
            default_idx = i
            indent = line[: len(line) - len(stripped)]
            break

    if default_idx == -1:
        raise ValueError("Could not find 'case _:' default branch in factory.py")

    # Build the new case block with matching indentation
    body_indent = indent + "    "
    new_block = (
        f"{indent}case VectorType.SURREALDB:  {SURREALDB_MARKER}\n"
        f"{body_indent}from owui_surrealdb_adapter import SurrealDBClient\n"
        f"\n"
        f"{body_indent}return SurrealDBClient()\n"
    )

    lines.insert(default_idx, new_block)

    return "".join(lines)


def patch_files(owui_root: str | Path) -> dict[str, bool]:
    """Patch both type.py and factory.py in place.

    Args:
        owui_root: Path to the open_webui package root
                   (e.g. /app/backend/open_webui)

    Returns:
        Dict mapping filename to whether it was modified.
    """
    root = Path(owui_root)
    vector_dir = root / "retrieval" / "vector"

    results: dict[str, bool] = {}

    # Patch type.py
    type_path = vector_dir / "type.py"
    type_src = type_path.read_text()
    type_patched = patch_type_py(type_src)
    if type_patched != type_src:
        type_path.write_text(type_patched)
        results["type.py"] = True
    else:
        results["type.py"] = False

    # Patch factory.py
    factory_path = vector_dir / "factory.py"
    factory_src = factory_path.read_text()
    factory_patched = patch_factory_py(factory_src)
    if factory_patched != factory_src:
        factory_path.write_text(factory_patched)
        results["factory.py"] = True
    else:
        results["factory.py"] = False

    return results


def main() -> None:
    """CLI entrypoint for standalone patching."""
    parser = argparse.ArgumentParser(
        description="Patch Open WebUI to support SurrealDB vector backend"
    )
    parser.add_argument(
        "--owui-root",
        default=DEFAULT_OWUI_ROOT,
        help=f"Path to open_webui package root (default: {DEFAULT_OWUI_ROOT})",
    )
    args = parser.parse_args()

    results = patch_files(args.owui_root)
    for filename, modified in results.items():
        status = "PATCHED" if modified else "ALREADY PATCHED"
        print(f"  {filename}: {status}")


if __name__ == "__main__":
    main()
