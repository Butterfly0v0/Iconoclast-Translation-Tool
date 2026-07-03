#!/usr/bin/env python3
"""Apply known Chinese text to Rosetta indices from a {#index} placeholder string."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

INDEX_RE = re.compile(r"\{#(\d+)\}")


def load_lines(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return [line for line in text.split("\n") if line != ""]


def write_lines(path: Path, lines: list[str]) -> None:
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


def parse_index_tokens(text: str) -> list[tuple[str, int | None]]:
    """Return sequence of (literal_or_empty, index_or_none)."""
    tokens: list[tuple[str, int | None]] = []
    pos = 0
    for match in INDEX_RE.finditer(text):
        if match.start() > pos:
            tokens.append((text[pos : match.start()], None))
        tokens.append(("", int(match.group(1))))
        pos = match.end()
    if pos < len(text):
        tokens.append((text[pos:], None))
    return tokens


def align_text_to_indices(index_text: str, chinese: str, base_rosetta: list[str]) -> dict[int, str]:
    index_tokens = parse_index_tokens(index_text)
    index_only = [idx for _, idx in index_tokens if idx is not None]
    literal_parts = [lit for lit, idx in index_tokens if idx is None and lit]

    mapping: dict[int, str] = {}

    # Fast path: only {#index} placeholders, no mixed literals
    if not literal_parts and len(index_only) == len(chinese):
        for idx, ch in zip(index_only, chinese):
            mapping[idx] = ch
        return mapping

    # Match literals from base Rosetta or provided Chinese string
    remaining = chinese
    for lit, idx in index_tokens:
        if idx is None:
            if not remaining.startswith(lit):
                raise ValueError(f"Literal {lit!r} not found at start of {remaining!r}")
            remaining = remaining[len(lit) :]
        else:
            if not remaining:
                raise ValueError(f"Expected character for index {idx}, but Chinese text ended")
            mapping[idx] = remaining[0]
            remaining = remaining[1:]

    if remaining:
        raise ValueError(f"Extra Chinese characters remain: {remaining!r}")

    return mapping


def apply_mapping(rosetta: list[str], mapping: dict[int, str], force: bool) -> tuple[list[str], list[str]]:
    updated = rosetta[:]
    while updated and updated[-1] == "":
        updated.pop()

    max_index = max(mapping)
    while len(updated) <= max_index:
        updated.append("")

    changes: list[str] = []
    for index, char in sorted(mapping.items()):
        if len(char) != 1:
            raise ValueError(f"Index {index}: expected one character, got {char!r}")

        old = updated[index] if index < len(updated) else ""
        is_placeholder = old and len(old) == 1 and ord(old) >= 0xE000

        if old and old != char and not force and not is_placeholder:
            changes.append(f"  skip #{index}: was {old!r}, would set {char!r} (use --force)")
            continue

        if old != char:
            updated[index] = char
            changes.append(f"  #{index}: {old!r} -> {char!r}")

    return updated, changes


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")

    tool_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Map {#index} strings to Chinese and update Rosetta_CN.txt"
    )
    parser.add_argument(
        "--indices",
        type=str,
        help='Index string, e.g. "{#3399}{#1020}!"',
    )
    parser.add_argument("--text", type=str, help="Known Chinese text, e.g. 骗子!")
    parser.add_argument(
        "--file",
        type=Path,
        help="JSON file with list of {indices, text} objects",
    )
    parser.add_argument(
        "--rosetta",
        type=Path,
        default=tool_dir / "Rosetta_CN.txt",
        help="Rosetta_CN.txt to update",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing mappings")
    args = parser.parse_args()

    if not args.rosetta.exists():
        print(f"Error: missing {args.rosetta}. Run build_rosetta_ocr.py first.")
        return 1

    base_path = tool_dir / "Rosetta.txt"
    base = load_lines(base_path) if base_path.exists() else []
    rosetta = load_lines(args.rosetta)

    pairs: list[tuple[str, str]] = []
    if args.file:
        payload = json.loads(args.file.read_text(encoding="utf-8"))
        for item in payload:
            pairs.append((item["indices"], item["text"]))
    elif args.indices and args.text:
        pairs.append((args.indices, args.text))
    else:
        parser.print_help()
        print("\nExample:")
        print('  python resolve_sentence.py --indices "{#3399}{#1020}!" --text "骗子!"')
        return 1

    all_mapping: dict[int, str] = {}
    for index_text, chinese in pairs:
        part = align_text_to_indices(index_text, chinese, base)
        for idx, ch in part.items():
            if idx in all_mapping and all_mapping[idx] != ch:
                print(f"Warning: index {idx} conflict {all_mapping[idx]!r} vs {ch!r}; keeping first")
                continue
            all_mapping[idx] = ch

    updated, changes = apply_mapping(rosetta, all_mapping, args.force)
    write_lines(args.rosetta, updated)

    for copy_dir in [tool_dir / "bin" / "Release" / "net7.0"]:
        if copy_dir.exists():
            write_lines(copy_dir / "Rosetta_CN.txt", updated)

    print(f"Updated {args.rosetta}")
    if changes:
        for line in changes:
            print(line)
    else:
        print("No changes applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
