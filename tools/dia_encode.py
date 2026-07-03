"""Encode/decode Iconoclasts dialogue text (matches Iconoclast.Dia.StringEncoder)."""

from __future__ import annotations

import re

INDEX_PLACEHOLDER_RE = re.compile(r"\{#(\d+)\}")


def build_char_lookup(lines: list[str]) -> dict[str, int]:
    """Last (highest) index wins for duplicate characters — same as Rosetta.cs."""
    lookup: dict[str, int] = {}
    for index in range(len(lines) - 1, -1, -1):
        char = lines[index]
        if char:
            lookup[char] = index
    return lookup


def encode_to_pipe(text: str, lines: list[str]) -> str:
    """Encode display text (with {tags}) to pipe-index form for dia gamecode."""
    lookup = build_char_lookup(lines)
    sentence = text.replace("\n", "{new}")
    encoded: list[str] = []
    is_code = False
    i = 0

    while i < len(sentence):
        if sentence[i] == "{" and i + 2 < len(sentence) and sentence[i + 1] == "#":
            match = INDEX_PLACEHOLDER_RE.match(sentence, i)
            if match:
                if is_code:
                    encoded.append(match.group(0))
                else:
                    encoded.append(match.group(1) + "|")
                i = match.end()
                continue

        char = sentence[i]

        if char == "{":
            is_code = True
        elif char == "}":
            encoded.append("}|")
            is_code = False
            i += 1
            continue

        if is_code:
            if encoded and encoded[-1] == "一" and char == "{":
                encoded.append("|")
            encoded.append(char)
        else:
            if char not in lookup:
                raise ValueError(
                    f"字符 {char!r} (U+{ord(char):04X}) 不在 Rosetta_CN.txt 中。"
                    "请先在字符表编辑器中补全，或使用 {{#索引}} 占位符。"
                )
            encoded.append(str(lookup[char]) + "|")

        i += 1

    result = "".join(encoded)
    if result.endswith("|"):
        result = result[:-1]
    return result.replace("\\\\", "\\").replace("一", "\\")


def validate_text(text: str, lines: list[str]) -> dict:
    """Return missing characters and whether {#index} placeholders are used."""
    lookup = build_char_lookup(lines)
    missing: list[dict[str, str]] = []
    seen: set[str] = set()
    is_code = False
    i = 0

    while i < len(text):
        if text[i] == "{" and i + 2 < len(text) and text[i + 1] == "#":
            match = INDEX_PLACEHOLDER_RE.match(text, i)
            if match:
                i = match.end()
                continue

        char = text[i]
        if char == "{":
            is_code = True
        elif char == "}":
            is_code = False
            i += 1
            continue

        if not is_code and char != "\n" and char not in lookup and char not in seen:
            seen.add(char)
            missing.append({"char": char, "codepoint": f"U+{ord(char):04X}"})

        i += 1

    return {"ok": not missing, "missing": missing}


def find_empty_slots(lines: list[str], base_count: int = 156) -> list[int]:
    """Indices still using PUA placeholders or blank — candidates for new glyphs."""
    from rosetta_store import is_placeholder

    slots: list[int] = []
    for index in range(base_count, len(lines)):
        char = lines[index] if index < len(lines) else ""
        if not char or is_placeholder(char):
            slots.append(index)
    return slots


def assign_char(lines: list[str], char: str, index: int | None = None) -> tuple[list[str], int]:
    """Assign a character to an index (existing or first empty slot)."""
    if len(char) != 1:
        raise ValueError("只能分配单个字符")

    updated = lines[:]
    if index is None:
        empty = find_empty_slots(updated)
        if not empty:
            raise ValueError("字符表已无空位（最大约 3537 个索引）")
        index = empty[0]

    while len(updated) <= index:
        updated.append("")

    updated[index] = char
    return updated, index
