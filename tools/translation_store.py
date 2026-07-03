"""Load, edit, and repack Iconoclasts Chinese dialogue (diachn)."""

from __future__ import annotations

import json
from pathlib import Path

from build_dialogue_crossref import (
    decode_speaker,
    decode_with_rosetta,
    load_rosetta,
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


def _norm_dialogue(text: str) -> str:
    return (text or "").replace("\r\n", "\n").replace("\r", "\n").replace("\n", "{new}")


def _line_baselines(dia, index: int, lines: list[str]) -> tuple[str, str]:
    speaker_cn_raw = raw_to_str(dia.speakers[index]) if index < len(dia.speakers) else ""
    sent_cn = dia.sentences[index] if index < len(dia.sentences) else b""
    gc_cn = dia.gamecodes[index] if index < len(dia.gamecodes) else b""
    _, cn_raw, _ = pick_dialogue_raw(sent_cn, gc_cn)
    cn_baseline = decode_cn_text(cn_raw, lines)
    speaker_baseline = decode_cn_text(speaker_cn_raw, lines) if speaker_cn_raw else ""
    return cn_baseline, speaker_baseline


def edit_differs_from_baseline(
    edit: dict,
    cn_baseline: str,
    speaker_baseline: str,
) -> bool:
    if "cn_text" in edit and _norm_dialogue(edit["cn_text"]) != _norm_dialogue(cn_baseline):
        return True
    if "speaker_cn" in edit and (edit.get("speaker_cn") or "") != speaker_baseline:
        return True
    return False


def prune_edits(tool_dir: Path) -> int:
    """Drop cached edits that match the current diachn baseline."""
    paths = tool_paths(tool_dir)
    edits = load_edits(tool_dir)
    if not edits:
        return 0

    dia = parse_dia_file(resolve_dia_path(tool_dir))
    lines = merged_rosetta_lines(tool_dir)
    kept: dict[str, dict] = {}
    removed = 0

    for line_no, edit in edits.items():
        index = int(line_no) - 1
        if index < 0 or index >= row_count(dia):
            removed += 1
            continue
        cn_baseline, speaker_baseline = _line_baselines(dia, index, lines)
        if edit_differs_from_baseline(edit, cn_baseline, speaker_baseline):
            kept[line_no] = edit
        else:
            removed += 1

    if removed:
        if kept:
            save_edits(tool_dir, kept)
        elif paths["edits"].exists():
            paths["edits"].unlink()

    return removed


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
    prune_edits(tool_dir)
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
        cn_baseline, speaker_baseline = _line_baselines(dia, i, lines)

        edit = edits.get(line_no, {})
        cn_display = edit["cn_text"] if "cn_text" in edit else cn_baseline
        speaker_cn = edit["speaker_cn"] if "speaker_cn" in edit else speaker_baseline

        rows.append(
            {
                "line": line_no,
                "speaker_en": cross.get("speaker_en", ""),
                "speaker_cn": speaker_cn,
                "speaker_cn_raw": raw_to_str(dia.speakers[i]) if i < len(dia.speakers) else "",
                "en_text": cross.get("en_text", ""),
                "cn_text": cn_display,
                "cn_encoding": pick_dialogue_raw(
                    dia.sentences[i] if i < len(dia.sentences) else b"",
                    dia.gamecodes[i] if i < len(dia.gamecodes) else b"",
                )[1],
                "cn_field": cross.get("cn_field", ""),
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

    dia = parse_dia_file(resolve_dia_path(tool_dir))
    index = line - 1
    cn_baseline, speaker_baseline = _line_baselines(dia, index, lines)

    entry: dict = {"cn_text": cn_text.replace("\n", "{new}")}
    if speaker_cn is not None:
        entry["speaker_cn"] = speaker_cn

    edits = load_edits(tool_dir)
    line_key = str(line)
    if edit_differs_from_baseline(entry, cn_baseline, speaker_baseline):
        edits[line_key] = entry
    elif line_key in edits:
        del edits[line_key]

    if edits:
        save_edits(tool_dir, edits)
    else:
        path = tool_paths(tool_dir)["edits"]
        if path.exists():
            path.unlink()

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
    prune_edits(tool_dir)
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

        wrote = False
        if "cn_text" in edit:
            cn_text = edit["cn_text"]
            encoded = encode_to_pipe(cn_text.replace("\n", "{new}"), lines).encode("utf-8")
            if cn_field == "sentence":
                while len(dia.sentences) <= index:
                    dia.sentences.append(b"")
                dia.sentences[index] = encoded
            else:
                while len(dia.gamecodes) <= index:
                    dia.gamecodes.append(b"")
                dia.gamecodes[index] = encoded
            wrote = True

        if "speaker_cn" in edit:
            speaker_encoded = encode_to_pipe(edit["speaker_cn"], lines).encode("utf-8")
            while len(dia.speakers) <= index:
                dia.speakers.append(b"")
            dia.speakers[index] = speaker_encoded
            wrote = True

        if wrote:
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


def _speaker_en_for_line(
    line_no: int,
    cross_by_line: dict[str, dict],
    en_dia,
    rosetta: list[str],
) -> str:
    cross = cross_by_line.get(str(line_no), {})
    speaker_en = cross.get("speaker_en", "")
    if speaker_en:
        return speaker_en
    index = line_no - 1
    if index < 0 or index >= row_count(en_dia):
        return ""
    speaker_raw = en_dia.speakers[index] if index < len(en_dia.speakers) else b""
    return decode_speaker(speaker_raw, rosetta) if speaker_raw else ""


def import_paratranz_to_edits(
    tool_dir: Path,
    dialogue_map: dict[str, dict],
    speaker_map: dict[str, dict],
) -> dict:
    """Apply ParaTranz JSON translations to translation_edits.json (editor workflow)."""
    from paratranz_convert import (
        LINE_KEY_RE,
        build_speaker_lookup,
        lookup_speaker_translation,
        paratranz_entry_translation,
        speaker_translations,
    )

    crossref = load_crossref(tool_dir)
    cross_by_line = {row["line"]: row for row in crossref}
    lines = merged_rosetta_lines(tool_dir)
    dia = parse_dia_file(resolve_dia_path(tool_dir))
    total_lines = row_count(dia)
    en_path = tool_paths(tool_dir)["game_dir"] / "data" / "dia"
    en_dia = parse_dia_file(en_path) if en_path.exists() else dia
    rosetta = load_rosetta(tool_paths(tool_dir)["tool_dir"] / "Rosetta.txt")
    edits = load_edits(tool_dir)

    applied_dialogue = 0
    applied_speakers = 0
    skipped_empty = 0
    skipped_unchanged = 0
    validation_errors: list[dict] = []

    def stage_edit(line_no: int) -> dict:
        return edits.setdefault(str(line_no), {})

    speakers_by_original, speakers_by_line, speaker_key_errors = speaker_translations(speaker_map)
    speaker_lookup = build_speaker_lookup(speakers_by_original)
    validation_errors.extend(speaker_key_errors)

    def apply_speaker_line(line_no: int, translation: str, key: str) -> None:
        nonlocal applied_speakers, skipped_unchanged
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
            return

        cn_baseline, speaker_baseline = _line_baselines(dia, line_no - 1, lines)
        existing = edits.get(str(line_no), {})
        merged = {**existing, "speaker_cn": translation}
        if not edit_differs_from_baseline(merged, cn_baseline, speaker_baseline):
            skipped_unchanged += 1
            return

        stage_edit(line_no)["speaker_cn"] = translation
        applied_speakers += 1

    for key, entry in dialogue_map.items():
        match = LINE_KEY_RE.match(key)
        if not match:
            validation_errors.append({"key": key, "error": "无效的 dialogue key 格式"})
            continue

        line_no = int(match.group(1))
        if line_no < 1 or line_no > total_lines:
            validation_errors.append({"key": key, "error": f"行号 {line_no} 超出范围（共 {total_lines} 行）"})
            continue

        translation = paratranz_entry_translation(entry)
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

        cn_baseline, speaker_baseline = _line_baselines(dia, line_no - 1, lines)
        candidate = {"cn_text": display_text}
        existing = edits.get(str(line_no), {})
        merged = {**existing, **candidate}
        if edit_differs_from_baseline(merged, cn_baseline, speaker_baseline):
            stage_edit(line_no)["cn_text"] = display_text
            applied_dialogue += 1
        else:
            skipped_unchanged += 1

        speaker_en = _speaker_en_for_line(line_no, cross_by_line, en_dia, rosetta)
        speaker_tr = lookup_speaker_translation(speaker_lookup, speaker_en)
        if speaker_tr:
            apply_speaker_line(line_no, speaker_tr, f"speaker:{speaker_en}")

    for line_no, translation in sorted(speakers_by_line.items()):
        apply_speaker_line(line_no, translation, f"line.{line_no:05d}.speaker")

    if speakers_by_original:
        for line_no in range(1, total_lines + 1):
            if line_no in speakers_by_line:
                continue
            speaker_en = _speaker_en_for_line(line_no, cross_by_line, en_dia, rosetta)
            if not speaker_en:
                continue
            translation = lookup_speaker_translation(speaker_lookup, speaker_en)
            if not translation:
                continue
            apply_speaker_line(line_no, translation, f"speaker:{speaker_en}")

    if applied_dialogue or applied_speakers:
        save_edits(tool_dir, edits)
    prune_edits(tool_dir)

    return {
        "ok": not validation_errors,
        "applied_dialogue": applied_dialogue,
        "applied_speakers": applied_speakers,
        "skipped_empty": skipped_empty,
        "skipped_unchanged": skipped_unchanged,
        "edited_count": len(load_edits(tool_dir)),
        "validation_errors": validation_errors,
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
