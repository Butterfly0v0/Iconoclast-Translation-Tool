#!/usr/bin/env python3
"""Serve glyph_labeler.html and glyph assets on localhost."""

from __future__ import annotations

import argparse
import http.server
import socketserver
import sys
import webbrowser
from pathlib import Path


class LabelerHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str | None = None, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        sys.stdout.write("%s - %s\n" % (self.address_string(), format % args))


def main() -> int:
    tools_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Start glyph labeler web UI")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    handler = lambda *h_args, **h_kwargs: LabelerHandler(  # noqa: E731
        *h_args, directory=str(tools_dir), **h_kwargs
    )

    with socketserver.TCPServer(("", args.port), handler) as httpd:
        url = f"http://127.0.0.1:{args.port}/glyph_labeler.html"
        print(f"Serving {tools_dir}")
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
