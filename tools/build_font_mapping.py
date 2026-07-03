#!/usr/bin/env python3
"""Build and cache Rosetta index -> font glyph mapping."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from chowdren_assets import load_assets
from font_mapping import (
    build_rosetta_asset_map,
    build_rosetta_to_ordinal,
    expected_char,
    load_lines,
    save_mapping_cache,
)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    tool_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="Build Rosetta -> glyph mapping cache")
    parser.add_argument("--no-live-ocr", action="store_true", help="Skip live OCR scan")
    parser.add_argument(
        "--game-dir",
        type=Path,
        default=tool_dir.parent,
        help="Iconoclasts game root (contains Assets.dat)",
    )
    args = parser.parse_args()

    assets_path = args.game_dir / "Assets.dat"
    if not assets_path.exists():
        print(f"Error: missing {assets_path}")
        return 1

    data, entries, glyph_ordinals = load_assets(assets_path)
    base = load_lines(tool_dir / "Rosetta.txt")
    cn = load_lines(tool_dir / "Rosetta_CN.txt")
    rosetta_to_ordinal, ocr_by_ordinal = build_rosetta_to_ordinal(
        tool_dir,
        use_live_ocr=not args.no_live_ocr,
    )
    asset_map = build_rosetta_asset_map(
        glyph_ordinals, rosetta_to_ordinal, ocr_by_ordinal, base, cn
    )

    cache_path = tool_dir / "tools" / "glyphs" / "font_mapping.json"
    save_mapping_cache(cache_path, rosetta_to_ordinal, asset_map, glyph_ordinals)

    base = load_lines(tool_dir / "Rosetta.txt")
    cn = load_lines(tool_dir / "Rosetta_CN.txt")
    print(f"Mapped {len(rosetta_to_ordinal)} / {len(glyph_ordinals)} Rosetta slots")
    print(f"Wrote {cache_path}")
    from font_mapping import pick_ordinal

    for idx in [45, 56, 1020, 2162, 3399]:
        ch = expected_char(idx, base, cn) or "?"
        ord_i = rosetta_to_ordinal.get(idx)
        if ord_i is None:
            ord_i = pick_ordinal(idx, rosetta_to_ordinal, ocr_by_ordinal, base, cn)
        print(f"  #{idx} {ch!r}: ordinal {ord_i} -> asset {asset_map[idx]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
