"""Map Rosetta index -> Assets.dat glyph image for {font02}.

The game does NOT use the Nth 22x22 archive image as Rosetta slot N.
We derive rosetta_index -> glyph_ordinal -> asset id from OCR + Rosetta_CN.
"""

from __future__ import annotations

import json
from pathlib import Path

from chowdren_assets import extract_glyph_by_asset, extract_glyph_by_rosetta, load_assets

PUA_BASE = 0xE000
GLYPH_COUNT = 3537

# Validated anchors: Rosetta index -> ordinal among 22x22 images
LATIN_ANCHORS: dict[int, int] = {
    41: 338,  # H
    45: 336,  # L
    49: 329,  # P
    51: 2625,  # R
    56: 2277,  # W
}


def load_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return [line for line in text.split("\n") if line != ""]


def load_ocr_char_map(meta_path: Path) -> dict[int, str]:
    if not meta_path.exists():
        return {}
    payload = json.loads(meta_path.read_text(encoding="utf-8"))
    entries = payload.get("entries", payload)
    result: dict[int, str] = {}
    for key, info in entries.items():
        if not isinstance(info, dict):
            continue
        if info.get("source") != "ocr":
            continue
        char = info.get("char", "")
        if not char or len(char) != 1 or ord(char) >= PUA_BASE:
            continue
        result[int(key)] = char
    return result


def _ocr_glyph(engine, image, scale: int = 6) -> tuple[str | None, float]:
    from PIL import Image, ImageOps

    image = image.convert("RGBA")
    image = image.resize((image.width * scale, image.height * scale), Image.NEAREST)
    background = Image.new("RGBA", image.size, (255, 255, 255, 255))
    background.paste(image, mask=image.split()[3])
    gray = ImageOps.grayscale(background)
    result = engine(gray)
    if not result or not result[0]:
        return None, 0.0
    text, confidence = result[0][0][1], float(result[0][0][2])
    text = text.strip()
    if not text:
        return None, confidence
    return text[0], confidence


def save_ocr_cache(cache_path: Path, ocr_by_ordinal: dict[int, str]) -> None:
    cache_path.write_text(
        json.dumps({"chars": {str(k): v for k, v in sorted(ocr_by_ordinal.items())}}, ensure_ascii=False),
        encoding="utf-8",
    )


def load_ocr_cache(cache_path: Path) -> dict[int, str]:
    if not cache_path.exists():
        return {}
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    return {int(k): v for k, v in payload.get("chars", {}).items()}


def missing_expected_chars(
    base: list[str],
    cn: list[str],
    ocr_by_ordinal: dict[int, str],
) -> set[str]:
    known = set(ocr_by_ordinal.values())
    missing: set[str] = set()
    for index in range(GLYPH_COUNT):
        char = expected_char(index, base, cn)
        if char and char not in known:
            missing.add(char)
    return missing


def build_ordinal_ocr_index(
    glyph_ordinals: list[int],
    data: bytes,
    entries,
    existing: dict[int, str],
    *,
    progress: bool = True,
    min_confidence: float = 0.35,
    only_chars: set[str] | None = None,
    cache_path: Path | None = None,
) -> dict[int, str]:
    """OCR glyph slots -> {ordinal: char}. One full pass; optional early stop when only_chars found."""
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        return dict(existing)

    engine = RapidOCR()
    result = dict(existing)
    todo = [o for o in range(len(glyph_ordinals)) if o not in result]
    if progress and todo:
        print(f"OCR {len(todo)} glyph slots...", flush=True)
    found_targets = set()
    for n, ordinal in enumerate(todo):
        try:
            image = extract_glyph_by_rosetta(data, entries, glyph_ordinals, ordinal)
        except (IndexError, ValueError):
            continue
        guess, conf = _ocr_glyph(engine, image)
        if guess and conf >= min_confidence:
            result[ordinal] = guess
            if only_chars and guess in only_chars:
                found_targets.add(guess)
        if cache_path and n and n % 100 == 0:
            save_ocr_cache(cache_path, result)
        if only_chars and found_targets >= only_chars:
            if progress:
                print(f"  found all {len(only_chars)} target chars after {n + 1} slots", flush=True)
            break
        if progress and n and n % 200 == 0:
            print(f"  OCR {n}/{len(todo)}", flush=True)
    if cache_path:
        save_ocr_cache(cache_path, result)
    return result


