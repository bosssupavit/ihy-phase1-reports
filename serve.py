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


def is_allowed(path: str) -> bool:
    if path in {"/", "/index.html", "/reports.json"}:
        return True
    rel = path.lstrip("/")
    if not rel or ".." in Path(rel).parts:
        return False
    candidate = (ROOT / rel).resolve()
    try:
        candidate.relative_to(ROOT.resolve())
    except ValueError:
        return False
    if not candidate.is_file():
        return False
    if path.startswith("/data/") and candidate.suffix == ".json":
        return True
    if candidate.parent == ROOT.resolve() and candidate.suffix == ".html":
        return candidate.name != "index.html"
    return False


class ReportHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if not is_allowed(path):
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
            for rel in (report.get("files") or {}).values():
                print(f"    /{rel}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
