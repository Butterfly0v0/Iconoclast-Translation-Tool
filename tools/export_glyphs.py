#!/usr/bin/env python3
"""Export all Rosetta-indexed 22x22 glyphs as PNG files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from chowdren_assets import extract_glyph_by_asset, load_assets
from font_mapping import get_rosetta_asset_map, load_mapping_cache


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")

    tool_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="Export Iconoclasts font glyphs by Rosetta index")
    parser.add_argument(
        "--game-dir",
        type=Path,
        default=tool_dir.parent,
        help="Iconoclasts game root",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent / "glyphs",
        help="Output directory for PNG glyphs",
    )
    parser.add_argument(
        "--max-index",
        type=int,
        default=None,
        help="Highest Rosetta index to export (default: all 22x22 glyphs)",
    )
    parser.add_argument(
        "--rebuild-mapping",
        action="store_true",
        help="Rebuild font_mapping.json before export",
    )
    args = parser.parse_args()

    assets_path = args.game_dir / "Assets.dat"
    if not assets_path.exists():
        print(f"Error: missing {assets_path}")
        return 1

    data, entries, _glyph_ordinals = load_assets(assets_path)
    asset_map = get_rosetta_asset_map(tool_dir, rebuild=args.rebuild_mapping)
    max_index = args.max_index if args.max_index is not None else len(asset_map) - 1
    max_index = min(max_index, len(asset_map) - 1)

    args.out.mkdir(parents=True, exist_ok=True)
    mapping: dict[str, int] = {}
    ordinal_map: dict[str, int] = {}

    cache = load_mapping_cache(args.out / "font_mapping.json") or load_mapping_cache(
        Path(__file__).resolve().parent / "glyphs" / "font_mapping.json"
    )
    if cache:
        rosetta_to_ordinal, _, _ = cache
        ordinal_map = {str(k): v for k, v in rosetta_to_ordinal.items()}

    print(f"Exporting glyphs 0..{max_index} to {args.out} (font-corrected mapping)")
    for rosetta_index in range(max_index + 1):
        asset_index = asset_map[rosetta_index]
        image = extract_glyph_by_asset(data, entries, asset_index)
        filename = f"{rosetta_index:05d}.png"
        image.save(args.out / filename)
        mapping[str(rosetta_index)] = asset_index
        if rosetta_index % 500 == 0:
            print(f"  {rosetta_index}/{max_index}")

    meta = {
        "glyph_size": [22, 22],
        "glyph_count": max_index + 1,
        "assets_path": str(assets_path),
        "mapping_version": 2,
        "rosetta_to_asset": mapping,
        "rosetta_to_ordinal": ordinal_map,
    }
    (args.out / "mapping.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Done. Wrote {max_index + 1} PNG files and mapping.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