def expected_char(index: int, base: list[str], cn: list[str]) -> str:
    if index < len(cn) and cn[index] and len(cn[index]) == 1 and ord(cn[index]) < PUA_BASE:
        return cn[index]
    if index < len(base) and base[index] and len(base[index]) == 1 and ord(base[index]) < PUA_BASE:
        return base[index]
    return ""


def build_rosetta_to_ordinal(
    tool_dir: Path,
    *,
    use_live_ocr: bool = True,
    progress: bool = True,
) -> dict[int, int]:
    """Return rosetta_index -> glyph_ordinal among 22x22 images."""
    ocr_meta_path = tool_dir / "tools" / "rosetta_ocr_meta.json"
    ocr_cache_path = tool_dir / "tools" / "glyph_ocr_by_ordinal.json"
    base = load_lines(tool_dir / "Rosetta.txt")
    cn = load_lines(tool_dir / "Rosetta_CN.txt")
    while len(cn) < GLYPH_COUNT:
        cn.append("")

    ocr_by_ordinal = load_ocr_char_map(ocr_meta_path)
    ocr_by_ordinal.update(load_ocr_cache(ocr_cache_path))

    if use_live_ocr:
        assets_path = tool_dir.parent / "Assets.dat"
        data, entries, glyph_ordinals = load_assets(assets_path)
        missing = missing_expected_chars(base, cn, ocr_by_ordinal)
        if progress and missing:
            print(f"Missing OCR for {len(missing)} expected chars", flush=True)
        before = len(ocr_by_ordinal)
        ocr_by_ordinal = build_ordinal_ocr_index(
            glyph_ordinals,
            data,
            entries,
            ocr_by_ordinal,
            progress=progress,
            only_chars=missing if missing and len(missing) <= 12 else None,
            cache_path=ocr_cache_path,
        )
        if len(ocr_by_ordinal) > before:
            save_ocr_cache(ocr_cache_path, ocr_by_ordinal)

    char_to_ordinals: dict[str, list[int]] = {}
    for ordinal, char in ocr_by_ordinal.items():
        char_to_ordinals.setdefault(char, []).append(ordinal)

    rosetta_to_ordinal: dict[int, int] = dict(LATIN_ANCHORS)
    ordinal_to_char: dict[int, str] = {
        ordinal: ocr_by_ordinal[ordinal] for ordinal in LATIN_ANCHORS.values() if ordinal in ocr_by_ordinal
    }

    def assign(index: int, ordinal: int) -> None:
        char = expected_char(index, base, cn)
        if char and ordinal in ordinal_to_char and ordinal_to_char[ordinal] != char:
            return
        if ordinal in ordinal_to_char:
            existing_char = ordinal_to_char[ordinal]
            if char and existing_char != char:
                return
        rosetta_to_ordinal[index] = ordinal
        if char:
            ordinal_to_char[ordinal] = char
        elif ordinal in ocr_by_ordinal:
            ordinal_to_char.setdefault(ordinal, ocr_by_ordinal[ordinal])

    # Unique char with unique rosetta slot and unique ordinal
    for char, ordinals in char_to_ordinals.items():
        rosetta_hits = [
            i
            for i in range(GLYPH_COUNT)
            if expected_char(i, base, cn) == char and i not in rosetta_to_ordinal
        ]
        if len(rosetta_hits) == 1 and len(ordinals) == 1:
            assign(rosetta_hits[0], ordinals[0])

    # Any rosetta slot with known char -> pick best ordinal (same char may share one glyph)
    for index in range(GLYPH_COUNT):
        if index in rosetta_to_ordinal:
            continue
        char = expected_char(index, base, cn)
        if len(char) != 1:
            continue
        ordinals = char_to_ordinals.get(char, [])
        if not ordinals:
            continue
        for ordinal in ordinals:
            conflict = any(
                expected_char(r, base, cn) != char and o == ordinal
                for r, o in rosetta_to_ordinal.items()
            )
            if not conflict:
                assign(index, ordinal)
                break

    return rosetta_to_ordinal, ocr_by_ordinal


