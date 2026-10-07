"""Verify the published CPU evidence and functional source/data bindings.

Reads complete .gz records; performs no compilation, native execution or timing.
The frozen measurement sources and existing original-trace checker are unchanged.
"""
import argparse
import gzip
import hashlib
import json
import math
import statistics
from pathlib import Path

import check_native
import summarize_native

ROOT = Path(__file__).resolve().parents[1]


def digest(stream):
    value = hashlib.sha256()
    size = 0
    while chunk := stream.read(1024 * 1024):
        size += len(chunk)
        value.update(chunk)
    return value.hexdigest().upper(), size


def file_digest(path):
    with path.open("rb") as stream:
        return digest(stream)[0]


def rows(path):
    opener = gzip.open if path.suffix == ".gz" else Path.open
    with opener(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            assert len(line) <= 4 * 1024**2
            yield json.loads(line)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("campaign", type=Path, nargs="?", default=ROOT / "results/native-campaign")
    args = ap.parse_args()
    out = args.campaign.resolve()
    env = json.loads((out / "environment.json").read_text(encoding="utf-8"))
    for name, expected in env["source_sha256"].items():
        assert file_digest(ROOT / "native" / name) == expected, (name, "measured source binding")
    assert file_digest(ROOT / "inputs/traces.jsonl") == env["original_input_sha256"]
    assert file_digest(ROOT / "results/campaign/certificates.jsonl") == env["original_certificate_sha256"]
    for name, info in env["compressed_records"].items():
        path = out / name
        assert file_digest(path) == info["gzip_sha256"] and path.stat().st_size == info["gzip_bytes"]
        with gzip.open(path, "rb") as stream:
            decoded, size = digest(stream)
        assert decoded == info["decoded_sha256"] and size == info["raw_bytes"], (name, "lossless full record")
    traces = {r["id"]: r["trace"] for r in rows(ROOT / "inputs/traces.jsonl")}
    expected_values, counts = {}, {}
    n = 0
    for record in rows(out / "conformance.jsonl"):
        case = record["id"]
        if record["trace"] is not None:
            traces[case] = record["trace"]
        verdict = check_native.checker.check(traces[case], record["certificate"])
        assert verdict["accepted"], (case, verdict)
        expected = check_native.required_values(traces[case])
        assert record["expected"] == expected and record["passed"]
        expected_values[case] = expected
        for actual in record["actual"]:
            assert actual["values"] == expected
            counts[case, actual["mode"]] = actual
        n += 1
    assert n == 207
    protocol = json.loads((ROOT / "native/protocol.json").read_text(encoding="utf-8"))
    order = [(case, pair, mode) for case in protocol["panel"] for pair in range(protocol["pairs_per_case"])
             for mode in (("baseline", "certified") if pair % 2 == 0 else ("certified", "baseline"))]
    samples = {}
    for index, record in enumerate(rows(out / "samples.jsonl.gz")):
        key = record["id"], record["pair"], record["mode"]
        assert index < len(order) and key == order[index] and key not in samples
        assert record["correct"] and record["repeats"] == protocol["trace_replays_per_block"]
        assert record["actual_values"] == expected_values[key[0]], (key, "actual native values")
        previous = counts[key[0], key[2]]
        for actual, observed in (("actual_loads", "loads"), ("actual_bytes", "bytes"),
                                 ("publications", "publications"), ("descriptor_copies", "descriptor_copies"), ("sink", "sink")):
            assert record[actual] == previous[observed], (key, actual)
        assert record["native_execution_ns"] > 0 and record["frequency"] > 0
        samples[key] = record
    assert len(samples) == len(order) == 308
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["raw_samples"] == 308 and summary["actual_outputs_equal"] and summary["no_samples_discarded"]
    native_slower = complete_slower = 0
    for case in summary["cases"]:
        name = case["id"]
        paired = []
        for pair in range(11):
            b, c = (samples[name, pair, mode] for mode in ("baseline", "certified"))
            assert b["actual_values"] == c["actual_values"]
            paired.append((summarize_native.phases(b), summarize_native.phases(c)))
        for field in paired[0][0]:
            ratios = [c[field] / b[field] if b[field] > 0 else None for b, c in paired]
            assert case[field]["paired_ratios"] == ratios
            finite = [r for r in ratios if r is not None]
            assert math.isclose(case[field]["baseline_median_ms"], statistics.median(b[field] for b, c in paired))
            assert math.isclose(case[field]["certified_median_ms"], statistics.median(c[field] for b, c in paired))
            if finite:
                assert math.isclose(case[field]["paired_ratio_median"], statistics.median(finite))
            assert case[field]["certified_slower_pairs"] == sum(c[field] > b[field] for b, c in paired)
        native_slower += case["native_execution_ms"]["certified_slower_pairs"]
        complete_slower += case["complete_from_decoded_trace_ms"]["certified_slower_pairs"]
    result = {"status": "PUBLISHED_NATIVE_EVIDENCE_PASSED", "source_bindings": len(env["source_sha256"]),
              "gzip_full_records_lossless": True, "original_checker_acceptances": n, "samples": len(samples), "pairs": 154,
              "actual_values_and_counts_equal": True, "paired_order_verified": True,
              "native_execution_slower_pairs": native_slower, "complete_path_slower_pairs": complete_slower,
              "no_compilation_execution_or_timing": True}
    (out / "checker-summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
