"""Detect Rosetta glyph index conflicts against the current character table."""

from __future__ import annotations

from typing import Any

from rosetta_store import is_placeholder


def is_real_char(char: str) -> bool:
    """True when index already holds a non-PUA, non-empty character."""
    return len(char) == 1 and not is_placeholder(char)


def format_proposed(char: str) -> str:
    if not char:
        return ""
    if is_placeholder(char):
        return ""
    return char


def conflict_message(index: int, existing: str, proposed: str) -> str:
    return f'#{index}已对应文字"{existing}"，是否强制替换为"{proposed}"'


def check_lines_against_table(
    current_lines: list[str],
    proposed_lines: list[str],
    *,
    indices: list[int] | None = None,
) -> list[dict[str, Any]]:
    """Return conflicts where proposed would overwrite an existing real character."""
    conflicts: list[dict[str, Any]] = []
    if indices is None:
        upper = max(len(current_lines), len(proposed_lines))
        indices = list(range(upper))
    for index in indices:
        existing = current_lines[index] if index < len(current_lines) else ""
        proposed = proposed_lines[index] if index < len(proposed_lines) else ""
        if proposed == existing:
            continue
        if not is_real_char(existing):
            continue
        conflicts.append(
            {
                "index": index,
                "existing": existing,
                "proposed": format_proposed(proposed),
            }
        )
    return conflicts


def check_mapping_against_table(
    current_lines: list[str],
    mapping: dict[int, str],
) -> list[dict[str, Any]]:
    """Return conflicts for a proposed index→char mapping."""
    conflicts: list[dict[str, Any]] = []
    for index, proposed in mapping.items():
        existing = current_lines[index] if index < len(current_lines) else ""
        if proposed == existing:
            continue
        if not is_real_char(existing):
            continue
        conflicts.append(
            {
                "index": index,
                "existing": existing,
                "proposed": proposed,
            }
        )
    return conflicts


def conflict_error(conflicts: list[dict[str, Any]]) -> dict[str, Any]:
    lines = [
        conflict_message(c["index"], c["existing"], c["proposed"])
        for c in conflicts
    ]
    return {
        "error": "glyph_index_conflict",
        "message": "\n".join(lines),
        "conflicts": conflicts,
    }