def pick_ordinal(
    rosetta_index: int,
    rosetta_to_ordinal: dict[int, int],
    ocr_by_ordinal: dict[int, str],
    base: list[str],
    cn: list[str],
) -> int:
    if rosetta_index in rosetta_to_ordinal:
        return rosetta_to_ordinal[rosetta_index]

    exp = expected_char(rosetta_index, base, cn)
    if exp:
        matches = [o for o, ch in ocr_by_ordinal.items() if ch == exp]
        if matches:
            for ordinal in matches:
                conflict = any(
                    expected_char(r, base, cn) != exp and rosetta_to_ordinal.get(r) == ordinal
                    for r in rosetta_to_ordinal
                )
                if not conflict:
                    return ordinal
            return matches[0]

    identity_ocr = ocr_by_ordinal.get(rosetta_index)
    if exp:
        if identity_ocr and identity_ocr != exp:
            matches = [o for o, ch in ocr_by_ordinal.items() if ch == exp]
            if matches:
                return matches[0]
            return rosetta_index
        if not identity_ocr:
            matches = [o for o, ch in ocr_by_ordinal.items() if ch == exp]
            if matches:
                return matches[0]
    return rosetta_index


def build_rosetta_asset_map(
    glyph_ordinals: list[int],
    rosetta_to_ordinal: dict[int, int],
    ocr_by_ordinal: dict[int, str] | None = None,
    base: list[str] | None = None,
    cn: list[str] | None = None,
) -> list[int]:
    ocr_by_ordinal = ocr_by_ordinal or {}
    base = base or []
    cn = cn or []
    asset_map: list[int] = []
    for rosetta_index in range(len(glyph_ordinals)):
        ordinal = pick_ordinal(rosetta_index, rosetta_to_ordinal, ocr_by_ordinal, base, cn)
        if ordinal < 0 or ordinal >= len(glyph_ordinals):
            ordinal = rosetta_index
        asset_map.append(glyph_ordinals[ordinal])
    return asset_map


def save_mapping_cache(
    cache_path: Path,
    rosetta_to_ordinal: dict[int, int],
    asset_map: list[int],
    glyph_ordinals: list[int],
) -> None:
    payload = {
        "version": 2,
        "glyph_count": len(glyph_ordinals),
        "rosetta_to_ordinal": {str(k): v for k, v in sorted(rosetta_to_ordinal.items())},
        "rosetta_to_asset": {str(i): asset_map[i] for i in range(len(asset_map))},
        "glyph_ordinals": glyph_ordinals,
    }
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_mapping_cache(cache_path: Path) -> tuple[dict[int, int], list[int], list[int]] | None:
    if not cache_path.exists():
        return None
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    if payload.get("version") != 2:
        return None
    rosetta_to_ordinal = {int(k): int(v) for k, v in payload.get("rosetta_to_ordinal", {}).items()}
    glyph_ordinals = [int(x) for x in payload.get("glyph_ordinals", [])]
    asset_map = [
        int(payload["rosetta_to_asset"][str(i)])
        for i in range(payload.get("glyph_count", len(glyph_ordinals)))
    ]
    return rosetta_to_ordinal, asset_map, glyph_ordinals


def get_rosetta_asset_map(tool_dir: Path, *, rebuild: bool = False) -> list[int]:
    cache_path = tool_dir / "tools" / "glyphs" / "font_mapping.json"
    if not rebuild:
        cached = load_mapping_cache(cache_path)
        if cached is not None:
            _, asset_map, _ = cached
            return asset_map

    assets_path = tool_dir.parent / "Assets.dat"
    data, entries, glyph_ordinals = load_assets(assets_path)
    base = load_lines(tool_dir / "Rosetta.txt")
    cn = load_lines(tool_dir / "Rosetta_CN.txt")
    rosetta_to_ordinal, ocr_by_ordinal = build_rosetta_to_ordinal(tool_dir, use_live_ocr=True)
    asset_map = build_rosetta_asset_map(
        glyph_ordinals, rosetta_to_ordinal, ocr_by_ordinal, base, cn
    )
    save_mapping_cache(cache_path, rosetta_to_ordinal, asset_map, glyph_ordinals)
    return asset_map
