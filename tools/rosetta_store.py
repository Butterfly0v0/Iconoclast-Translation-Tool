"""Load/save Rosetta_CN.txt and apply index mappings."""

from __future__ import annotations

import json
import re
from pathlib import Path

INDEX_RE = re.compile(r"\{#(\d+)\}")
PUA_BASE = 0xE000
BASE_COUNT = 156


def load_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return [line for line in text.split("\n") if line != ""]


def write_lines(path: Path, lines: list[str]) -> None:
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


def is_placeholder(char: str) -> bool:
    return len(char) == 1 and PUA_BASE <= ord(char) <= 0xF8FF


def infer_max_index(tool_dir: Path) -> int:
    for candidate in (
        tool_dir / "indices_used.txt",
        tool_dir / "tools" / "dialogue_crossref.json",
    ):
        if not candidate.exists():
            continue
        if candidate.suffix == ".txt":
            values = [int(line) for line in candidate.read_text(encoding="utf-8").splitlines() if line.strip().isdigit()]
            if values:
                return max(values)
        else:
            rows = json.loads(candidate.read_text(encoding="utf-8"))
            max_idx = 0
            for row in rows:
                for key in ("cn_indices", "en_indices"):
                    for part in row.get(key, "").split():
                        if part.isdigit():
                            max_idx = max(max_idx, int(part))
            if max_idx:
                return max_idx
    return 3454


def load_table(tool_dir: Path) -> tuple[list[str], int]:
    base_path = tool_dir / "Rosetta.txt"
    cn_path = tool_dir / "Rosetta_CN.txt"
    base = load_lines(base_path)
    if not base:
        raise FileNotFoundError(f"Missing {base_path}")

    max_index = infer_max_index(tool_dir)
    if cn_path.exists():
        lines = load_lines(cn_path)
    else:
        lines = base[:]

    while len(lines) <= max_index:
        lines.append("")

    for index in range(min(len(base), len(lines))):
        if base[index]:
            lines[index] = base[index]

    for index in range(BASE_COUNT, len(lines)):
        if not lines[index]:
            lines[index] = chr(PUA_BASE + (index - BASE_COUNT))

    return lines, max_index


def table_stats(lines: list[str], max_index: int) -> dict[str, int]:
    filled = 0
    pua = 0
    for index in range(BASE_COUNT, min(len(lines), max_index + 1)):
        char = lines[index] if index < len(lines) else ""
        if not char:
            continue
        if is_placeholder(char):
            pua += 1
        else:
            filled += 1
    return {"base": BASE_COUNT, "filled_cjk": filled, "placeholder_cjk": pua, "max_index": max_index}


def save_table(tool_dir: Path, lines: list[str]) -> list[str]:
    targets = [
        tool_dir / "Rosetta_CN.txt",
        tool_dir / "bin" / "Release" / "net7.0" / "Rosetta_CN.txt",
    ]
    written: list[str] = []
    for path in targets:
        if path.parent.exists():
            write_lines(path, lines)
            written.append(str(path))
    return written


def braces_to_index_text(text: str) -> str:
    if "{#" not in text and "|" in text:
        return text
    return INDEX_RE.sub(lambda match: str(match.group(1)), text.replace("{#", "").replace("}", "|"))


def parse_index_tokens(text: str) -> list[tuple[str, int | None]]:
    tokens: list[tuple[str, int | None]] = []
    pos = 0
    normalized = text
    if "{#" in text:
        normalized = INDEX_RE.sub(lambda m: f"|{m.group(1)}|", text)
    for match in re.finditer(r"\|(\d+)\|?", normalized):
        if match.start() > pos:
            tokens.append((normalized[pos : match.start()], None))
        tokens.append(("", int(match.group(1))))
        pos = match.end()
    if pos < len(normalized):
        tokens.append((normalized[pos:], None))
    return tokens


def align_text_to_indices(index_text: str, chinese: str) -> dict[int, str]:
    tokens = parse_index_tokens(index_text)
    literal_parts = [lit for lit, idx in tokens if idx is None and lit]
    mapping: dict[int, str] = {}

    if not literal_parts and not any(lit for lit, _ in tokens if lit):
        indices = [idx for _, idx in tokens if idx is not None]
        if len(indices) != len(chinese):
            raise ValueError(f"索引数 {len(indices)} 与汉字数 {len(chinese)} 不一致")
        for idx, ch in zip(indices, chinese):
            mapping[idx] = ch
        return mapping

    remaining = chinese
    for lit, idx in tokens:
        if idx is None:
            lit_clean = lit.replace("|", "")
            if not lit_clean:
                continue
            if not remaining.startswith(lit_clean):
                raise ValueError(f"字面量 {lit_clean!r} 与剩余文本 {remaining!r} 不匹配")
            remaining = remaining[len(lit_clean) :]
        else:
            if not remaining:
                raise ValueError(f"索引 {idx} 缺少对应汉字")
            mapping[idx] = remaining[0]
            remaining = remaining[1:]

    if remaining:
        raise ValueError(f"多余汉字: {remaining!r}")
    return mapping


def apply_mapping(
    lines: list[str],
    mapping: dict[int, str],
    force: bool = True,
) -> tuple[list[str], list[dict]]:
    updated = lines[:]
    changes: list[dict] = []

    max_index = max(mapping)
    while len(updated) <= max_index:
        updated.append("")

    for index, char in sorted(mapping.items()):
        if len(char) != 1:
            raise ValueError(f"索引 {index} 只能是一个字")
        old = updated[index] if index < len(updated) else ""
        if old and old != char and not force and not is_placeholder(old):
            changes.append({"index": index, "skipped": True, "old": old, "new": char})
            continue
        if old != char:
            updated[index] = char
            changes.append({"index": index, "skipped": False, "old": old, "new": char})
    return updated, changes
