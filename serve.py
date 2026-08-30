#!/usr/bin/env python3
"""Serve Phase 1 HTML report dashboards from public/."""

from __future__ import annotations

import argparse
import http.server
import socketserver
from pathlib import Path

from build_manifest import collect_reports, write_manifest

ROOT = Path(__file__).resolve().parent / "public"
DEFAULT_PORT = 8080


def allowed_paths() -> set[str]:
    paths = {"/", "/index.html", "/reports.json"}
    for path in ROOT.glob("*.html"):
        if path.name == "index.html":
            continue
        paths.add(f"/{path.name}")
    return paths


class ReportHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path not in allowed_paths():
            self.send_error(404, "Report not found")
            return
        if path == "/":
            self.path = "/index.html"
        super().do_GET()

    def log_message(self, fmt: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve IHY Phase 1 HTML reports")
    parser.add_argument("-p", "--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    if not ROOT.is_dir():
        raise SystemExit(f"Missing public directory: {ROOT}")

    reports = collect_reports()
    write_manifest(reports)

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", args.port), ReportHandler) as httpd:
        print(f"Serving reports at http://127.0.0.1:{args.port}/")
        for report in reports:
            print(f"  /{report['file']}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
