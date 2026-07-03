# Iconoclast Translation Tool

Fan-made toolkit for translating [Iconoclasts](https://store.steampowered.com/app/393520/Iconoclasts/) dialogue. This fork adds **Simplified/Traditional Chinese** support, browser-based editors, and [ParaTranz](https://paratranz.cn/) import/export.

> **中文说明：** See [README_CN.md](README_CN.md) for the full Chinese localization guide.

**Fork repository:** https://github.com/Butterfly0v0/Iconoclast-Translation-Tool  
**Upstream:** https://github.com/Liquid-S/Iconoclast-Translation-Tool

## Fan-made translations

- Italian: https://alliceteam.altervista.org/iconoclasts-pc-psvita/ (All-Ice Team)

---

## Requirements

- [.NET 7](https://dotnet.microsoft.com/download/dotnet/7.0) — for `CLI.exe`
- **Python 3.10+** (for Chinese tooling):

```powershell
pip install -r tools\requirements.txt
```

Place the game folder next to this tool (default: `..\data\dia`, `..\data\diachn`, `..\Assets.dat`).

---

## Quick start (original CLI)

1. Copy the game's `dia` into this folder, or use **Copy dia from game** in the CLI.
2. Run `CLI.exe` (`dotnet build -c Release` → `bin\Release\net7.0\CLI.exe`).
3. **Extract data** → edit `Extracted text\Iconoclast.po` with [Poedit](https://poedit.net/).
4. **Repack text** → copy `Repacked File\dia` back to the game's `data\` folder.

For Chinese (`diachn` / `diacht`), switch the language file in the CLI menu and keep `Rosetta_CN.txt` next to `CLI.exe`.

---

## Chinese localization workflow

### 1. Character table — `Rosetta_CN.txt`

Iconoclasts Chinese uses a Rosetta index font (~3537 glyph slots). Build and fill the mapping:

| Step | Action |
|------|--------|
| Scaffold | `python build_rosetta_cn.py` — creates `Rosetta_CN.txt` with PUA placeholders |
| Resolve from known text | `python tools\resolve_sentence.py --indices "{#3399}!" --text "骗子!"` |
| **Recommended** | Double-click `启动字符表编辑器.bat` |

Generate the dialogue cross-reference first (needed by editors and ParaTranz import):

```powershell
python tools\build_dialogue_crossref.py --cn-diff-only
```

### 2. Glyph previews — `tools\glyphs\`

Preview PNGs are **manually maintained**: `NNNNN.png` where `NNNNN` is the 5-digit Rosetta index (`#3399` → `03399.png`). The character editor loads these files directly. Do not overwrite them with automated Assets.dat exports.

See `tools\glyphs\README.txt` for naming rules.

### 3. Translation editors

| Tool | Batch file | Purpose |
|------|------------|---------|
| Character / dialogue editor | `启动字符表编辑器.bat` | Map indices to Han characters; search English lines; conflict checks |
| In-game Chinese text editor | `启动译文编辑器.bat` | Edit `diachn` lines, validate chars, repack |
| ParaTranz export / import | `导出ParaTranz.bat` / `导入ParaTranz.bat` | Collaborate on [ParaTranz](https://paratranz.cn/) |

### 4. ParaTranz workflow

```powershell
python tools\paratranz_convert.py export
# Edit tools\paratranz\dialogue.json and speakers.json on ParaTranz
python tools\paratranz_convert.py import --target working
python tools\paratranz_convert.py import --target game
```

**Output files**

| File | Contents |
|------|----------|
| `dialogue.json` | One entry per dialogue line (`line.00005`, …) |
| `speakers.json` | **Deduplicated** speakers by English name (`speaker.MINA`, `speaker.BLACK`, …) |

**JSON entry format**

```json
{
  "key": "line.00005",
  "original": "English or tagged source text",
  "translation": "Chinese translation",
  "context": "speaker_en=WHITE; line=5; ..."
}
```

**Speaker import:** translations from `speaker.*` keys are applied to every line whose `speaker_en` matches the entry's `original` field (via `dialogue_crossref.json`). Legacy per-line keys `line.00005.speaker` are still supported.

Before first ParaTranz import, run `build_dialogue_crossref.py --cn-diff-only`.

### 5. Command-line helpers

```powershell
python tools\apply_translation.py set --line 5 --text "{bub06}{font02}...骗子!"
python tools\apply_translation.py repack --target game
python tools\apply_translation.py add-char 龘
python tools\apply_translation.py slots
```

---

## Deploy translated `diachn`

**Option A — Translation editor (recommended):** save all edits → **打包写入游戏 diachn** → test in game.

**Option B — CLI + Poedit:** extract PO → edit → repack → copy to `data\`.

Keep `Rosetta_CN.txt` synced in the tool root and `bin\Release\net7.0\`.

---

## Project layout

| Path | Description |
|------|-------------|
| `Iconoclast/` | Core dia / Rosetta / PO handling (C#) |
| `tools/` | Python parsers, web editors, ParaTranz converter |
| `tools/glyphs/NNNNN.png` | Manually maintained 22×22 glyph previews |
| `tools/paratranz/` | Exported ParaTranz JSON (generated locally) |
| `Rosetta.txt` | Base Latin/symbol table |
| `Rosetta_CN.txt` | Extended Chinese character table |
| `README_CN.md` | Full Chinese documentation |

---

## Build

```powershell
dotnet build -c Release
```

Output: `bin\Release\net7.0\CLI.exe`

---

## Acknowledgements

- Original tool: [Liquid-S/Iconoclast-Translation-Tool](https://github.com/Liquid-S/Iconoclast-Translation-Tool)
- [Yarhl](https://github.com/SceneGate/Yarhl) — `.po` read/write (`Yarhl.dll`, `Yarhl.Media.dll`)
