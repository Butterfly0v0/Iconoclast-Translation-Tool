# Iconoclast 中文本地化说明



本目录为修改版 [Iconoclast Translation Tool](https://github.com/Liquid-S/Iconoclast-Translation-Tool)，支持简体中文/繁体中文 `dia` 文件。



## 首次准备



1. 安装 [.NET 7 运行时](https://dotnet.microsoft.com/download/dotnet/7.0)（或直接使用已编译的 `bin\Release\net7.0\CLI.exe`）

2. 安装 Python 工具依赖：



```powershell

pip install -r tools\requirements.txt

```



3. 生成中文字符表（推荐 OCR 流程）：



```powershell

python tools\build_rosetta_ocr.py

```



这会从 `Assets.dat` 导出 22×22 字形图、OCR 识别，并生成 `Rosetta_CN.txt`。



旧版占位符脚本仍可用：`python build_rosetta_cn.py`



---



## 三种字符表工具



### 1. 自动 OCR（`tools/build_rosetta_ocr.py`）



从游戏字体图集自动识别汉字，写入 `Rosetta_CN.txt`。



```powershell

# 导出字形 + OCR（首次较慢，约 3500 张图）

python tools\build_rosetta_ocr.py



# 仅重新 OCR（已有 tools\glyphs\）

python tools\build_rosetta_ocr.py --export-glyphs

```



- 索引 **0–155**：沿用 `Rosetta.txt` 拉丁字符

- 索引 **156+**：OCR 识别 22×22 字形（`font02` 中文字体）

- 识别失败的位置用 PUA 占位符（`U+E000+`），可在标注页补全

- 元数据：`tools\rosetta_ocr_meta.json`



### 2. 句子反推（`tools/resolve_sentence.py`）



已知某句官方中文时，从 `{#索引}` 字符串反推字符映射。



```powershell

python tools\resolve_sentence.py --indices "{#3399}{#1020}!" --text "骗子!"

```



批量 JSON 示例 `pairs.json`：



```json

[

  {"indices": "{#3399}{#1020}!", "text": "骗子!"},

  {"indices": "{#2162}", "text": "白"}

]

```



```powershell

python tools\resolve_sentence.py --file pairs.json

```



### 3. 字形标注页（`tools/glyph_labeler.html`）



OCR 不准或待确认的字形，可在浏览器里人工标注并导出 `Rosetta_CN.txt`。



```powershell

python tools\serve_labeler.py

```



浏览器打开 `http://127.0.0.1:8765/glyph_labeler.html`：



- 筛选「待标注 / 占位符」

- 输入对应汉字，自动保存到浏览器

- **导出 Rosetta_CN.txt** 后复制到工具目录



### 4. 台词对照表（`tools/build_dialogue_crossref.py`）



生成英文原文、英文编码、中文编码的对照表，便于在游戏中核对索引对应的汉字。



```powershell

python tools\build_dialogue_crossref.py



# 仅输出中文编码与英文不同的行（推荐）

python tools\build_dialogue_crossref.py --cn-diff-only

```



输出：`tools\dialogue_crossref.html`（可搜索）、`dialogue_crossref.csv`（Excel）、`dialogue_crossref.json`



### 5. 字符表编辑器（推荐，免命令行）



双击 `启动字符表编辑器.bat`，浏览器会自动打开编辑器。



功能：

- **台词对照**：搜索英文 → 选中行 → 输入游戏内中文 → 一键写入 `Rosetta_CN.txt`

- **冲突确认**：若某索引在字符表中已有对应汉字，而本次填写要改为不同汉字，保存前会弹窗列出全部冲突（格式如 `#3399已对应文字"骗"，是否强制替换为"偏"`），确认后才写入；PUA 占位或空索引直接填写，同一索引同一汉字不提示

- **按索引编辑**：查看字形图、修改单个字

- **字形网格**：批量浏览待填索引



### 6. ParaTranz 协作翻译（`tools/paratranz_convert.py`）

与 [ParaTranz](https://paratranz.cn/) 协作时，可将台词导出为两个 JSON 文件（台词与说话人分开），在 ParaTranz 中编辑后再导入写回 `diachn`。

**流程：**

1. 双击 `导出ParaTranz.bat`（或 `python tools\paratranz_convert.py export`）
2. 将 `tools\paratranz\dialogue.json` 与 `speakers.json` 上传到 ParaTranz 项目
3. 在 ParaTranz 中编辑 `translation` 字段
4. 下载 JSON 覆盖 `tools\paratranz\` 后，双击 `导入ParaTranz.bat`（默认写入工具目录 `diachn` 副本）
5. 验证无误后：`python tools\paratranz_convert.py import --target game` 写入游戏 `data\diachn`

每条记录格式：`key`、`original`（英文）、`translation`（中文）、`context`（行号、编码等元信息，可选）。

### 7. 译文编辑器（修改官方中文译文）



字符表填完后，用此工具直接改 `diachn` 里的中文台词，无需 Poedit。



双击 `启动译文编辑器.bat` 打开。



**流程：**

1. 搜索并选中一行，在右侧编辑中文（保留 `{bub06}{font02}…` 等标签，换行用 `{new}`）

2. 点「检查缺字」确认所有汉字都在 `Rosetta_CN.txt` 中

3. 点「保存当前行修改」（可多次，修改会暂存）

4. 全部完成后点「打包写入游戏 diachn」→ 自动备份并写入 `..\data\diachn`



**命令行（可选）：**



```powershell
python tools\apply_translation.py set --line 5 --text "{bub06}{font02}...骗子!"
python tools\apply_translation.py repack --target game
python tools\apply_translation.py add-char 龘
python tools\apply_translation.py slots
```



---



## 打包与部署



### 方式 A：译文编辑器（推荐）



1. 在译文编辑器中保存所有修改

2. 点「打包写入游戏 diachn」

3. 启动游戏验证



### 方式 B：CLI.exe + Poedit（传统）



1. 运行 `bin\Release\net7.0\CLI.exe`

2. 菜单 **Change language file** → `diachn`

3. **Copy dia from game** → 从 `..\data\` 复制

4. **Extract text** → 生成 `Extracted text\Iconoclast.po`

5. 用 Poedit 编辑 PO（UTF-8）

6. **Repack text** → 输出 `Repacked File\diachn`

7. 复制到游戏 `data\` 覆盖



两种方式都需要 `Rosetta_CN.txt` 与 `bin\Release\net7.0\Rosetta_CN.txt` 保持同步（编辑器会自动写入两处）。



---



## 译文超出字符表时如何加字



游戏字体固定约 **3537** 个 22×22 字形槽（Rosetta 索引 **0–3536**），**不能**通过本工具自动往 `Assets.dat` 里增加新 PNG。



**可行做法：**



1. **复用空槽位**：译文编辑器 →「检查缺字」→ 输入缺失汉字 →「加入字符表」  
   会自动占用下一个 PUA 占位符索引。

2. **替换字形图**：若该索引的 PNG 形状不对，用图像软件替换  
   `tools\glyphs\NNNNN.png`（NNNNN 为 5 位索引号），再重新打包 `Assets.dat`（需自行处理，本工具仅提取字形）。

3. **同字多索引**：同一汉字可能对应多个索引；打包时 C# 工具取**最高索引**。  
   若已有正确字形，直接在 `Rosetta_CN.txt` 映射到该索引即可，不必新建。

4. **实在不够**：只能替换游戏中不再使用的冷僻字索引，或修改 `Assets.dat` 资源（超出本工具范围）。



---



## 翻译工具使用流程（Poedit 路线）



1. 运行 `bin\Release\net7.0\CLI.exe`

2. 菜单 **Change language file** 切换到 `diachn`（简体）或 `diacht`（繁体）

3. **Copy dia from game** — 从 `..\data\` 复制语言文件

4. **Extract text** — 生成 `Extracted text\Iconoclast.po`

5. 用 [Poedit](https://poedit.net/) 编辑 PO 文件（编码 **UTF-8**）

   - 完成 `Rosetta_CN.txt` 后，PO 里会显示真实汉字而非 `{#3399}`

6. **Repack text** — 输出到 `Repacked File\diachn`

7. 复制回游戏 `data\` 覆盖原文件



## 重要说明



- 游戏 `{font02}` 中文字体：每个 Rosetta 索引对应 `Assets.dat` 中一张 **22×22** 字形图（共 3537 张），**不是**按资源包扫描顺序一一对应，需先运行 `重建字形映射.bat` 或 `python tools\build_font_mapping.py` + `python tools\export_glyphs.py` 生成正确预览

- 索引 **0–155** 为拉丁/符号；**156+** 为中文（及共用符号）

- 若 OCR/标注未完成，仍可用 `{#索引}` 占位符编辑并回写

- 工具使用 **UTF-8**，避免中文 Windows 下 GBK 乱码



## 文件结构



| 路径 | 说明 |

|------|------|

| `tools/chowdren_assets.py` | 解析 Assets.dat、按索引提取字形 |

| `tools/font_mapping.py` | Rosetta 索引 → 字形图映射 |
| `tools/build_font_mapping.py` | 构建映射缓存 |
| `tools/export_glyphs.py` | 导出 `tools/glyphs/00000.png` … |
| `重建字形映射.bat` | 一键重建映射并导出 PNG |

| `tools/build_rosetta_ocr.py` | OCR → `Rosetta_CN.txt` |

| `tools/resolve_sentence.py` | 已知句子 → 更新字符表 |

| `tools/glyph_labeler.html` | 浏览器字形标注（旧版） |

| `tools/rosetta_editor.html` | **字符表编辑器（推荐）** |

| `tools/translation_editor.html` | **译文编辑器** |

| `tools/apply_translation.py` | 命令行改译文 / 打包 |
| `tools/paratranz_convert.py` | ParaTranz JSON 导出 / 导入 |
| `导出ParaTranz.bat` / `导入ParaTranz.bat` | 双击导出 / 导入 ParaTranz |

| `tools/rosetta_server.py` | 编辑器本地服务 |
| `tools/rosetta_conflicts.py` | 字符表索引冲突检测 |

| `启动字符表编辑器.bat` | 双击启动字符表 |

| `启动译文编辑器.bat` | 双击启动译文编辑 |

| `Rosetta_CN.txt` | 扩展字符表（约 3455 行） |


