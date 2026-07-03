"""Write Iconoclasts dia / diachn binary dialogue files."""

from __future__ import annotations

import io
import shutil
import struct
from datetime import datetime
from pathlib import Path

from dia_parser import DiaData


def read_header_count(path: Path) -> int:
    data = path.read_bytes()
    if len(data) < 10:
        raise ValueError(f"File too small: {path}")
    return struct.unpack("<I", data[6:10])[0]


def write_dia_file(path: Path, data: DiaData, row_count: int | None = None) -> None:
    """Write dia binary matching Iconoclast.Dia.BuildDia layout."""
    if row_count is None:
        row_count = len(data.sentences)
    buffer = io.BytesIO()

    buffer.write(struct.pack("<I", 0x31525241))
    buffer.write(struct.pack("<h", 0x302E))
    buffer.write(struct.pack("<I", row_count))

    for i in range(row_count):
        speaker = data.speakers[i] if i < len(data.speakers) else b""
        sentence = data.sentences[i] if i < len(data.sentences) else b""
        gamecode = data.gamecodes[i] if i < len(data.gamecodes) else b""

        _write_speaker_block(buffer, speaker)
        _write_text_block(buffer, sentence)
        _write_text_block(buffer, gamecode)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(buffer.getvalue())


def _write_speaker_block(buffer: io.BytesIO, payload: bytes) -> None:
    buffer.write(struct.pack("<I", 3))
    buffer.write(struct.pack("<I", 1))
    buffer.write(struct.pack("<I", 2))
    buffer.write(struct.pack("<I", len(payload) + 1))
    buffer.write(payload)
    buffer.write(b"\x00")


def _write_text_block(buffer: io.BytesIO, payload: bytes) -> None:
    buffer.write(struct.pack("<I", 1))
    buffer.write(struct.pack("<I", 2))
    buffer.write(struct.pack("<I", len(payload) + 1))
    buffer.write(payload)
    buffer.write(b"\x00")


def backup_file(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_suffix(path.suffix + f".bak_{stamp}")
    shutil.copy2(path, backup)
    return backup
