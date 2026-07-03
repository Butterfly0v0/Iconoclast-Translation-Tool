#!/usr/bin/env python3
"""Build Rosetta_CN.txt for Iconoclast Chinese localization.

The game maps each displayed character to a numeric index in Rosetta.txt.
Latin indices 0-155 come from the original Rosetta.txt. Chinese uses indices
up to ~3454. This script extends the table so the translation tool can encode
and decode Chinese text.

Usage (from Iconoclast-Translation-Tool folder):
    python build_rosetta_cn.py
    python build_rosetta_cn.py --game-dir "D:\\SteamLibrary\\steamapps\\common\\Iconoclasts"
"""

from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path


def load_base_rosetta(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    lines = [line for line in text.split("\n") if line != ""]
    return lines


def collect_indices(dia_path: Path) -> tuple[int, set[int]]:
    data = dia_path.read_bytes()
    indices: set[int] = set()
    for match in re.finditer(rb"(?<=[\x00|{])(\d+)(?=[\x00|}\\])", data):
        indices.add(int(match.group(1)))
    return (max(indices) if indices else 0, indices)


def try_extract_charset_from_assets(assets_path: Path, base: list[str]) -> list[str] | None:
    """Search Assets.dat for a UTF-16-LE charset matching the base Rosetta order."""
    data = assets_path.read_bytes()
    if len(base) < 2:
        return None

    prefix = "".join(base[: min(20, len(base))]).encode("utf-16-le")
    start = data.find(prefix)
    if start < 0:
        return None

    chars: list[str] = []
    offset = start
    while offset + 1 < len(data):
        codepoint = data[offset] | (data[offset + 1] << 8)
        if codepoint == 0:
            break
        chars.append(chr(codepoint))
        offset += 2
        if len(chars) > 5000:
            break

    if len(chars) <= len(base):
        return None

    if chars[: len(base)] != base:
        return None

    return chars


def build_extended_table(base: list[str], max_index: int, charset: list[str] | None) -> list[str]:
    if max_index < len(base) - 1:
        max_index = len(base) - 1

    extended = base[:]
    while len(extended) <= max_index:
        extended.append("")

    if charset and len(charset) > len(base):
        for i in range(len(base), min(len(charset), len(extended))):
            if charset[i]:
                extended[i] = charset[i]
        return extended

    for i in range(len(base), len(extended)):
        if not extended[i]:
            # Private Use Area: one unique placeholder per index for round-trip editing.
            extended[i] = chr(0xE000 + (i - len(base)))

    return extended


def write_rosetta_cn(path: Path, lines: list[str]) -> None:
    content = "\n".join(lines) + "\n"
    path.write_bytes(content.encode("utf-8"))


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build Rosetta_CN.txt for Iconoclast Chinese support")
    parser.add_argument(
        "--game-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Iconoclasts game root directory",
    )
    parser.add_argument(
        "--dia",
        type=str,
        default="diachn",
        help="Language dia file to analyze (default: diachn)",
    )
    args = parser.parse_args()

    tool_dir = Path(__file__).resolve().parent
    base_path = tool_dir / "Rosetta.txt"
    out_path = tool_dir / "Rosetta_CN.txt"
    indices_log = tool_dir / "indices_used.txt"

    if not base_path.exists():
        print(f"Error: missing {base_path}")
        return 1

    dia_path = args.game_dir / "data" / args.dia
    if not dia_path.exists():
        print(f"Error: missing {dia_path}")
        return 1

    base = load_base_rosetta(base_path)
    max_index, used = collect_indices(dia_path)
    print(f"Loaded base Rosetta: {len(base)} entries")
    print(f"Analyzed {dia_path.name}: max index = {max_index}, unique indices = {len(used)}")

    charset = None
    assets_path = args.game_dir / "Assets.dat"
    ocr_meta = tool_dir / "tools" / "rosetta_ocr_meta.json"
    if ocr_meta.exists():
        import json

        payload = json.loads(ocr_meta.read_text(encoding="utf-8"))
        entries = payload.get("entries", {})
        charset = base[:]
        for key, info in entries.items():
            idx = int(key)
            ch = info.get("char", "")
            if ch and len(ch) == 1 and ord(ch) < 0xE000:
                while len(charset) <= idx:
                    charset.append("")
                charset[idx] = ch
        print(f"Loaded OCR/manual mappings from {ocr_meta.name}")
    elif assets_path.exists():
        charset = try_extract_charset_from_assets(assets_path, base)
        if charset:
            print(f"Found embedded charset in Assets.dat ({len(charset)} characters)")
        else:
            print("Could not auto-extract charset from Assets.dat")
            print("Tip: run tools/build_rosetta_ocr.py for glyph OCR.")

    extended = build_extended_table(base, max_index, charset)
    write_rosetta_cn(out_path, extended)

    cjk_indices = sorted(i for i in used if i >= len(base))
    indices_log.write_text(
        "\n".join(str(i) for i in cjk_indices),
        encoding="utf-8",
    )

    filled = sum(
        1
        for i in range(len(base), len(extended))
        if extended[i] and ord(extended[i]) < 0xE000
    )
    placeholder = sum(
        1
        for i in range(len(base), len(extended))
        if extended[i] and ord(extended[i]) >= 0xE000
    )

    print(f"Wrote {out_path} ({len(extended)} entries)")
    print(f"  CJK entries with real characters: {filled}")
    print(f"  CJK placeholder entries (PUA): {placeholder}")
    print(f"Wrote index list to {indices_log}")

    if placeholder:
        print()
        print("Some Chinese slots use private-use placeholders (U+E000+).")
        print("Replace them in Rosetta_CN.txt with real characters before writing new Chinese text.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
