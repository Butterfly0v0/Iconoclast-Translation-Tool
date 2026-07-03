#!/usr/bin/env python3
"""Build EN/CN dialogue cross-reference for Rosetta index mapping."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
from pathlib import Path

from dia_parser import parse_dia_file, row_count

INDEX_PIPE_RE = re.compile(r"\|(\d+)")
INDEX_LEAD_RE = re.compile(r"^(\d+)(?=\||$)")


def load_rosetta(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return [line for line in text.split("\n") if line != ""]


def load_rosetta_cn(path: Path) -> dict[int, str]:
    if not path.exists():
        return {}
    lines = load_rosetta(path)
    mapping: dict[int, str] = {}
    for index, char in enumerate(lines):
        if char and len(char) == 1 and ord(char) < 0xE000:
            mapping[index] = char
    return mapping


def raw_to_str(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace")


SKIP_TEXTS = {"buttons", ""}
SKIP_PREFIXES = ("whotalk", "1\\", "2\\", "3\\")


def extract_indices(text: str) -> list[int]:
    indices = [int(match.group(1)) for match in INDEX_PIPE_RE.finditer(text)]
    lead = INDEX_LEAD_RE.match(text)
    if lead:
        indices.insert(0, int(lead.group(1)))
    return indices


def _split_brace_blocks(text: str) -> list[tuple[str, str]]:
    """Split into ('block', '{...}') and ('text', '...') preserving order."""
    parts: list[tuple[str, str]] = []
    i = 0
    while i < len(text):
        if text[i] == "{":
            j = text.find("}", i)
            if j == -1:
                parts.append(("text", text[i:]))
                break
            parts.append(("block", text[i : j + 1]))
            i = j + 1
            if i < len(text) and text[i] == "|":
                i += 1
            continue
        j = i
        while j < len(text) and text[j] != "{":
            j += 1
        if j > i:
            parts.append(("text", text[i:j]))
        i = j
    return parts


def _decode_index_run(text: str, char_at) -> str:
    """Decode pipe-separated index runs outside {tags}."""
    out: list[str] = []
    i = 0
    while i < len(text):
        if text[i] == "|":
            i += 1
            if i >= len(text):
                break
        if i >= len(text):
            break
        if not text[i].isdigit():
            out.append(text[i])
            i += 1
            continue
        start = i
        while i < len(text) and text[i].isdigit():
            i += 1
        out.append(char_at(int(text[start:i])))
    return "".join(out)


def decode_with_rosetta(text: str, rosetta: list[str]) -> str:
    """Decode pipe-index segments; keep {tags} as-is."""

    if not text:
        return text

    def char_at(index: int) -> str:
        if 0 <= index < len(rosetta) and rosetta[index]:
            return rosetta[index]
        return f"{{#{index}}}"

    chunks: list[str] = []
    for kind, segment in _split_brace_blocks(text):
        if kind == "block":
            chunks.append(segment)
        else:
            chunks.append(_decode_index_run(segment, char_at))
    return "".join(chunks)


def decode_index_string(text: str, rosetta: list[str]) -> str:
    """Decode strings that are only pipe-separated indices (e.g. speaker names)."""
    if not text or "{" in text:
        return decode_with_rosetta(text, rosetta)
    indices = extract_indices(text)
    if not indices:
        return text
    only_indices = re.fullmatch(r"[\d|]+", text) is not None
    if only_indices:
        chars = []
        for index in indices:
            if 0 <= index < len(rosetta) and rosetta[index]:
                chars.append(rosetta[index])
            else:
                chars.append(f"{{#{index}}}")
        return "".join(chars)
    return decode_with_rosetta(text, rosetta)


def indices_to_braces(indices: list[int], suffix: str = "") -> str:
    body = "".join(f"{{#{index}}}" for index in indices)
    return body + suffix


def is_dialogue_payload(text: str) -> bool:
    if text in SKIP_TEXTS:
        return False
    if text.startswith(SKIP_PREFIXES):
        return False
    return bool(extract_indices(text) or "{" in text)


def pick_dialogue_raw(sentence: bytes, gamecode: bytes) -> tuple[str, str, str]:
    """Return (source_field, raw_encoding, control_tail)."""
    sent = raw_to_str(sentence)
    gc = raw_to_str(gamecode)

    if is_dialogue_payload(gc):
        control = sent if sent not in SKIP_TEXTS and not is_dialogue_payload(sent) else ""
        return "gamecode", gc, control
    if is_dialogue_payload(sent):
        return "sentence", sent, gc if gc not in SKIP_TEXTS else ""
    if gc:
        return "gamecode", gc, sent
    return "sentence", sent, ""


def decode_speaker(raw: bytes, rosetta: list[str]) -> str:
    text = raw_to_str(raw)
    return decode_index_string(text, rosetta)


def decode_speaker_cn(raw: bytes, rosetta: list[str], cn_map: dict[int, str]) -> str:
    text = raw_to_str(raw).strip()
    if not text:
        return ""

    def char_at(index: int) -> str:
        if index in cn_map:
            return cn_map[index]
        if 0 <= index < len(rosetta) and rosetta[index]:
            return rosetta[index]
        return f"{{#{index}}}"

    if "{" in text:
        return decode_with_rosetta(text, rosetta)

    indices = extract_indices(text)
    if indices and re.fullmatch(r"[\d|]+", text):
        return "".join(char_at(index) for index in indices)
    return decode_with_rosetta(text, rosetta)


def known_cn_chars(indices: list[int], cn_map: dict[int, str]) -> str:
    chars = []
    for index in indices:
        if index in cn_map:
            chars.append(cn_map[index])
        else:
            chars.append("?")
    return "".join(chars)


def build_rows(
    en_data,
    cn_data,
    rosetta: list[str],
    cn_map: dict[int, str],
    cn_diff_only: bool,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    total = row_count(en_data)

    for i in range(total):
        speaker_en = en_data.speakers[i] if i < len(en_data.speakers) else b""
        speaker_cn = cn_data.speakers[i] if i < len(cn_data.speakers) else b""
        sent_en = en_data.sentences[i] if i < len(en_data.sentences) else b""
        sent_cn = cn_data.sentences[i] if i < len(cn_data.sentences) else b""
        gc_en = en_data.gamecodes[i] if i < len(en_data.gamecodes) else b""
        gc_cn = cn_data.gamecodes[i] if i < len(cn_data.gamecodes) else b""

        en_src, en_raw, en_ctrl = pick_dialogue_raw(sent_en, gc_en)
        cn_src, cn_raw, cn_ctrl = pick_dialogue_raw(sent_cn, gc_cn)

        en_indices = extract_indices(en_raw)
        cn_indices = extract_indices(cn_raw)

        if cn_diff_only and cn_raw == en_raw:
            continue

        en_text = decode_with_rosetta(en_raw, rosetta)
        cn_braces = indices_to_braces(cn_indices)

        rows.append(
            {
                "line": str(i + 1),
                "speaker_en": decode_speaker(speaker_en, rosetta),
                "speaker_cn": decode_speaker_cn(speaker_cn, rosetta, cn_map),
                "speaker_cn_indices": raw_to_str(speaker_cn),
                "en_text": en_text,
                "en_encoding": en_raw,
                "en_indices": " ".join(map(str, en_indices)),
                "en_field": en_src,
                "cn_encoding": cn_raw,
                "cn_indices": " ".join(map(str, cn_indices)),
                "cn_braces": cn_braces,
                "cn_known": known_cn_chars(cn_indices, cn_map) if cn_indices else "",
                "cn_field": cn_src,
                "control_en": en_ctrl,
                "control_cn": cn_ctrl,
            }
        )

    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_html(path: Path, rows: list[dict[str, str]]) -> None:
    head = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<title>Iconoclasts 台词对照</title>
<style>
body { font-family: "Segoe UI", sans-serif; margin: 16px; background: #111; color: #eee; }
input { width: 100%; padding: 10px; margin-bottom: 12px; background: #222; color: #eee; border: 1px solid #444; }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th, td { border: 1px solid #333; padding: 6px 8px; vertical-align: top; }
th { background: #1b1b1b; position: sticky; top: 0; }
tr:nth-child(even) { background: #161616; }
.en { color: #9fd; }
.cn { color: #fd9; }
.idx { color: #adf; font-family: Consolas, monospace; }
.note { color: #888; font-size: 12px; margin-bottom: 12px; }
</style>
</head>
<body>
<h1>Iconoclasts 台词对照</h1>
<p class="note">用法：在游戏中找到英文台词，在本表搜索 <span class="en">en_text</span>，查看同行的 <span class="cn">cn_indices</span> / <span class="idx">cn_braces</span>，对照游戏画面填写汉字。</p>
<input id="q" placeholder="搜索英文、编码、索引、说话人…" />
<table>
<thead><tr>
<th>#</th><th>说话人(英)</th><th>说话人(中)</th><th>英文原文</th><th>英文编码</th>
<th>中文编码</th><th>中文索引</th><th>cn_braces</th><th>已知汉字</th>
</tr></thead>
<tbody>
"""
    body_parts = []
    for row in rows:
        body_parts.append(
            "<tr>"
            f"<td>{html.escape(row['line'])}</td>"
            f"<td>{html.escape(row['speaker_en'])}</td>"
            f"<td class='cn'>{html.escape(row['speaker_cn'])}</td>"
            f"<td class='en'>{html.escape(row['en_text'])}</td>"
            f"<td class='idx'>{html.escape(row['en_encoding'])}</td>"
            f"<td class='idx'>{html.escape(row['cn_encoding'])}</td>"
            f"<td class='idx'>{html.escape(row['cn_indices'])}</td>"
            f"<td class='idx'>{html.escape(row['cn_braces'])}</td>"
            f"<td class='cn'>{html.escape(row['cn_known'])}</td>"
            "</tr>"
        )
    tail = """</tbody></table>
<script>
const q = document.getElementById('q');
q.addEventListener('input', () => {
  const v = q.value.toLowerCase();
  for (const tr of document.querySelectorAll('tbody tr')) {
    tr.style.display = tr.innerText.toLowerCase().includes(v) ? '' : 'none';
  }
});
</script>
</body></html>
"""
    path.write_text(head + "\n".join(body_parts) + tail, encoding="utf-8")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")

    tool_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="Build EN/CN dialogue cross-reference table")
    parser.add_argument("--game-dir", type=Path, default=tool_dir.parent)
    parser.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument(
        "--cn-diff-only",
        action="store_true",
        help="Only include lines where CN encoding differs from EN",
    )
    args = parser.parse_args()

    en_path = args.game_dir / "data" / "dia"
    cn_path = args.game_dir / "data" / "diachn"
    rosetta_path = tool_dir / "Rosetta.txt"
    rosetta_cn_path = tool_dir / "Rosetta_CN.txt"

    for path in (en_path, cn_path, rosetta_path):
        if not path.exists():
            print(f"Error: missing {path}")
            return 1

    rosetta = load_rosetta(rosetta_path)
    cn_map = load_rosetta_cn(rosetta_cn_path)
    en_data = parse_dia_file(en_path)
    cn_data = parse_dia_file(cn_path)

    rows = build_rows(en_data, cn_data, rosetta, cn_map, args.cn_diff_only)

    csv_path = args.out_dir / "dialogue_crossref.csv"
    html_path = args.out_dir / "dialogue_crossref.html"
    json_path = args.out_dir / "dialogue_crossref.json"

    write_csv(csv_path, rows)
    write_html(html_path, rows)
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    cn_diff = sum(1 for r in rows if r["cn_encoding"] != r["en_encoding"])
    print(f"Wrote {len(rows)} rows ({cn_diff} with different CN encoding)")
    print(f"  CSV:  {csv_path}")
    print(f"  HTML: {html_path}")
    print(f"  JSON: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
