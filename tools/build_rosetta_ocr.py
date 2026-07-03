#!/usr/bin/env python3
"""OCR exported glyphs and build Rosetta_CN.txt."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Install Pillow: pip install Pillow") from exc

try:
    from rapidocr_onnxruntime import RapidOCR
except ImportError:
    RapidOCR = None  # type: ignore[misc, assignment]

PUA_BASE = 0xE000


def load_base_rosetta(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    lines = [line for line in text.split("\n") if line != ""]
    return lines


def collect_max_index(dia_path: Path) -> int:
    data = dia_path.read_bytes()
    indices = [int(m.group(1)) for m in re.finditer(rb"(?<=[\x00|{])(\d+)(?=[\x00|}\\])", data)]
    return max(indices) if indices else 0


def ocr_glyph(engine, png_path: Path, scale: int = 4) -> tuple[str | None, float]:
    image = Image.open(png_path).convert("RGBA")
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
    # Single glyph only
    return text[0], confidence


def build_table(
    base: list[str],
    max_index: int,
    glyphs_dir: Path,
    min_confidence: float,
    ocr_start: int,
    only_indices: set[int] | None = None,
    existing_meta: dict[int, dict] | None = None,
    checkpoint_path: Path | None = None,
) -> tuple[list[str], dict[int, dict]]:
    extended = base[:]
    while len(extended) <= max_index:
        extended.append("")

    meta: dict[int, dict] = {int(k): v for k, v in (existing_meta or {}).items()}
    engine = None
    if RapidOCR is not None:
        print("Using RapidOCR...")
        engine = RapidOCR()
    else:
        print(f"RapidOCR not installed; indices >= {ocr_start} will use PUA placeholders.")
        print("Install: pip install rapidocr-onnxruntime")

    if only_indices is not None:
        ocr_targets = sorted(i for i in only_indices if i >= ocr_start and i <= max_index)
        print(f"OCR scope: {len(ocr_targets)} indices (used-only mode)")
    else:
        ocr_targets = [i for i in range(len(extended)) if i >= ocr_start]

    processed = 0
    total = len(ocr_targets)

    for index in ocr_targets:
        if index < len(base) and base[index]:
            extended[index] = base[index]
            meta.setdefault(index, {"source": "Rosetta.txt", "char": base[index]})
            if meta[index].get("source") == "ocr":
                extended[index] = meta[index]["char"]
                continue

        if meta.get(index, {}).get("source") == "ocr":
            extended[index] = meta[index]["char"]
            continue
        if meta.get(index, {}).get("char") and ord(meta[index]["char"]) < PUA_BASE:
            extended[index] = meta[index]["char"]
            continue

        png = glyphs_dir / f"{index:05d}.png"
        if not png.exists():
            extended[index] = chr(PUA_BASE + (index - len(base)))
            meta[index] = {"source": "missing_glyph", "char": extended[index]}
            continue

        char: str | None = None
        confidence = 0.0
        if engine is not None:
            char, confidence = ocr_glyph(engine, png)

        if char and confidence >= min_confidence and len(char) == 1:
            extended[index] = char
            meta[index] = {"source": "ocr", "char": char, "confidence": confidence}
        else:
            extended[index] = chr(PUA_BASE + (index - len(base)))
            meta[index] = {
                "source": "placeholder",
                "char": extended[index],
                "confidence": confidence,
                "ocr_guess": char,
            }

        processed += 1
        if processed % 50 == 0:
            print(f"  OCR progress: {processed}/{total}", flush=True)
            if checkpoint_path is not None:
                save_checkpoint(
                    checkpoint_path, extended, meta, max_index, min_confidence, ocr_start
                )

    for index in range(len(extended)):
        if extended[index]:
            continue
        if index < len(base) and base[index]:
            extended[index] = base[index]
        elif index >= ocr_start:
            extended[index] = chr(PUA_BASE + (index - len(base)))

    return extended, meta


def save_checkpoint(
    path: Path,
    extended: list[str],
    meta: dict[int, dict],
    max_index: int,
    min_confidence: float,
    ocr_start: int,
) -> None:
    filled_ocr = sum(1 for m in meta.values() if m.get("source") == "ocr")
    placeholders = sum(
        1
        for i in range(ocr_start, len(extended))
        if extended[i] and ord(extended[i]) >= PUA_BASE
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "max_index": max_index,
                "ocr_start": ocr_start,
                "min_confidence": min_confidence,
                "filled_ocr": filled_ocr,
                "placeholders": placeholders,
                "entries": {str(k): v for k, v in sorted(meta.items())},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def write_rosetta(path: Path, lines: list[str]) -> None:
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")

    tool_dir = Path(__file__).resolve().parent.parent
    default_glyphs = Path(__file__).resolve().parent / "glyphs"

    parser = argparse.ArgumentParser(description="OCR glyphs and build Rosetta_CN.txt")
    parser.add_argument("--game-dir", type=Path, default=tool_dir.parent)
    parser.add_argument("--glyphs", type=Path, default=default_glyphs)
    parser.add_argument("--dia", type=str, default="diachn")
    parser.add_argument("--min-confidence", type=float, default=0.45)
    parser.add_argument("--ocr-start", type=int, default=156)
    parser.add_argument("--export-glyphs", action="store_true", help="Run export_glyphs.py first")
    parser.add_argument(
        "--used-only",
        action="store_true",
        help="OCR only indices referenced in diachn (faster)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from tools/rosetta_ocr_meta.json checkpoint",
    )
    args = parser.parse_args()

    base_path = tool_dir / "Rosetta.txt"
    out_path = tool_dir / "Rosetta_CN.txt"
    meta_path = tool_dir / "tools" / "rosetta_ocr_meta.json"

    if not base_path.exists():
        print(f"Error: missing {base_path}")
        return 1

    dia_path = args.game_dir / "data" / args.dia
    if not dia_path.exists():
        print(f"Error: missing {dia_path}")
        return 1

    if args.export_glyphs or not args.glyphs.exists():
        print("Exporting glyphs from Assets.dat...")
        import subprocess

        export_script = Path(__file__).resolve().parent / "export_glyphs.py"
        cmd = [
            sys.executable,
            str(export_script),
            "--game-dir",
            str(args.game_dir),
            "--out",
            str(args.glyphs),
        ]
        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            return result.returncode

    if not args.glyphs.exists():
        print(f"Error: glyph folder missing: {args.glyphs}")
        return 1

    base = load_base_rosetta(base_path)
    max_index = collect_max_index(dia_path)
    print(f"Base Rosetta: {len(base)} entries; {args.dia} max index: {max_index}")

    existing_meta: dict[int, dict] | None = None
    if args.resume and meta_path.exists():
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
        existing_meta = {int(k): v for k, v in payload.get("entries", {}).items()}
        print(f"Resuming from checkpoint ({len(existing_meta)} entries)")

    only_indices: set[int] | None = None
    if args.used_only:
        used_path = tool_dir / "indices_used.txt"
        if not used_path.exists():
            import subprocess

            subprocess.run([sys.executable, str(tool_dir / "build_rosetta_cn.py")], check=False)
        if used_path.exists():
            only_indices = {
                int(line.strip())
                for line in used_path.read_text(encoding="utf-8").splitlines()
                if line.strip().isdigit()
            }
            print(f"Used-only: {len(only_indices)} unique indices from {used_path.name}")

    extended, meta = build_table(
        base,
        max_index,
        args.glyphs,
        args.min_confidence,
        args.ocr_start,
        only_indices=only_indices,
        existing_meta=existing_meta,
        checkpoint_path=meta_path,
    )
    write_rosetta(out_path, extended)

    filled_ocr = sum(1 for m in meta.values() if m.get("source") == "ocr")
    placeholders = sum(
        1
        for i in range(args.ocr_start, len(extended))
        if extended[i] and ord(extended[i]) >= PUA_BASE
    )

    save_checkpoint(
        meta_path, extended, meta, max_index, args.min_confidence, args.ocr_start
    )

    # Copy to build output if present
    for copy_dir in [tool_dir / "bin" / "Release" / "net7.0"]:
        if copy_dir.exists():
            write_rosetta(copy_dir / "Rosetta_CN.txt", extended)

    print(f"Wrote {out_path} ({len(extended)} entries)")
    print(f"  OCR filled (index>={args.ocr_start}): {filled_ocr}")
    print(f"  PUA placeholders remaining: {placeholders}")
    print(f"  Metadata: {meta_path}")
    if placeholders:
        print("Open tools/glyph_labeler.html to fix remaining glyphs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
