#!/usr/bin/env python3
"""Export/import Iconoclasts dialogue for ParaTranz JSON workflow."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from build_dialogue_crossref import (
    build_rows,
    decode_speaker,
    decode_speaker_cn,
    decode_with_rosetta,
    is_dialogue_payload,
    load_rosetta,
    load_rosetta_cn,
    pick_dialogue_raw,
    raw_to_str,
)
from dia_encode import encode_to_pipe, validate_text
from dia_parser import parse_dia_file, row_count
from dia_writer import backup_file, read_header_count, write_dia_file
from translation_store import load_crossref, merged_rosetta_lines, tool_paths

LINE_KEY_RE = re.compile(r"^line\.(\d+)$")
SPEAKER_LINE_KEY_RE = re.compile(r"^line\.(\d+)\.speaker$")
UNIQUE_SPEAKER_KEY_RE = re.compile(r"^speaker\..+$")


def _speaker_slug(name: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z\u0080-\uFFFF]+", "_", name.strip())
    slug = slug.strip("_").upper()
    return slug or "UNKNOWN"


def _unique_speaker_key(name: str, used: set[str]) -> str:
    base = f"speaker.{_speaker_slug(name)}"
    key = base
    suffix = 2
    while key in used:
        key = f"{base}_{suffix}"
        suffix += 1
    used.add(key)
    return key


def _tool_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def _build_context(**parts: str | int) -> str:
    return "; ".join(f"{key}={value}" for key, value in parts.items() if value != "")


def export_paratranz(
    tool_dir: Path,
    *,
    game_dir: Path,
    out_dir: Path,
    dialogue_out: Path,
    speakers_out: Path,
) -> dict:
    en_path = game_dir / "data" / "dia"
    cn_path = game_dir / "data" / "diachn"
    rosetta_path = tool_dir / "Rosetta.txt"
    rosetta_cn_path = tool_dir / "Rosetta_CN.txt"

    for path in (en_path, cn_path, rosetta_path):
        if not path.exists():
            raise FileNotFoundError(f"缺少文件: {path}")

    rosetta = load_rosetta(rosetta_path)
    cn_map = load_rosetta_cn(rosetta_cn_path)
    merged_lines = merged_rosetta_lines(tool_dir)
    en_data = parse_dia_file(en_path)
    cn_data = parse_dia_file(cn_path)

    rows = build_rows(en_data, cn_data, rosetta, cn_map, cn_diff_only=False)

    dialogue_entries: list[dict] = []
    speaker_groups: dict[str, dict] = {}
    skipped = 0

    for row in rows:
        line_no = int(row["line"])
        en_raw = row["en_encoding"]
        if not is_dialogue_payload(en_raw):
            skipped += 1
            continue

        cn_raw = row["cn_encoding"]
        cn_text = decode_with_rosetta(cn_raw, merged_lines) if cn_raw else ""

        dialogue_entries.append(
            {
                "key": f"line.{line_no:05d}",
                "original": row["en_text"],
                "translation": cn_text,
                "context": _build_context(
                    speaker_en=row["speaker_en"],
                    cn_field=row["cn_field"],
                    en_encoding=en_raw,
                    line=line_no,
                ),
            }
        )

        speaker_en = row["speaker_en"]
        if not speaker_en:
            continue

        group = speaker_groups.setdefault(
            speaker_en,
            {
                "original": speaker_en,
                "translation": row["speaker_cn"],
                "lines": [],
                "encodings": set(),
            },
        )
        group["lines"].append(line_no)
        if row["speaker_cn_indices"]:
            group["encodings"].add(row["speaker_cn_indices"])
        if not group["translation"] and row["speaker_cn"]:
            group["translation"] = row["speaker_cn"]

    speaker_entries: list[dict] = []
    used_speaker_keys: set[str] = set()
    for speaker_en in sorted(speaker_groups, key=lambda name: min(speaker_groups[name]["lines"])):
        info = speaker_groups[speaker_en]
        lines = sorted(info["lines"])
        encoding = next(iter(info["encodings"])) if len(info["encodings"]) == 1 else ""
        speaker_entries.append(
            {
                "key": _unique_speaker_key(speaker_en, used_speaker_keys),
                "original": info["original"],
                "translation": info["translation"],
                "context": _build_context(
                    speaker_encoding=encoding,
                    line_count=len(lines),
                    first_line=lines[0],
                    last_line=lines[-1],
                ),
            }
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    dialogue_out.write_text(
        json.dumps(dialogue_entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    speakers_out.write_text(
        json.dumps(speaker_entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "dialogue_count": len(dialogue_entries),
        "speaker_count": len(speaker_entries),
        "unique_speakers": len(speaker_groups),
        "skipped_non_dialogue": skipped,
        "total_rows": len(rows),
        "dialogue_out": str(dialogue_out),
        "speakers_out": str(speakers_out),
    }


def _parse_paratranz_entries(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{path} 应为 JSON 数组")
    return {entry["key"]: entry for entry in payload if entry.get("key")}


def _speaker_translations(
    speaker_map: dict[str, dict],
) -> tuple[dict[str, str], dict[int, str], list[dict]]:
    """Return (by English name, by line number for legacy keys, validation errors)."""
    by_original: dict[str, str] = {}
    by_line: dict[int, str] = {}
    errors: list[dict] = []

    for key, entry in speaker_map.items():
        translation = (entry.get("translation") or "").strip()
        if not translation:
            continue

        line_match = SPEAKER_LINE_KEY_RE.match(key)
        if line_match:
            by_line[int(line_match.group(1))] = translation
            continue

        if not UNIQUE_SPEAKER_KEY_RE.match(key):
            errors.append({"key": key, "error": "无效的 speaker key 格式"})
            continue

        original = (entry.get("original") or "").strip()
        if not original:
            errors.append({"key": key, "error": "缺少 original（英文说话人名）"})
            continue

        if original in by_original and by_original[original] != translation:
            errors.append(
                {
                    "key": key,
                    "error": f"说话人 {original!r} 存在冲突译文",
                }
            )
            continue
        by_original[original] = translation

    return by_original, by_line, errors


def _apply_speaker_translation(
    *,
    line_no: int,
    translation: str,
    lines: list[str],
    dia,
    validation_errors: list[dict],
    encode_errors: list[dict],
    key: str,
) -> bool:
    index = line_no - 1
    if index < 0 or index >= row_count(dia):
        validation_errors.append({"key": key, "error": f"行号 {line_no} 超出范围"})
        return False

    validation = validate_text(translation, lines)
    if not validation["ok"]:
        validation_errors.append(
            {
                "key": key,
                "line": line_no,
                "field": "speaker",
                "missing": validation["missing"],
            }
        )
        return False

    try:
        encoded = encode_to_pipe(translation, lines).encode("utf-8")
    except ValueError as exc:
        encode_errors.append({"key": key, "line": line_no, "error": str(exc)})
        return False

    while len(dia.speakers) <= index:
        dia.speakers.append(b"")
    dia.speakers[index] = encoded
    return True


def _resolve_cn_field(tool_dir: Path, line_no: int, dia, cross_by_line: dict[str, dict]) -> str:
    cross = cross_by_line.get(str(line_no), {})
    if cross.get("cn_field"):
        return cross["cn_field"]

    index = line_no - 1
    sent_cn = dia.sentences[index] if index < len(dia.sentences) else b""
    gc_cn = dia.gamecodes[index] if index < len(dia.gamecodes) else b""
    cn_field, _, _ = pick_dialogue_raw(sent_cn, gc_cn)
    return cn_field


def import_paratranz(
    tool_dir: Path,
    *,
    game_dir: Path,
    dialogue_in: Path,
    speakers_in: Path,
    target: str,
    dry_run: bool,
) -> dict:
    paths = tool_paths(tool_dir)
    source_path = paths["dia_cn"]
    if not source_path.exists():
        source_path = paths["working"]
    if not source_path.exists():
        raise FileNotFoundError("找不到 diachn，请先从游戏 data 目录复制")

    dia = parse_dia_file(source_path)
    lines = merged_rosetta_lines(tool_dir)
    cross_by_line = {row["line"]: row for row in load_crossref(tool_dir)}

    dialogue_map = _parse_paratranz_entries(dialogue_in)
    speaker_map = _parse_paratranz_entries(speakers_in)

    applied_dialogue = 0
    applied_speakers = 0
    skipped_empty = 0
    validation_errors: list[dict] = []
    encode_errors: list[dict] = []

    for key, entry in dialogue_map.items():
        match = LINE_KEY_RE.match(key)
        if not match:
            validation_errors.append({"key": key, "error": "无效的 dialogue key 格式"})
            continue

        line_no = int(match.group(1))
        index = line_no - 1
        if index < 0 or index >= row_count(dia):
            validation_errors.append({"key": key, "error": f"行号 {line_no} 超出范围"})
            continue

        translation = (entry.get("translation") or "").strip()
        if not translation:
            skipped_empty += 1
            continue

        display_text = translation.replace("\n", "{new}")
        validation = validate_text(display_text, lines)
        if not validation["ok"]:
            validation_errors.append(
                {
                    "key": key,
                    "line": line_no,
                    "field": "dialogue",
                    "missing": validation["missing"],
                }
            )
            continue

        try:
            encoded = encode_to_pipe(display_text, lines).encode("utf-8")
        except ValueError as exc:
            encode_errors.append({"key": key, "line": line_no, "error": str(exc)})
            continue

        cn_field = _resolve_cn_field(tool_dir, line_no, dia, cross_by_line)
        if cn_field == "sentence":
            while len(dia.sentences) <= index:
                dia.sentences.append(b"")
            dia.sentences[index] = encoded
        else:
            while len(dia.gamecodes) <= index:
                dia.gamecodes.append(b"")
            dia.gamecodes[index] = encoded
        applied_dialogue += 1

    speakers_by_original, speakers_by_line, speaker_key_errors = _speaker_translations(speaker_map)
    validation_errors.extend(speaker_key_errors)

    for line_no, translation in sorted(speakers_by_line.items()):
        key = f"line.{line_no:05d}.speaker"
        if _apply_speaker_translation(
            line_no=line_no,
            translation=translation,
            lines=lines,
            dia=dia,
            validation_errors=validation_errors,
            encode_errors=encode_errors,
            key=key,
        ):
            applied_speakers += 1

    if speakers_by_original:
        total = row_count(dia)
        for line_no in range(1, total + 1):
            if line_no in speakers_by_line:
                continue

            cross = cross_by_line.get(str(line_no), {})
            speaker_en = cross.get("speaker_en", "")
            if not speaker_en:
                continue

            translation = speakers_by_original.get(speaker_en)
            if not translation:
                continue

            key = f"speaker:{speaker_en}"
            if _apply_speaker_translation(
                line_no=line_no,
                translation=translation,
                lines=lines,
                dia=dia,
                validation_errors=validation_errors,
                encode_errors=encode_errors,
                key=key,
            ):
                applied_speakers += 1

    result = {
        "dry_run": dry_run,
        "applied_dialogue": applied_dialogue,
        "applied_speakers": applied_speakers,
        "skipped_empty": skipped_empty,
        "validation_errors": validation_errors,
        "encode_errors": encode_errors,
        "output": None,
        "backups": [],
        "working_copy": None,
    }

    if dry_run or (applied_dialogue == 0 and applied_speakers == 0):
        return result

    if target == "game":
        out_path = paths["dia_cn"]
    elif target == "working":
        out_path = paths["working"]
    else:
        out_path = paths["repacked"]

    if out_path.exists():
        result["backups"].append(str(backup_file(out_path)))

    header_rows = read_header_count(source_path)
    write_dia_file(out_path, dia, row_count=header_rows)
    write_dia_file(paths["working"], dia, row_count=header_rows)

    result["output"] = str(out_path)
    result["working_copy"] = str(paths["working"])
    return result


def cmd_export(args: argparse.Namespace) -> int:
    tool_dir = _tool_dir()
    paths = tool_paths(tool_dir)
    game_dir = args.game_dir or paths["game_dir"]
    out_dir = args.out_dir or (Path(__file__).resolve().parent / "paratranz")
    dialogue_out = args.dialogue_out or (out_dir / "dialogue.json")
    speakers_out = args.speakers_out or (out_dir / "speakers.json")

    stats = export_paratranz(
        tool_dir,
        game_dir=game_dir,
        out_dir=out_dir,
        dialogue_out=dialogue_out,
        speakers_out=speakers_out,
    )

    print(
        f"导出完成: {stats['dialogue_count']} 条台词, "
        f"{stats['speaker_count']} 个说话人（去重后）"
    )
    print(f"  跳过非台词行: {stats['skipped_non_dialogue']} / {stats['total_rows']}")
    print(f"  台词: {stats['dialogue_out']}")
    print(f"  说话人: {stats['speakers_out']}")
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    tool_dir = _tool_dir()
    paths = tool_paths(tool_dir)
    game_dir = args.game_dir or paths["game_dir"]
    paratranz_dir = Path(__file__).resolve().parent / "paratranz"
    dialogue_in = args.dialogue_in or (paratranz_dir / "dialogue.json")
    speakers_in = args.speakers_in or (paratranz_dir / "speakers.json")

    if not dialogue_in.exists() and not speakers_in.exists():
        print(f"Error: 找不到 {dialogue_in} 或 {speakers_in}")
        return 1

    result = import_paratranz(
        tool_dir,
        game_dir=game_dir,
        dialogue_in=dialogue_in,
        speakers_in=speakers_in,
        target=args.target,
        dry_run=args.dry_run,
    )

    mode = "（预览）" if result["dry_run"] else ""
    print(f"导入{mode}: 台词 {result['applied_dialogue']} 条, 说话人 {result['applied_speakers']} 条")
    print(f"  跳过空译文: {result['skipped_empty']}")

    if result["validation_errors"]:
        print(f"  缺字/验证失败: {len(result['validation_errors'])} 条")
        for item in result["validation_errors"][:10]:
            print(f"    {item}")
        if len(result["validation_errors"]) > 10:
            print(f"    ... 另有 {len(result['validation_errors']) - 10} 条")

    if result["encode_errors"]:
        print(f"  编码失败: {len(result['encode_errors'])} 条")
        for item in result["encode_errors"][:10]:
            print(f"    {item}")

    if result["output"]:
        print(f"  已写入: {result['output']}")
        if result["backups"]:
            print(f"  备份: {', '.join(result['backups'])}")

    if result["validation_errors"] or result["encode_errors"]:
        return 1
    return 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="ParaTranz JSON ↔ Iconoclasts diachn 转换")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_export = sub.add_parser("export", help="导出 dialogue.json 与 speakers.json")
    p_export.add_argument("--game-dir", type=Path, default=None, help="游戏根目录（含 data/dia）")
    p_export.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="输出目录，默认 tools/paratranz",
    )
    p_export.add_argument("--dialogue-out", type=Path, default=None)
    p_export.add_argument("--speakers-out", type=Path, default=None)
    p_export.set_defaults(func=cmd_export)

    p_import = sub.add_parser("import", help="从 ParaTranz JSON 写回 diachn")
    p_import.add_argument("--game-dir", type=Path, default=None)
    p_import.add_argument("--dialogue-in", type=Path, default=None)
    p_import.add_argument("--speakers-in", type=Path, default=None)
    p_import.add_argument(
        "--target",
        choices=("game", "working", "repacked"),
        default="working",
        help="写入目标（默认 working，确认后再写 game）",
    )
    p_import.add_argument("--dry-run", action="store_true", help="仅验证，不写文件")
    p_import.set_defaults(func=cmd_import)

    args = parser.parse_args()
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
