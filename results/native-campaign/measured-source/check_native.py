"""Read-only independent audit of real C++ results; never runs a trace simulator.

Checks original certificates with the existing source-separated checker, and
compares recorded C++ buffer values/addresses/transitions to the trace semantics.
The only new output is independent-summary.json in the private experiment folder.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import checker


def records(path):
    assert path.stat().st_size <= 256 * 1024**2, "evidence file bound"
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            assert len(line) <= 4 * 1024**2, "record size bound"
            yield json.loads(line)


def value(page, lane):
    mask = 65535 if page["format"] == "fp16" else 255
    return (page["content"] * 131 + page["generation"] * 17 + page["kv_group"] * 7 + lane * 29) & mask


def required_values(trace):
    out = []
    for step in trace["steps"]:
        # Separate fixed-point reachability, then sorted unique atom lanes.
        live = set(step["roots"])
        while True:
            extended = live | {child for j in live for child in step["nodes"][j]["children"]}
            if extended == live:
                break
            live = extended
        mapping = {(b[0], b[1]): b[2] for b in step["bindings"]}
        lanes = {(mapping[h, l], i) for j in live for h, l, lo, hi in step["nodes"][j]["atoms"] for i in range(lo, hi)}
        out.append([value(trace["pages"][p], i) for p, i in sorted(lanes)])
    return out


def expected_events(trace, certificate, mode):
    required, _ = checker.normalize(trace)
    epochs = certificate["epochs"] if mode == "certified" else [
        {"start": t, "end": t, "pages": [[p] for p in sorted(need)]} for t, need in enumerate(required)]
    pages = trace["pages"]
    for epoch in epochs:
        for t in range(epoch["start"], epoch["end"] + 1):
            for p, meta in enumerate(pages):
                if meta["last"] == t - 1:
                    yield {"kind": "retire", "step": t, "page": p, "slot": meta["slot"], "generation": meta["generation"]}
            for p, meta in enumerate(pages):
                if meta["first"] == t:
                    yield {"kind": "activate", "step": t, "page": p, "slot": meta["slot"], "generation": meta["generation"], "offset": meta["slot"] * 2 * trace["page_size"], "value": meta["content"]}
            if t == epoch["start"]:
                yield {"kind": "publish", "step": t, "start": epoch["start"], "end": epoch["end"], "value": len(epoch["pages"])}
            for desc in epoch["pages"]:
                p = desc[0]
                meta = pages[p]
                width = 2 if meta["format"] == "fp16" else 1
                cap = min(meta["length"], max(0, trace["steps"][t]["frontier"] - meta["base"] + 1))
                yield {"kind": "consult", "step": t, "page": p, "slot": meta["slot"], "generation": meta["generation"], "start": epoch["start"], "end": epoch["end"], "value": cap}
                for i in range(cap):
                    yield {"kind": "load", "step": t, "page": p, "slot": meta["slot"], "generation": meta["generation"], "lane": i, "width": width, "offset": meta["slot"] * 2 * trace["page_size"] + i * width, "value": value(meta, i), "start": epoch["start"], "end": epoch["end"]}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out", type=Path)
    args = ap.parse_args()
    out = args.out.resolve()
    assert out.is_dir(), "existing native evidence directory required"
    traces = {r["id"]: r["trace"] for r in records(ROOT / "inputs/traces.jsonl")}
    certs = {}
    cases = 0
    for row in records(out / "conformance.jsonl"):
        if row["trace"] is not None:
            traces[row["id"]] = row["trace"]
        trace = traces[row["id"]]
        verdict = checker.check(trace, row["certificate"])
        assert verdict["accepted"], (row["id"], verdict)
        certs[row["id"]] = row["certificate"]
        expected = required_values(trace)
        assert row["expected"] == expected
        assert len(row["actual"]) == 2 and row["passed"]
        for actual in row["actual"]:
            assert actual["values"] == expected, (row["id"], actual["mode"])
            events = expected_events(trace, row["certificate"], actual["mode"])
            loads = count = copied = byte_count = 0
            sink = 0
            for event in events:
                if event["kind"] == "load":
                    loads += 1
                    byte_count += event["width"]
                    sink = (sink * 1099511628211 + event["value"] + 1) & ((1 << 64) - 1)
                if event["kind"] == "publish":
                    count += 1
                    copied += event["value"]
            assert (actual["loads"], actual["bytes"], actual["publications"], actual["descriptor_copies"], actual["sink"]) == (loads, byte_count, count, copied, sink)
        cases += 1
    assert cases == 207
    group = None
    iterator = None
    base_address = None
    obligations = groups = 0
    for row in records(out / "observations.jsonl"):
        key = row["id"], row["mode"]
        if key != group:
            if iterator is not None:
                assert next(iterator, None) is None, (group, "missing events")
            group = key
            iterator = iter(expected_events(traces[key[0]], certs[key[0]], key[1]))
            base_address = None
            groups += 1
        expected = next(iterator, None)
        assert expected is not None, (key, "extra event")
        ev = row["ev"]
        assert all(ev[k] == v for k, v in expected.items()), (key, expected, ev)
        if ev["kind"] in ("activate", "load"):
            base = int(ev["address"], 16) - ev["offset"]
            assert base > 0
            if base_address is None:
                base_address = base
            assert base_address == base, (key, "physical arena mapping")
        obligations += 1
    assert next(iterator, None) is None and groups == 36
    summary = {"status": "INDEPENDENT_CHECKS_PASSED", "cases": cases, "original_checker_acceptances": cases,
               "native_observation_groups": groups, "native_event_obligations": obligations,
               "actual_values_equal": True, "performance_measurements_started": False}
    (out / "independent-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
