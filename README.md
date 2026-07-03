# Iconoclast Translation Tool

Fan-made toolkit for translating [Iconoclasts](https://store.steampowered.com/app/393520/Iconoclasts/) dialogue. This fork extends the original tool with **Simplified/Traditional Chinese** support, browser-based editors, and [ParaTranz](https://paratranz.cn/) import/export.

> **中文说明：** See [README_CN.md](README_CN.md) for the full Chinese localization guide.

## Fan-made translations

- Italian: https://alliceteam.altervista.org/iconoclasts-pc-psvita/ (All-Ice Team)

---

## Requirements

- [.NET 7](https://dotnet.microsoft.com/download/dotnet/7.0) — for `CLI.exe`
- **Python 3.10+** (optional, for Chinese tooling):

```powershell
pip install -r tools\requirements.txt
```

---

## Quick start (original CLI workflow)

1. Copy the game's `dia` file into this folder (or use **Copy dia from game** in the CLI).
2. Run `CLI.exe` (build with `dotnet build -c Release`, or use `bin\Release\net7.0\CLI.exe`).
3. **Extract data** → edit `Extracted text\Iconoclast.po` with [Poedit](https://poedit.net/) or similar.
4. **Repack text** → copy `Repacked File\dia` back into the game's `data\` folder.

For Chinese (`diachn` / `diacht`), switch the language file in the CLI menu first, and place `Rosetta_CN.txt` next to `CLI.exe` (see below).

---

## Chinese localization (this fork)

### Character table — `Rosetta_CN.txt`

Iconoclasts Chinese text uses a custom Rosetta index font (~3537 glyphs in `Assets.dat`). Generate or edit the mapping with:

| Method | Command / action |
|--------|------------------|
| Placeholder scaffold | `python build_rosetta_cn.py` |
| Sentence resolver | `python tools\resolve_sentence.py --indices "{#3399}!" --text "骗子!"` |
| **Character editor (recommended)** | Double-click `启动字符表编辑器.bat` |

### Translation editors

| Tool | Batch file | Purpose |
|------|------------|---------|
| Character / dialogue cross-ref editor | `启动字符表编辑器.bat` | Map indices to Han characters; search English lines |
| In-game Chinese text editor | `启动译文编辑器.bat` | Edit `diachn` lines directly, then repack |
| ParaTranz export / import | `导出ParaTranz.bat` / `导入ParaTranz.bat` | Collaborate on [ParaTranz](https://paratranz.cn/) |

### ParaTranz workflow

```powershell
python tools\paratranz_convert.py export
# Upload tools\paratranz\dialogue.json and speakers.json to ParaTranz
python tools\paratranz_convert.py import --target working   # test in tool folder
python tools\paratranz_convert.py import --target game      # write to game data\diachn
```

Each JSON entry: `key`, `original` (English), `translation` (Chinese), optional `context` (line number, encoding, etc.). Dialogue and speaker names are in **separate files**.

### Command-line helpers

```powershell
python tools\build_dialogue_crossref.py --cn-diff-only
python tools\apply_translation.py set --line 5 --text "{bub06}...骗子!"
python tools\apply_translation.py repack --target game
```

Glyph preview PNGs live in `tools\glyphs\` as `NNNNN.png` (Rosetta index). Edit or replace files there directly; the editor loads them by filename.

---

## Project layout

| Path | Description |
|------|-------------|
| `Iconoclast/` | Core dia / Rosetta / PO handling (C#) |
| `tools/` | Python parsers, web editors, ParaTranz converter |
| `Rosetta.txt` | Base Latin/symbol character table |
| `Rosetta_CN.txt` | Extended Chinese character table (user-generated) |
| `README_CN.md` | Full Chinese documentation |

Generated at runtime (not required in repo): `tools\paratranz\`, `tools\dialogue_crossref.*`, local `diachn` copies.

Shipped in repo: `tools\glyphs\NNNNN.png` — manually maintained 22×22 previews (`NNNNN` = Rosetta index).

---

## Build

```powershell
dotnet build -c Release
```

Output: `bin\Release\net7.0\CLI.exe`

---

## Acknowledgements

- Original tool: [Liquid-S/Iconoclast-Translation-Tool](https://github.com/Liquid-S/Iconoclast-Translation-Tool)
- [Yarhl](https://github.com/SceneGate/Yarhl) — `.po` file read/write (`Yarhl.dll`, `Yarhl.Media.dll`)
