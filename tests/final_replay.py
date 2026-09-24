#!/usr/bin/env python3
"""Budget-closed replay of the final producer/checker source.

The project had 997 counted obligations left after the retained campaign and the
first clean contract run. The final closeout spends exactly 750 here and 247 in
a clean rerun of contracts.py. This replay does not regenerate the 400 mutation
campaign; it checks every retained positive in safety mode, all 48 tiny cases in
strict mode, and freshly regenerates two certificates with the final producer.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import resource
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CAP = 750


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists() and any(args.out.iterdir()):
        raise SystemExit("output must be new or empty")
    args.out.mkdir(parents=True, exist_ok=True)

    resource.setrlimit(resource.RLIMIT_AS, (2500 * 1024**2, 2500 * 1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (90, 90))
    if hasattr(os, "sched_setaffinity"):
        os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})

    checker = load_module("final_checker", ROOT / "src" / "checker.py")
    producer = load_module("final_producer", ROOT / "src" / "producer.py")
    input_rows = read_jsonl(ROOT / "inputs" / "traces.jsonl")
    certificate_rows = read_jsonl(ROOT / "results" / "campaign" / "certificates.jsonl")
    positive_rows = read_jsonl(ROOT / "results" / "campaign" / "positive.jsonl")

    if len(input_rows) != 200 or len(certificate_rows) != 200 or len(positive_rows) != 200:
        raise AssertionError("expected exactly 200 retained positive records")
    traces = {row["id"]: row["trace"] for row in input_rows}
    certificates = {row["id"]: row["certificate"] for row in certificate_rows}
    positives = {row["id"]: row for row in positive_rows}
    ordered_ids = [row["id"] for row in input_rows]
    if set(traces) != set(certificates) or set(traces) != set(positives):
        raise AssertionError("positive trace/certificate/result identifiers differ")

    tiny = ordered_ids[:48]
    fresh = ordered_ids[:2]
    strict_intervals = sum(len(traces[key]["steps"]) * (len(traces[key]["steps"]) + 1) // 2 for key in tiny)
    fresh_intervals = sum(len(traces[key]["steps"]) * (len(traces[key]["steps"]) + 1) // 2 for key in fresh)
    fresh_queries = sum(len(traces[key]["steps"]) for key in fresh)
    expected = 200 + 48 + strict_intervals + len(fresh) + fresh_intervals + fresh_queries
    if (strict_intervals, fresh_intervals, fresh_queries, expected) != (482, 12, 6, CAP):
        raise AssertionError((strict_intervals, fresh_intervals, fresh_queries, expected))

    started_cpu = time.process_time()
    started_wall = time.monotonic()
    obligations = 0
    events: list[dict[str, Any]] = []

    def charge(amount: int) -> None:
        nonlocal obligations
        if amount < 0 or obligations + amount > CAP:
            raise AssertionError("final replay obligation cap")
        obligations += amount

    # Every retained positive is parsed and replayed by the final checker source.
    # Safety-only mode intentionally avoids claiming a fresh all-case optimum run.
    for key in ordered_ids:
        answer = checker.check(traces[key], certificates[key], optimal=False)
        charge(answer["certificate_obligations"] + answer["span_obligations"])
        if not answer["accepted"]:
            raise AssertionError((key, answer))
        if answer["total_cost"] != positives[key]["opt"]:
            raise AssertionError((key, answer["total_cost"], positives[key]["opt"]))
        events.append({"phase": "all-positive-safety", "id": key, "result": answer})

    # The complete tiny set receives strict direct-interval and dual checks.
    for key in tiny:
        answer = checker.check(traces[key], certificates[key], optimal=True)
        charge(answer["certificate_obligations"] + answer["span_obligations"])
        if not answer["accepted"] or answer["total_cost"] != positives[key]["opt"]:
            raise AssertionError((key, answer, positives[key]["opt"]))
        events.append({"phase": "tiny-strict", "id": key, "result": answer})

    # Two representative three-step certificates are regenerated from final
    # producer source, compared structurally with the retained certificate, and
    # then strictly checked by the separately loaded final checker source.
    for key in fresh:
        trace = traces[key]
        generated = producer.solve(trace)
        charge(len(trace["steps"]))  # one producer minimum query per prefix
        if generated["certificate"] != certificates[key]:
            raise AssertionError(f"fresh producer mismatch: {key}")
        answer = checker.check(trace, generated["certificate"], optimal=True)
        charge(answer["certificate_obligations"] + answer["span_obligations"])
        if not answer["accepted"]:
            raise AssertionError((key, answer))
        events.append({
            "phase": "fresh-producer-strict",
            "id": key,
            "producer_metrics": generated["producer_metrics"],
            "result": answer,
        })

    if obligations != CAP:
        raise AssertionError((obligations, CAP))

    with (args.out / "replay.jsonl").open("w", encoding="utf-8") as target:
        for row in events:
            target.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")

    usage = resource.getrusage(resource.RUSAGE_SELF)
    summary = {
        "status": "final_source_replay_passed",
        "all_positive_safety_replays": 200,
        "tiny_strict_replays": 48,
        "fresh_producer_cases": 2,
        "checker_certificate_replays": 250,
        "checker_interval_obligations": strict_intervals + fresh_intervals,
        "producer_minimum_queries": fresh_queries,
        "events": len(events),
        "obligations": obligations,
        "cpu_self_s": time.process_time() - started_cpu,
        "wall_s": time.monotonic() - started_wall,
        "peak_self_rss_kib": usage.ru_maxrss,
        "parallel_children_max": 0,
        "worker_cpu_affinity_count": 1,
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
