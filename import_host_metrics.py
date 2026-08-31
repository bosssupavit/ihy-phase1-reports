#!/usr/bin/env python3
"""Convert CSV CPU/RAM samples into host_metrics.json for a run."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def load_csv(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            t = row.get("t") or row.get("time") or row.get("timestamp")
            cpu = row.get("cpu") or row.get("cpu_percent") or row.get("CPU")
            ram = row.get("ram") or row.get("memory") or row.get("RAM")
            if not t:
                continue
            sample: dict = {"t": t}
            if cpu not in (None, ""):
                sample["cpu"] = float(cpu)
            if ram not in (None, ""):
                sample["ram"] = float(ram)
            if len(sample) > 1:
                rows.append(sample)
    return rows


def summarize(samples: list[dict]) -> dict:
    cpus = [s["cpu"] for s in samples if "cpu" in s]
    rams = [s["ram"] for s in samples if "ram" in s]
    out: dict = {}
    if cpus:
        out["cpu_avg"] = sum(cpus) / len(cpus)
        out["cpu_max"] = max(cpus)
    if rams:
        out["ram_avg"] = sum(rams) / len(rams)
        out["ram_max"] = max(rams)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="CSV → host_metrics.json")
    parser.add_argument("csv", type=Path, help="CSV with t/time, cpu, ram columns")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output JSON path (default: same dir as CSV)",
    )
    parser.add_argument("--host", default="")
    parser.add_argument("--cpu-unit", default="percent")
    parser.add_argument("--ram-unit", default="MiB")
    args = parser.parse_args()

    samples = load_csv(args.csv)
    if not samples:
        raise SystemExit("No samples found — CSV needs t/time + cpu and/or ram columns")

    out = args.output or args.csv.with_name("host_metrics.json")
    payload = {
        "host": args.host or None,
        "cpu_unit": args.cpu_unit,
        "ram_unit": args.ram_unit,
        "summary": summarize(samples),
        "samples": samples,
    }
    if not payload["host"]:
        del payload["host"]
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out} ({len(samples)} samples)")


if __name__ == "__main__":
    main()
