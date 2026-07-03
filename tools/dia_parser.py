"""Parse Iconoclasts dia / diachn binary dialogue files."""

from __future__ import annotations

import io
import struct
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DiaData:
    speakers: list[bytes]
    sentences: list[bytes]
    gamecodes: list[bytes]


def parse_dia_file(path: Path) -> DiaData:
    data = path.read_bytes()
    stream = io.BytesIO(data)
    stream.seek(6)
    stream.read(4)  # sentence count header

    speakers: list[bytes] = []
    sentences: list[bytes] = []
    gamecodes: list[bytes] = []

    while stream.tell() < len(data):
        block_type = struct.unpack("<I", stream.read(4))[0]
        if block_type == 1:
            stream.read(4)
            length = struct.unpack("<I", stream.read(4))[0]
            payload = stream.read(length - 1)
            stream.read(1)
            if len(sentences) == len(gamecodes):
                sentences.append(payload)
            else:
                gamecodes.append(payload)
        elif block_type == 3:
            stream.read(8)
            length = struct.unpack("<I", stream.read(4))[0]
            speakers.append(stream.read(length - 1))
            stream.read(1)
        else:
            break

    return DiaData(speakers=speakers, sentences=sentences, gamecodes=gamecodes)


def row_count(data: DiaData) -> int:
    return max(len(data.speakers), len(data.sentences), len(data.gamecodes))
