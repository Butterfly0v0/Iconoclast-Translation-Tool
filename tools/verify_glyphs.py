#!/usr/bin/env python3
"""Verify exported glyph PNGs match Rosetta_CN expected chars."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageOps

try:
    from rapidocr_onnxruntime import RapidOCR
except ImportError:
    RapidOCR = None  # type: ignore[misc, assignment]

from font_mapping import expected_char, load_lines

PUA_BASE = 0xE000


def ocr_png(engine, path: Path) -> str | None:
    img = Image.open(path).convert("RGBA").resize((88, 88), Image.NEAREST)
    bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    bg.paste(img, mask=img.split()[3])
    result = engine(ImageOps.grayscale(bg))
    if result and result[0]:
        return result[0][0][1]
    return None


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    tool_dir = Path(__file__).resolve().parent.parent
    glyphs = tool_dir / "tools" / "glyphs"
    base = load_lines(tool_dir / "Rosetta.txt")
    cn = load_lines(tool_dir / "Rosetta_CN.txt")

    if RapidOCR is None:
        print("Install rapidocr-onnxruntime")
        return 1

    engine = RapidOCR()
    checks = [45, 56, 1020, 2162, 3399]
    ok = 0
    for idx in checks:
        exp = expected_char(idx, base, cn)
        png = glyphs / f"{idx:05d}.png"
        if not png.exists():
            print(f"#{idx} MISSING {png.name} (expect {exp!r})")
            continue
        got = ocr_png(engine, png)
        match = got == exp or (exp == "W" and got and got.startswith("W"))
        status = "OK" if match else "FAIL"
        if match:
            ok += 1
        print(f"#{idx} expect {exp!r} got {got!r} -> {status}")
    print(f"Passed {ok}/{len(checks)}")
    return 0 if ok == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
