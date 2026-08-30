#!/usr/bin/env python3
"""Build public/reports.json and sync sanitized run JSON into public/data/."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent / "public"
DATA_ROOT = ROOT / "data"
RUNS_ROOT = Path(__file__).resolve().parent.parent
SKIP = {"index.html"}
LABEL_OVERRIDES = {
    "getme": "Get Me",
    "text_to_sign": "Text to Sign",
}
SECRET_HEADER_KEYS = {"authorization", "cookie", "set-cookie", "x-api-key"}
BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.I)


def label_for(name: str) -> str:
    stem = Path(name).stem
    stem = re.sub(r"^phase\d+_", "", stem)
    if stem in LABEL_OVERRIDES:
        return LABEL_OVERRIDES[stem]
    parts = [p for p in stem.split("_") if p]
    if not parts:
        return name
    return " ".join(p.upper() if p.lower() == "id" else p.capitalize() for p in parts)


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


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if key.lower() in SECRET_HEADER_KEYS:
                out[key] = "[redacted]"
            elif key.lower() == "headers" and isinstance(item, dict):
                out[key] = {
                    hk: (
                        "[redacted]"
                        if hk.lower() in SECRET_HEADER_KEYS
                        else sanitize(hv)
                    )
                    for hk, hv in item.items()
                }
            else:
                out[key] = sanitize(item)
        return out
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, str):
        return BEARER_RE.sub("Bearer [redacted]", value)
    return value


def metric_values(metrics: dict[str, Any], name: str) -> dict[str, Any] | None:
    raw = metrics.get(name)
    if not isinstance(raw, dict):
        return None
    values = raw.get("values")
    return values if isinstance(values, dict) else raw


def pick_number(values: dict[str, Any] | None, *keys: str) -> float | int | None:
    if not values:
        return None
    for key in keys:
        if key in values and isinstance(values[key], (int, float)):
            return values[key]
    return None


def build_highlights(handle: dict[str, Any] | None) -> dict[str, Any]:
    if not handle:
        return {}
    metrics = handle.get("metrics")
    if not isinstance(metrics, dict):
        return {}

    reqs = metric_values(metrics, "http_reqs")
    failed = metric_values(metrics, "http_req_failed")
    checks = metric_values(metrics, "checks")
    duration = metric_values(metrics, "http_req_duration")
    vus_max = metric_values(metrics, "vus_max")

    highlights: dict[str, Any] = {}
    count = pick_number(reqs, "count")
    rate = pick_number(reqs, "rate")
    fail_rate = pick_number(failed, "rate", "value")
    check_rate = pick_number(checks, "rate", "value")
    p95 = pick_number(duration, "p(95)")
    avg = pick_number(duration, "avg")
    vus = pick_number(vus_max, "value", "max")

    if count is not None:
        highlights["http_reqs"] = count
    if rate is not None:
        highlights["http_req_rate"] = rate
    if fail_rate is not None:
        highlights["http_fail_rate"] = fail_rate
    if check_rate is not None:
        highlights["checks_pass_rate"] = check_rate
    if p95 is not None:
        highlights["duration_p95_ms"] = p95
    if avg is not None:
        highlights["duration_avg_ms"] = avg
    if vus is not None:
        highlights["vus_max"] = vus
    return highlights


def sync_run_json(run_id: str, report_stem: str) -> dict[str, Any]:
    """Copy sanitized run JSON into public/data/<run_id>/ and return sidecar info."""
    src_dir = RUNS_ROOT / run_id
    dest_dir = DATA_ROOT / run_id
    dest_dir.mkdir(parents=True, exist_ok=True)

    files: dict[str, str] = {}
    clock: dict[str, Any] | None = None
    handle: dict[str, Any] | None = None

    clock_src = src_dir / "run_clock.json"
    if clock_src.is_file():
        clock = json.loads(clock_src.read_text(encoding="utf-8"))
        dest = dest_dir / "run_clock.json"
        dest.write_text(json.dumps(clock, indent=2) + "\n", encoding="utf-8")
        files["run_clock"] = f"data/{run_id}/run_clock.json"

    handle_src = src_dir / "handle_summary.json"
    if handle_src.is_file():
        handle = json.loads(handle_src.read_text(encoding="utf-8"))
        cleaned = sanitize(handle)
        dest = dest_dir / "handle_summary.json"
        dest.write_text(json.dumps(cleaned, indent=2) + "\n", encoding="utf-8")
        files["handle_summary"] = f"data/{run_id}/handle_summary.json"

    summary_name = f"summary_{report_stem}.json"
    summary_src = src_dir / summary_name
    if summary_src.is_file():
        summary = sanitize(json.loads(summary_src.read_text(encoding="utf-8")))
        dest = dest_dir / summary_name
        dest.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        files["summary"] = f"data/{run_id}/{summary_name}"

    info: dict[str, Any] = {"files": files}
    if isinstance(clock, dict):
        info["clock"] = {
            k: clock[k]
            for k in ("started_at", "ended_at", "elapsed", "duration_ms")
            if k in clock
        }
    highlights = build_highlights(handle)
    if highlights:
        info["highlights"] = highlights
    return info


def collect_reports() -> list[dict[str, Any]]:
    if DATA_ROOT.exists():
        shutil.rmtree(DATA_ROOT)
    DATA_ROOT.mkdir(parents=True, exist_ok=True)

    reports: list[dict[str, Any]] = []
    for path in sorted(ROOT.glob("*.html")):
        if path.name in SKIP:
            continue
        entry: dict[str, Any] = {
            "file": path.name,
            "label": label_for(path.name),
        }
        meta = run_meta_for(path.name)
        if meta:
            entry["meta"] = meta
            entry.update(sync_run_json(meta, path.stem))
        reports.append(entry)
    return reports


def write_manifest(reports: list[dict[str, Any]]) -> Path:
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
        extras = []
        if r.get("clock"):
            extras.append(f"elapsed={r['clock'].get('elapsed')}")
        if r.get("files"):
            extras.append(f"json={len(r['files'])}")
        suffix = f" ({', '.join(extras)})" if extras else ""
        print(f"  {r['file']} → {r['label']}{suffix}")


if __name__ == "__main__":
    main()
