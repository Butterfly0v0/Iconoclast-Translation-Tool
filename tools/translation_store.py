"""Load, edit, and repack Iconoclasts Chinese dialogue (diachn)."""

from __future__ import annotations

import json
from pathlib import Path

from build_dialogue_crossref import (
    decode_with_rosetta,
    pick_dialogue_raw,
    raw_to_str,
)
from dia_encode import assign_char, encode_to_pipe, validate_text
from dia_parser import parse_dia_file, row_count
from dia_writer import backup_file, read_header_count, write_dia_file
from rosetta_store import load_table, save_table

PUA_BASE = 0xE000
GLYPH_MAX_INDEX = 3536


def tool_paths(tool_dir: Path) -> dict[str, Path]:
    game_dir = tool_dir.parent
    return {
        "tool_dir": tool_dir,
        "game_dir": game_dir,
        "dia_cn": game_dir / "data" / "diachn",
        "crossref": tool_dir / "tools" / "dialogue_crossref.json",
        "repacked": tool_dir / "Repacked File" / "diachn",
        "working": tool_dir / "diachn",
        "po": tool_dir / "bin" / "Release" / "net7.0" / "Extracted text" / "Iconoclast.po",
        "edits": tool_dir / "tools" / "translation_edits.json",
    }


def merged_rosetta_lines(tool_dir: Path) -> list[str]:
    lines, _ = load_table(tool_dir)
    return lines


def decode_cn_text(raw: str, lines: list[str]) -> str:
    return decode_with_rosetta(raw, lines)


def load_crossref(tool_dir: Path) -> list[dict]:
    path = tool_paths(tool_dir)["crossref"]
    if not path.exists():
        raise FileNotFoundError(f"缺少对照表 {path}，请先运行 build_dialogue_crossref.py --cn-diff-only")
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_dia_path(tool_dir: Path) -> Path:
    paths = tool_paths(tool_dir)
    for candidate in (paths["working"], paths["dia_cn"], paths["repacked"]):
        if candidate.exists():
            return candidate
    raise FileNotFoundError("找不到 diachn，请先从游戏 data 目录复制到工具目录")


def load_translation_rows(tool_dir: Path) -> tuple[list[dict], Path]:
    crossref = load_crossref(tool_dir)
    dia_path = resolve_dia_path(tool_dir)
    dia = parse_dia_file(dia_path)
    lines = merged_rosetta_lines(tool_dir)
    edits = load_edits(tool_dir)

    rows: list[dict] = []
    cross_by_line = {row["line"]: row for row in crossref}

    total = row_count(dia)
    for i in range(total):
        line_no = str(i + 1)
        cross = cross_by_line.get(line_no, {})
        speaker_cn_raw = raw_to_str(dia.speakers[i]) if i < len(dia.speakers) else ""
        sent_cn = dia.sentences[i] if i < len(dia.sentences) else b""
        gc_cn = dia.gamecodes[i] if i < len(dia.gamecodes) else b""
        cn_src, cn_raw, _ = pick_dialogue_raw(sent_cn, gc_cn)

        edit = edits.get(line_no, {})
        cn_display = edit.get("cn_text") or decode_cn_text(cn_raw, lines)
        speaker_cn = edit.get("speaker_cn") or decode_cn_text(speaker_cn_raw, lines) if speaker_cn_raw else ""

        rows.append(
            {
                "line": line_no,
                "speaker_en": cross.get("speaker_en", ""),
                "speaker_cn": speaker_cn,
                "speaker_cn_raw": speaker_cn_raw,
                "en_text": cross.get("en_text", ""),
                "cn_text": cn_display,
                "cn_encoding": cn_raw,
                "cn_field": cn_src,
                "cn_indices": cross.get("cn_indices", ""),
                "edited": line_no in edits,
            }
        )

    return rows, dia_path


def load_edits(tool_dir: Path) -> dict[str, dict]:
    path = tool_paths(tool_dir)["edits"]
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_edits(tool_dir: Path, edits: dict[str, dict]) -> None:
    path = tool_paths(tool_dir)["edits"]
    path.write_text(json.dumps(edits, ensure_ascii=False, indent=2), encoding="utf-8")


