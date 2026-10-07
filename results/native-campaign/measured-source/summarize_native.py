"""Arithmetic on reserved-slot raw samples only; no allocator/trace execution."""
import argparse
import csv
import json
import statistics
from pathlib import Path


def phases(row):
    seconds = 1000 / row["frequency"]
    n = row["repeats"]
    return {
        "setup_ms": row["setup_ticks"] * seconds / n,
        "checking_ms": row["checking_ticks"] * seconds / n,
        "allocation_ms": row["allocation_ticks"] * seconds,
        "adapter_ms": row["adapter_ticks"] * seconds,
        "native_execution_ms": row["native_execution_ns"] / 1e6 / n,
        "host_batch_envelope_ms": row["execution_ticks"] * seconds / n,
        "complete_from_decoded_trace_ms": row["complete_from_decoded_trace_ticks"] * seconds,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out", type=Path)
    args = ap.parse_args()
    out = args.out.resolve()
    assert out.is_dir(), "existing reserved-slot evidence directory required"
    protocol = json.loads((Path(__file__).parent / "protocol.json").read_text(encoding="utf-8"))
    assert (out / "samples.jsonl").stat().st_size <= 128 * 1024**2
    samples = {}
    with (out / "samples.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            assert len(line) <= 4 * 1024**2
            row = json.loads(line)
            key = row["id"], row["pair"], row["mode"]
            assert key not in samples and row["correct"]
            assert row["id"] in protocol["panel"] and row["mode"] in ("baseline", "certified")
            assert row["repeats"] == protocol["trace_replays_per_block"]
            assert 0 <= row["pair"] < protocol["pairs_per_case"]
            assert row["native_execution_ns"] > 0 and row["frequency"] > 0
            samples[key] = row
    assert len(samples) == len(protocol["panel"]) * protocol["pairs_per_case"] * 2
    table = []
    details = []
    for case in protocol["panel"]:
        paired = []
        for pair in range(protocol["pairs_per_case"]):
            b, c = (samples[case, pair, mode] for mode in ("baseline", "certified"))
            assert b["actual_values"] == c["actual_values"], (case, pair, "unequal native result")
            paired.append((phases(b), phases(c)))
        per_case = {"id": case, "pairs": len(paired), "all_actual_values_equal": True}
        for field in paired[0][0]:
            ratios = [c[field] / b[field] if b[field] > 0 else None for b, c in paired]
            finite = [r for r in ratios if r is not None]
            gains = [100 * (1 - ratio) for ratio in finite]
            data = {
                "baseline_median_ms": statistics.median(b[field] for b, c in paired),
                "certified_median_ms": statistics.median(c[field] for b, c in paired),
                "paired_ratio_median": statistics.median(finite) if finite else None,
                "paired_ratio_min": min(finite) if finite else None, "paired_ratio_max": max(finite) if finite else None,
                "paired_gain_percent_median": statistics.median(gains) if gains else None,
                "certified_slower_pairs": sum(c[field] > b[field] for b, c in paired),
                "below_resolution_baseline_pairs": sum(r is None for r in ratios),
                "paired_ratios": ratios,
            }
            per_case[field] = data
            table.append({"id": case, "phase": field, "pairs": len(paired), **{k: v for k, v in data.items() if k != "paired_ratios"}})
        first_b = samples[case, 0, "baseline"]
        first_c = samples[case, 0, "certified"]
        per_case["counts"] = {mode: {k: row[k] for k in ("actual_loads", "actual_bytes", "publications", "descriptor_copies")} for mode, row in (("baseline", first_b), ("certified", first_c))}
        details.append(per_case)
    summary = {"status": "MEASURED_PAIRED_NATIVE_CPU", "raw_samples": len(samples), "panel_cases": len(details),
               "pairs_per_case": protocol["pairs_per_case"], "actual_outputs_equal": True, "cases": details,
               "limitations": protocol["limits"], "no_samples_discarded": True}
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    with (out / "phases.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(table[0]))
        writer.writeheader()
        writer.writerows(table)
    print(json.dumps({k: v for k, v in summary.items() if k != "cases"}))


if __name__ == "__main__":
    main()
