#!/usr/bin/env python3
"""Local web server for Rosetta_CN character table editor."""

from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from dia_encode import validate_text
from rosetta_conflicts import (
    check_lines_against_table,
    check_mapping_against_table,
    conflict_error,
)
from rosetta_store import (
    align_text_to_indices,
    apply_mapping,
    load_table,
    save_table,
    table_stats,
)
from translation_store import (
    add_char_to_rosetta,
    apply_line_edit,
    char_help,
    load_translation_rows,
    repack_diachn,
)

TOOL_DIR = Path(__file__).resolve().parent
ROOT_DIR = TOOL_DIR.parent
TOOLS_DIR = TOOL_DIR


class RosettaEditorHandler(BaseHTTPRequestHandler):
    server_version = "IconoclastRosettaEditor/1.0"

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        sys.stdout.write("%s - %s\n" % (self.address_string(), format % args))

    def _send_json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def _file_path(self, url_path: str) -> Path | None:
        rel = url_path.lstrip("/")
        if not rel or ".." in rel.replace("\\", "/"):
            return None
        path = (TOOLS_DIR / rel).resolve()
        if not str(path).startswith(str(TOOLS_DIR.resolve())):
            return None
        return path

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/rosetta":
            try:
                lines, max_index = load_table(TOOL_DIR.parent)
                stats = table_stats(lines, max_index)
                self._send_json(200, {"lines": lines, "stats": stats})
            except Exception as exc:  # noqa: BLE001
                self._send_json(500, {"error": str(exc)})
            return

        if parsed.path == "/api/translations":
            try:
                rows, dia_path = load_translation_rows(ROOT_DIR)
                self._send_json(200, {"rows": rows, "source": str(dia_path)})
            except Exception as exc:  # noqa: BLE001
                self._send_json(500, {"error": str(exc)})
            return

        if parsed.path == "/api/translation/help":
            try:
                self._send_json(200, char_help(ROOT_DIR))
            except Exception as exc:  # noqa: BLE001
                self._send_json(500, {"error": str(exc)})
            return

        file_path = self._file_path(parsed.path)
        if file_path is None or not file_path.is_file():
            self.send_error(404)
            return

        content = file_path.read_bytes()
        content_type = "application/octet-stream"
        if file_path.suffix == ".html":
            content_type = "text/html; charset=utf-8"
        elif file_path.suffix == ".json":
            content_type = "application/json; charset=utf-8"
        elif file_path.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif file_path.suffix == ".js":
            content_type = "application/javascript; charset=utf-8"
        elif file_path.suffix == ".png":
            content_type = "image/png"

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            payload = self._read_json()
        except json.JSONDecodeError:
            self._send_json(400, {"error": "Invalid JSON"})
            return

        if parsed.path == "/api/save":
            lines = payload.get("lines")
            if not isinstance(lines, list):
                self._send_json(400, {"error": "Missing lines array"})
                return
            lines = [str(line) for line in lines]
            force_replace = bool(payload.get("force_replace", False))
            current_lines, max_index = load_table(TOOL_DIR.parent)
            conflicts = check_lines_against_table(current_lines, lines)
            if conflicts and not force_replace:
                self._send_json(409, conflict_error(conflicts))
                return
            written = save_table(TOOL_DIR.parent, lines)
            stats = table_stats(lines, max_index)
            self._send_json(200, {"ok": True, "written": written, "stats": stats, "lines": lines})
            return

        if parsed.path == "/api/set":
            index = payload.get("index")
            char = payload.get("char", "")
            if not isinstance(index, int):
                self._send_json(400, {"error": "index must be integer"})
                return
            force_replace = bool(payload.get("force_replace", False))
            lines, max_index = load_table(TOOL_DIR.parent)
            while len(lines) <= index:
                lines.append("")
            proposed = lines[:]
            proposed[index] = char
            conflicts = check_lines_against_table(lines, proposed, indices=[index])
            if conflicts and not force_replace:
                self._send_json(409, conflict_error(conflicts))
                return
            lines[index] = char
            written = save_table(TOOL_DIR.parent, lines)
            self._send_json(
                200,
                {
                    "ok": True,
                    "lines": lines,
                    "written": written,
                    "stats": table_stats(lines, max_index),
                },
            )
            return

        if parsed.path == "/api/resolve":
            index_text = payload.get("indices") or payload.get("encoding") or ""
            chinese = payload.get("text") or ""
            force = bool(payload.get("force", True))
            force_replace = bool(payload.get("force_replace", False))
            save = bool(payload.get("save", True))
            try:
                mapping = align_text_to_indices(index_text, chinese)
                lines, max_index = load_table(TOOL_DIR.parent)
                conflicts = check_mapping_against_table(lines, mapping)
                if conflicts and not force_replace:
                    self._send_json(409, conflict_error(conflicts))
                    return
                lines, changes = apply_mapping(lines, mapping, force=force)
                written: list[str] = []
                if save:
                    written = save_table(TOOL_DIR.parent, lines)
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "lines": lines,
                        "changes": changes,
                        "written": written,
                        "stats": table_stats(lines, max_index),
                    },
                )
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
            except Exception as exc:  # noqa: BLE001
                self._send_json(500, {"error": str(exc)})
            return

        if parsed.path == "/api/translation/save":
            line = payload.get("line")
            cn_text = payload.get("cn_text", "")
            speaker_cn = payload.get("speaker_cn")
            if not isinstance(line, int):
                self._send_json(400, {"error": "line must be integer"})
                return
            result = apply_line_edit(ROOT_DIR, line, cn_text, speaker_cn)
            if not result.get("ok"):
                self._send_json(400, result)
                return
            self._send_json(200, result)
            return

        if parsed.path == "/api/translation/validate":
            text = payload.get("text", "")
            try:
                lines, _ = load_table(ROOT_DIR)
                result = validate_text(text.replace("\n", "{new}"), lines)
                self._send_json(200, result)
            except Exception as exc:  # noqa: BLE001
                self._send_json(500, {"error": str(exc)})
            return

        if parsed.path == "/api/translation/repack":
            target = payload.get("target", "game")
            backup = bool(payload.get("backup", True))
            try:
                result = repack_diachn(ROOT_DIR, target=target, backup=backup)
                self._send_json(200, result)
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
            except Exception as exc:  # noqa: BLE001
                self._send_json(500, {"error": str(exc)})
            return

        if parsed.path == "/api/translation/add-char":
            char = payload.get("char", "")
            index = payload.get("index")
            save = bool(payload.get("save", True))
            try:
                result = add_char_to_rosetta(ROOT_DIR, char, index, save=save)
                self._send_json(200, result)
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
            except Exception as exc:  # noqa: BLE001
                self._send_json(500, {"error": str(exc)})
            return

        self._send_json(404, {"error": "Unknown API"})


def main() -> int:
    parser = argparse.ArgumentParser(description="Iconoclasts Rosetta character table editor")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--page", default="rosetta_editor.html", help="Page to open (rosetta_editor.html or translation_editor.html)")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    httpd = ThreadingHTTPServer(("", args.port), RosettaEditorHandler)
    url = f"http://127.0.0.1:{args.port}/{args.page}"
    print(f"Serving {TOOLS_DIR}")
    print(f"Open {url}")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