def apply_line_edit(
    tool_dir: Path,
    line: int,
    cn_text: str,
    speaker_cn: str | None = None,
) -> dict:
    lines = merged_rosetta_lines(tool_dir)
    validation = validate_text(cn_text.replace("\n", "{new}"), lines)
    if not validation["ok"]:
        return {"ok": False, "validation": validation}

    if speaker_cn is not None and speaker_cn.strip():
        speaker_validation = validate_text(speaker_cn, lines)
        if not speaker_validation["ok"]:
            return {"ok": False, "validation": speaker_validation, "field": "speaker_cn"}

    edits = load_edits(tool_dir)
    entry = {"cn_text": cn_text}
    if speaker_cn is not None:
        entry["speaker_cn"] = speaker_cn
    edits[str(line)] = entry
    save_edits(tool_dir, edits)

    return {"ok": True, "line": line, "edited_count": len(edits)}


def repack_diachn(
    tool_dir: Path,
    *,
    target: str = "game",
    backup: bool = True,
) -> dict:
    """Apply pending edits and write diachn. target: game | repacked | working."""
    paths = tool_paths(tool_dir)
    dia_path = resolve_dia_path(tool_dir)
    dia = parse_dia_file(dia_path)
    lines = merged_rosetta_lines(tool_dir)
    edits = load_edits(tool_dir)

    if not edits:
        raise ValueError("没有待写入的译文修改，请先在编辑器中保存各行。")

    applied = 0
    for line_no, edit in edits.items():
        index = int(line_no) - 1
        if index < 0 or index >= row_count(dia):
            continue

        sent_cn = dia.sentences[index] if index < len(dia.sentences) else b""
        gc_cn = dia.gamecodes[index] if index < len(dia.gamecodes) else b""
        cn_field, _, _ = pick_dialogue_raw(sent_cn, gc_cn)

        cn_text = edit.get("cn_text", "")
        encoded = encode_to_pipe(cn_text.replace("\n", "{new}"), lines).encode("utf-8")

        if cn_field == "sentence":
            while len(dia.sentences) <= index:
                dia.sentences.append(b"")
            dia.sentences[index] = encoded
        else:
            while len(dia.gamecodes) <= index:
                dia.gamecodes.append(b"")
            dia.gamecodes[index] = encoded

        if edit.get("speaker_cn") is not None:
            speaker_encoded = encode_to_pipe(edit["speaker_cn"], lines).encode("utf-8")
            while len(dia.speakers) <= index:
                dia.speakers.append(b"")
            dia.speakers[index] = speaker_encoded

        applied += 1

    if target == "game":
        out_path = paths["dia_cn"]
    elif target == "working":
        out_path = paths["working"]
    else:
        out_path = paths["repacked"]

    backups: list[str] = []
    if backup and out_path.exists():
        backups.append(str(backup_file(out_path)))

    header_rows = read_header_count(dia_path)
    write_dia_file(out_path, dia, row_count=header_rows)

    # Keep working copy in tool root for CLI compatibility
    write_dia_file(paths["working"], dia, row_count=header_rows)

    return {
        "ok": True,
        "applied": applied,
        "output": str(out_path),
        "backups": backups,
        "working_copy": str(paths["working"]),
    }


def add_char_to_rosetta(
    tool_dir: Path,
    char: str,
    index: int | None = None,
    *,
    save: bool = True,
) -> dict:
    lines, max_index = load_table(tool_dir)
    if index is not None and index > GLYPH_MAX_INDEX:
        raise ValueError(f"索引 {index} 超出字形上限 {GLYPH_MAX_INDEX}")

    updated, used_index = assign_char(lines, char, index)
    if used_index > GLYPH_MAX_INDEX:
        raise ValueError(
            f"索引 {used_index} 超出 Assets.dat 字形数量（0–{GLYPH_MAX_INDEX}）。"
            "请复用未使用的索引，或手动替换 Assets.dat 中的 PNG 字形。"
        )

    written: list[str] = []
    if save:
        written = save_table(tool_dir, updated)

    return {
        "ok": True,
        "index": used_index,
        "char": char,
        "written": written,
        "glyph_png": str(tool_dir / "tools" / "glyphs" / f"{used_index:05d}.png"),
    }


def char_help(tool_dir: Path) -> dict:
    lines, max_index = load_table(tool_dir)
    from dia_encode import find_empty_slots

    empty = find_empty_slots(lines)
    return {
        "max_index": max_index,
        "glyph_limit": GLYPH_MAX_INDEX,
        "empty_slots": len(empty),
        "first_empty": empty[:20],
        "note": (
            "游戏字体共约 3537 个 22×22 字形槽位（索引 0–3536）。"
            "新增汉字应优先填入 PUA 占位符空位；若字形图不对，需用图像软件替换 "
            "tools/glyphs/NNNNN.png 并重新打包 Assets.dat（本工具暂不支持自动写入 Assets.dat）。"
        ),
    }
