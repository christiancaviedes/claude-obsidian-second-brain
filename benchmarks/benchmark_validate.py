#!/usr/bin/env python3
"""Benchmark the deterministic, offline export-validation path."""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from main import _validate_input


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("examples/sample-export.json"))
    parser.add_argument("--runs", type=int, default=100)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    timings = []
    for _ in range(args.runs):
        started = time.perf_counter()
        with contextlib.redirect_stdout(io.StringIO()):
            is_valid = _validate_input(args.input)
        if not is_valid:
            raise SystemExit("validation failed")
        timings.append((time.perf_counter() - started) * 1000)

    result = {
        "benchmark": "offline-export-validation",
        "dataset": str(args.input),
        "runs": args.runs,
        "median_ms": round(statistics.median(timings), 3),
        "p95_ms": round(sorted(timings)[max(0, int(args.runs * 0.95) - 1)], 3),
        "api_calls": 0,
        "estimated_api_cost_usd": 0,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    payload = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
