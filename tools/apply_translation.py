#!/usr/bin/env python3
"""Batch apply translation edits or repack diachn from command line."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from translation_store import (
    add_char_to_rosetta,
    apply_line_edit,
    char_help,
    load_translation_rows,
    repack_diachn,
    save_edits,
    load_edits,
)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    tool_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="Apply Chinese translation edits to diachn")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="List rows with pending edits")
    p_list.add_argument("--line", type=int)

    p_set = sub.add_parser("set", help="Set one line translation")
    p_set.add_argument("--line", type=int, required=True)
    p_set.add_argument("--text", required=True, help="Chinese display text (include {tags} if needed)")
    p_set.add_argument("--speaker", default=None)

    p_import = sub.add_parser("import", help="Import edits JSON { \"5\": {\"cn_text\": \"...\"}, ... }")
    p_import.add_argument("file", type=Path)

    p_repack = sub.add_parser("repack", help="Write diachn with all pending edits")
    p_repack.add_argument("--target", choices=("game", "repacked", "working"), default="game")
    p_repack.add_argument("--no-backup", action="store_true")

    p_add = sub.add_parser("add-char", help="Assign a new character to an empty Rosetta slot")
    p_add.add_argument("char")
    p_add.add_argument("--index", type=int)

    sub.add_parser("slots", help="Show empty glyph slot info")

    args = parser.parse_args()

    try:
        if args.cmd == "list":
            rows, dia_path = load_translation_rows(tool_dir)
            print(f"Source: {dia_path}")
            edits = load_edits(tool_dir)
            for row in rows:
                if args.line and int(row["line"]) != args.line:
                    continue
                mark = "*" if row["edited"] else " "
                print(f"{mark} {row['line']:>4}  {row['speaker_en']:<8}  {row['en_text'][:50]}")
                if row["edited"]:
                    print(f"      CN: {edits[row['line']]['cn_text'][:60]}")
            return 0

        if args.cmd == "set":
            result = apply_line_edit(tool_dir, args.line, args.text, args.speaker)
            if not result["ok"]:
                print("验证失败:", result.get("validation"))
                return 1
            print(f"已保存第 {args.line} 行（共 {result['edited_count']} 处修改，待 repack）")
            return 0

        if args.cmd == "import":
            payload = json.loads(args.file.read_text(encoding="utf-8"))
            edits = load_edits(tool_dir)
            edits.update({str(k): v for k, v in payload.items()})
            save_edits(tool_dir, edits)
            print(f"已导入 {len(payload)} 条，累计 {len(edits)} 条待写入")
            return 0

        if args.cmd == "repack":
            result = repack_diachn(tool_dir, target=args.target, backup=not args.no_backup)
            print(f"已写入 {result['applied']} 条 → {result['output']}")
            if result["backups"]:
                print("备份:", ", ".join(result["backups"]))
            return 0

        if args.cmd == "add-char":
            result = add_char_to_rosetta(tool_dir, args.char, args.index)
            print(f"#{result['index']} ← {result['char']}")
            print("字形图:", result["glyph_png"])
            return 0

        if args.cmd == "slots":
            info = char_help(tool_dir)
            print(json.dumps(info, ensure_ascii=False, indent=2))
            return 0

    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
