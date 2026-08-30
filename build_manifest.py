#!/usr/bin/env python3
"""Build public/reports.json from HTML dashboards in public/."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "public"
RUNS_ROOT = Path(__file__).resolve().parent.parent
SKIP = {"index.html"}


def label_for(name: str) -> str:
    stem = Path(name).stem
    stem = re.sub(r"^phase\d+_", "", stem)
    stem = stem.replace("_", " ").strip()
    return stem.title() if stem else name


def run_meta_for(public_name: str) -> str | None:
    """Newest run folder that has a matching *_dashboard.html source."""
    stem = Path(public_name).stem
    matches: list[str] = []
    for run_dir in RUNS_ROOT.glob("20*"):
        if not run_dir.is_dir():
            continue
        if (run_dir / f"{stem}_dashboard.html").is_file() or (
            run_dir / f"{stem}.html"
        ).is_file():
            matches.append(run_dir.name)
    return max(matches) if matches else None


def collect_reports() -> list[dict[str, str]]:
    reports: list[dict[str, str]] = []
    for path in sorted(ROOT.glob("*.html")):
        if path.name in SKIP:
            continue
        entry = {
            "file": path.name,
            "label": label_for(path.name),
        }
        meta = run_meta_for(path.name)
        if meta:
            entry["meta"] = meta
        reports.append(entry)
    return reports


def write_manifest(reports: list[dict[str, str]]) -> Path:
    out = ROOT / "reports.json"
    out.write_text(json.dumps({"reports": reports}, indent=2) + "\n", encoding="utf-8")
    return out


def main() -> None:
    if not ROOT.is_dir():
        raise SystemExit(f"Missing public directory: {ROOT}")
    reports = collect_reports()
    out = write_manifest(reports)
    print(f"Wrote {out} ({len(reports)} reports)")
    for r in reports:
        print(f"  {r['file']} → {r['label']}")


if __name__ == "__main__":
    main()
