# Iconoclast 中文本地化说明

本目录为修改版 [Iconoclast Translation Tool](https://github.com/Liquid-S/Iconoclast-Translation-Tool)，支持简体中文/繁体中文 `dia` 文件，并提供浏览器编辑器与 [ParaTranz](https://paratranz.cn/) 协作流程。

**本仓库：** https://github.com/Butterfly0v0/Iconoclast-Translation-Tool

---

## 首次准备

1. 安装 [.NET 7 运行时](https://dotnet.microsoft.com/download/dotnet/7.0)（或直接使用 `bin\Release\net7.0\CLI.exe`）

2. 安装 Python 依赖：

```powershell
pip install -r tools\requirements.txt
```

3. 生成中文字符表骨架：

```powershell
python build_rosetta_cn.py
```

这会分析 `diachn` 中用到的索引，生成带 PUA 占位符的 `Rosetta_CN.txt`。之后用字符表编辑器或 `resolve_sentence.py` 填写汉字。

4. 生成台词对照表（**编辑器与 ParaTranz 导入均依赖此文件**）：

```powershell
python tools\build_dialogue_crossref.py --cn-diff-only
```

输出：`tools\dialogue_crossref.json`、`.html`、`.csv`

---

## 字形预览图

编辑器中的字形预览来自 **`tools\glyphs\NNNNN.png`**，文件名中的 `NNNNN` 为 Rosetta 索引（如 `#3399` → `03399.png`）。

- 本目录为**人工维护**，部分预览已随仓库上传
- **请勿**从 `Assets.dat` 自动批量导出覆盖
- 说明见 `tools\glyphs\README.txt`

---

## 工具一览

### 1. 句子反推（`tools/resolve_sentence.py`）

已知官方中文时，从 `{#索引}` 反推字符映射：

```powershell
python tools\resolve_sentence.py --indices "{#3399}{#1020}!" --text "骗子!"
python tools\resolve_sentence.py --file pairs.json
```

### 2. 字形标注页（`tools/glyph_labeler.html`）

```powershell
python tools\serve_labeler.py
```

浏览器打开 `http://127.0.0.1:8765/glyph_labeler.html`，人工标注后导出 `Rosetta_CN.txt`。

### 3. 字符表编辑器（推荐）

双击 **`启动字符表编辑器.bat`**

- **台词对照**：搜英文 → 输入游戏内中文 → 写入 `Rosetta_CN.txt`
- **冲突确认**：索引已有不同汉字时弹窗确认后再写入
- **按索引编辑 / 字形网格**：查看 `tools\glyphs\` 预览图并改字
- **重复索引**：检测同一汉字对应多个索引

### 4. ParaTranz 协作翻译

**导出：** 双击 **`导出ParaTranz.bat`**

```powershell
python tools\paratranz_convert.py export
```

| 文件 | 说明 |
|------|------|
| `tools\paratranz\dialogue.json` | 台词，每行一条（`line.00005`），共 **4250** 条 |
| `tools\paratranz\speakers.json` | 说话人，**按英文名去重**（`speaker.MINA` 等，约 130 条） |

每条记录：`key`、`original`（英文）、`translation`（中文）、`context`（可选元信息）。

**在 ParaTranz 编辑后**，请**同时下载** `dialogue.json` 与 `speakers.json`，覆盖到 `tools\paratranz\`。

**导入方式 A — 译文编辑器（推荐）**

1. 双击 **`启动译文编辑器.bat`**
2. 点 **「导入 tools/paratranz」** 读取默认目录，或 **「选择 JSON 文件导入」** 手动选取两个 JSON
3. 导入结果写入待打包缓存 `tools\translation_edits.json`
4. 确认无误后点 **「打包写入游戏 diachn」**

**导入方式 B — 命令行**

双击 **`导入ParaTranz.bat`**，或：

```powershell
python tools\paratranz_convert.py import --target working
python tools\paratranz_convert.py import --target game
```

**说话人导入：** 根据 `dialogue_crossref.json` 中每行的 `speaker_en`，将 `speaker.*` 的译文写回对应行；兼容旧版 `line.00005.speaker` 逐行格式。

**说明：** 与当前 `diachn` 相同的译文会被跳过（`skipped_unchanged`）；仅真正改动的行会进入待打包列表。仅改说话人时，打包不会覆盖台词正文。

### 5. 译文编辑器

双击 **`启动译文编辑器.bat`**

1. 编辑中文（保留 `{bub06}{font02}…` 标签，换行用 `{new}`）
2. 「检查缺字」→「保存当前行修改」
3. 「打包写入游戏 diachn」

命令行：

```powershell
python tools\apply_translation.py set --line 5 --text "{bub06}...骗子!"
python tools\apply_translation.py repack --target game
```

---

## 本地 Web 服务

两个 `.bat` 启动脚本会在 **8765** 端口开启本地服务。若端口已被占用（例如上次窗口未关闭），程序会自动尝试 **8766、8767…**；也可直接刷新浏览器访问已在运行的旧地址。

关闭黑色命令行窗口即可停止服务。

---

## 打包与部署

### 方式 A：译文编辑器（推荐）

保存修改 → 打包写入 `data\diachn` → 进游戏验证

### 方式 B：CLI.exe + Poedit

1. CLI 切换到 `diachn` → Copy dia → Extract text
2. Poedit 编辑 PO（UTF-8）
3. Repack → 复制到游戏 `data\`

两种方式均需 `Rosetta_CN.txt` 与 `bin\Release\net7.0\Rosetta_CN.txt` 同步（编辑器会自动写入）。

---

## 译文超出字符表时如何加字

游戏字体固定约 **3537** 个 22×22 槽位（索引 **0–3536**），不能通过本工具自动增加 `Assets.dat` 中的 PNG。

1. **复用空槽位**：译文编辑器 → 检查缺字 → 加入字符表（占用 PUA 占位索引）
2. **替换字形图**：修改 `tools\glyphs\NNNNN.png`，再自行处理 `Assets.dat` 打包
3. **同字多索引**：C# 打包取最高索引；可复用已有字形索引
4. **槽位用尽**：替换冷僻字索引或修改 `Assets.dat`（超出本工具范围）

---

## 常见问题

| 现象 | 处理 |
|------|------|
| 启动时报 `PermissionError` / 端口 8765 | 关闭先前打开的编辑器窗口，或让程序自动换用 8766+ 端口 |
| ParaTranz 导入后「已修改」很多但内容没变 | 先运行 `build_dialogue_crossref.py --cn-diff-only`；与 `diachn` 相同的项会被自动忽略 |
| 只改了说话人，打包后台词被清空 | 请使用最新版工具；当前打包仅写入缓存里实际存在的字段 |
| 字符表编辑器「加载失败」 | 更新代码后重启 `.bat` 并刷新浏览器 |

---

## 重要说明

- 索引 **0–155**：拉丁/符号；**156+**：中文及共用符号
- 字符表未填完时，可用 `{#索引}` 占位符编辑并回写
- 工具统一 **UTF-8**，避免 GBK 乱码

---

## 文件结构

| 路径 | 说明 |
|------|------|
| `tools/rosetta_editor.html` | **字符表编辑器** |
| `tools/translation_editor.html` | **译文编辑器**（含 ParaTranz 导入） |
| `tools/paratranz_convert.py` | ParaTranz 导出 / 导入 |
| `tools/translation_store.py` | 译文缓存、ParaTranz 合并、打包 |
| `tools/build_dialogue_crossref.py` | 英中台词对照表 |
| `tools/resolve_sentence.py` | 已知句子 → 更新字符表 |
| `tools/apply_translation.py` | 命令行改译文 / 打包 |
| `tools/glyphs/NNNNN.png` | 字形预览（人工维护） |
| `tools/translation_edits.json` | 待打包译文缓存（本地生成） |
| `build_rosetta_cn.py` | 生成 `Rosetta_CN.txt` 骨架 |
| `Rosetta_CN.txt` | 扩展字符表 |
| `启动字符表编辑器.bat` | 启动字符表编辑器 |
| `启动译文编辑器.bat` | 启动译文编辑器 |
| `导出ParaTranz.bat` / `导入ParaTranz.bat` | ParaTranz 快捷脚本 |
