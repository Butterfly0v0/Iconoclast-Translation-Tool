"""Read Iconoclasts Assets.dat (Chowdren archive v1) and extract font glyphs."""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

try:
    from PIL import Image
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Install Pillow: pip install Pillow") from exc


@dataclass(frozen=True)
class AssetOffsets:
    images: int
    images_end: int
    sounds: int
    type_sizes: int


@dataclass(frozen=True)
class ImageEntry:
    index: int
    offset: int
    width: int
    height: int
    compressed_size: int
    data_offset: int


def read_u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def read_u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def find_type_sizes(data: bytes) -> int:
    file_size = len(data)
    for i in range(file_size):
        if read_u32(data, i) >= file_size:
            continue
        first_entry = read_u32(data, i)
        j = i + 4
        while j < first_entry:
            entry = read_u32(data, j)
            if entry >= file_size or entry < first_entry:
                distance = first_entry - j
                if distance <= 24:
                    return first_entry - 24
                break
            j += 4
    raise RuntimeError("Could not locate type_sizes in Assets.dat")


def find_asset_offsets(data: bytes) -> AssetOffsets:
    type_sizes = find_type_sizes(data)
    size_images = read_u32(data, type_sizes)
    size_sounds = read_u32(data, type_sizes + 4)
    size_fonts = read_u32(data, type_sizes + 8)
    size_shaders = read_u32(data, type_sizes + 12)

    file_size = len(data)
    data_shaders = file_size - read_u32(data, type_sizes + 20) if read_u32(data, type_sizes + 20) else file_size - size_shaders
    # Iconoclasts: platform/files sizes are 0; shaders at end of header region
    data_platform = file_size
    data_files = file_size - read_u32(data, type_sizes + 16)
    data_shaders = data_files - size_shaders
    data_fonts = data_shaders - size_fonts
    data_sounds = data_fonts - size_sounds
    data_images = data_sounds - size_images

    alignment = type_sizes % 4
    max_search = type_sizes

    def find_u32(value: int) -> int:
        start = alignment % 4
        for off in range(start, max_search, 4):
            if read_u32(data, off) == value:
                return off
        raise RuntimeError(f"Could not find offset marker 0x{value:x}")

    images = find_u32(data_images)
    sounds = find_u32(data_sounds)

    all_offsets = [images, sounds, find_u32(data_fonts), find_u32(data_shaders)]
    images_end = next(v for v in all_offsets[1:] if v != all_offsets[0])

    return AssetOffsets(
        images=images,
        images_end=images_end,
        sounds=sounds,
        type_sizes=type_sizes,
    )


def parse_image_entry_v2(data: bytes, entry_offset: int) -> tuple[int, int, int, int]:
    offset = entry_offset
    width = read_u16(data, offset)
    height = read_u16(data, offset + 2)
    offset += 4 + 4
    extra_count = data[offset]
    offset += 1 + extra_count * 4
    compressed_size = read_u32(data, offset)
    data_offset = offset + 4
    return width, height, compressed_size, data_offset


def list_image_entries(data: bytes, offsets: AssetOffsets | None = None) -> list[ImageEntry]:
    if offsets is None:
        offsets = find_asset_offsets(data)

    entries: list[ImageEntry] = []
    index = 0
    for table_off in range(offsets.images, offsets.images_end, 4):
        entry_offset = read_u32(data, table_off)
        width, height, compressed_size, data_offset = parse_image_entry_v2(data, entry_offset)
        entries.append(
            ImageEntry(
                index=index,
                offset=entry_offset,
                width=width,
                height=height,
                compressed_size=compressed_size,
                data_offset=data_offset,
            )
        )
        index += 1
    return entries


def decompress_rgba(data: bytes, entry: ImageEntry) -> bytes:
    compressed = data[entry.data_offset : entry.data_offset + entry.compressed_size]
    raw = zlib.decompress(compressed)
    expected = entry.width * entry.height * 4
    if len(raw) < expected:
        raise ValueError(
            f"Image #{entry.index} decompressed to {len(raw)} bytes, expected {expected}"
        )
    return raw[:expected]


def extract_image(data: bytes, entry: ImageEntry) -> Image.Image:
    rgba = decompress_rgba(data, entry)
    return Image.frombytes("RGBA", (entry.width, entry.height), rgba)


def build_rosetta_glyph_map(entries: list[ImageEntry], size: tuple[int, int] = (22, 22)) -> list[int]:
    """List asset ids for each 22x22 glyph in archive scan order (ordinal -> asset).

    NOTE: Rosetta slot N is NOT archive ordinal N. For editor previews use
    tools/glyphs/NNNNN.png where NNNNN is the Rosetta index.
    """
    glyph_assets = [e.index for e in entries if (e.width, e.height) == size]
    if not glyph_assets:
        raise RuntimeError(f"No {size[0]}x{size[1]} images found")
    return glyph_assets


def load_assets(path: Path) -> tuple[bytes, list[ImageEntry], list[int]]:
    data = path.read_bytes()
    entries = list_image_entries(data)
    glyph_map = build_rosetta_glyph_map(entries)
    return data, entries, glyph_map


def extract_glyph_by_asset(data: bytes, entries: list[ImageEntry], asset_index: int) -> Image.Image:
    return extract_image(data, entries[asset_index])


def extract_glyph_by_rosetta(
    data: bytes,
    entries: list[ImageEntry],
    glyph_map: list[int],
    rosetta_index: int,
) -> Image.Image:
    if rosetta_index < 0 or rosetta_index >= len(glyph_map):
        raise IndexError(f"Rosetta index {rosetta_index} out of range (0-{len(glyph_map) - 1})")
    asset_index = glyph_map[rosetta_index]
    return extract_image(data, entries[asset_index])
