"""Portable independent finite closure/cut oracle; no saved data or native code."""
import copy
import importlib.util
import itertools
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "src" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


producer, checker = load("producer"), load("checker")


def trace_for(lives, needs, weights=(1, 3), setup=1, rho=0, recycled=False):
    pages = [{"slot": 0 if recycled else p, "generation": p + 1,
              "content": 100 + p, "format": "int8", "kv_group": 0,
              "first": a, "last": b, "base": 0, "length": 2,
              "weight": weights[p]} for p, (a, b) in enumerate(lives)]
    steps = []
    for t, need in enumerate(needs):
        active = [p for p, (a, b) in enumerate(lives) if a <= t <= b]
        bindings = [[0, p, p, 100 + p, "int8", 0] for p in active]
        # Logical aliases, duplicate roots/atoms and a cycle; node 2 is typed
        # but unreachable, so its atoms do not become requirements.
        bindings += [[0, 10 + p, p, 100 + p, "int8", 0] for p in active]
        atoms = [[0, p, 0, 1] for p in sorted(need)]
        steps.append({"frontier": 1, "bindings": bindings,
                      "nodes": [{"children": [1], "atoms": atoms},
                                {"children": [0], "atoms": [[0, 10 + p, 0, 1] for p in sorted(need)]},
                                {"children": [], "atoms": [[0, p, 0, 2] for p in active]}],
                      "roots": [0, 0]})
    return {"pages": pages, "steps": steps, "setup": setup, "visit_weight": rho,
            "page_size": 2, "address_bits": 16, "heads": 1}


def requirements_reference(trace):
    result = []
    for step in trace["steps"]:
        nodes = step["nodes"]
        closure = [[i == j or j in nodes[i]["children"] for j in range(len(nodes))]
                   for i in range(len(nodes))]
        for pivot in range(len(nodes)):
            for i in range(len(nodes)):
                for j in range(len(nodes)):
                    closure[i][j] |= closure[i][pivot] and closure[pivot][j]
        need = set()
        for j, node in enumerate(nodes):
            if any(closure[r][j] for r in step["roots"]):
                for head, logical, lo, hi in node["atoms"]:
                    if lo < hi:
                        matches = [b[2] for b in step["bindings"] if b[:2] == [head, logical]]
                        if len(matches) != 1:
                            raise AssertionError("test binding")
                        need.add(matches[0])
        result.append(need)
    return result


def reference(trace, mode="fast"):
    required = requirements_reference(trace)
    pages = trace["pages"]
    def partitions(length):
        for flags in itertools.product((0, 1), repeat=length - 1):
            ends = [t for t, flag in enumerate(flags) if flag] + [length - 1]
            starts = [0] + [t + 1 for t in ends[:-1]]
            intervals = list(zip(starts, ends))
            epochs = []
            for s, t in intervals:
                selected = {p for q in range(s, t + 1) for p in required[q]}
                if any((mode != "no_birth" and pages[p]["first"] > s) or
                       (mode != "no_death" and pages[p]["last"] < t) for p in selected):
                    break
                weight = sum(pages[p]["weight"] for p in selected)
                cost = trace["setup"] + (1 + trace["visit_weight"] * (t - s + 1)) * weight
                descriptors = [[p, pages[p]["slot"], pages[p]["generation"], pages[p]["content"],
                                pages[p]["format"], pages[p]["kv_group"]] for p in sorted(selected)]
                epochs.append({"start": s, "end": t, "pages": descriptors, "cost": cost})
            else:
                yield sum(e["cost"] for e in epochs), tuple(reversed(starts)), epochs
    best = [min(partitions(length), key=lambda x: (x[0], x[1]))
            for length in range(1, len(required) + 1)]
    return {"epochs": best[-1][2], "potentials": [0] + [x[0] for x in best],
            "frontiers": [s["frontier"] for s in trace["steps"]], "total_cost": best[-1][0]}


def cases():
    for lives, recycled in ((((0, 2), (0, 2)), False),
                            (((0, 1), (0, 2)), False),
                            (((0, 2), (1, 2)), False),
                            (((0, 0), (1, 2)), True)):
        options = [[set(p for p, (a, b) in enumerate(lives) if flag[p] and a <= t <= b)
                    for flag in itertools.product((0, 1), repeat=2)] for t in range(3)]
        options = [list({tuple(sorted(s)) for s in choices}) for choices in options]
        for needs in itertools.product(*options):
            for setup, rho in ((0, 0), (2, 0), (1, 3)):
                yield trace_for(lives, needs, setup=setup, rho=rho, recycled=recycled)


class RequirementsRegression(unittest.TestCase):
    def test_literal_oracle_and_canonical_ids(self):
        for trace in cases():
            self.assertEqual(producer.requirements(trace), requirements_reference(trace))
            for mode in ("fast", "direct", "no_birth", "no_death"):
                result = producer.solve(trace, mode=mode)
                self.assertEqual(result["certificate"], reference(trace, mode))
                if mode in ("fast", "direct"):
                    verdict = checker.check(trace, result["certificate"])
                    self.assertTrue(verdict["accepted"], verdict)
                    self.assertEqual(verdict["span_obligations"], 6)
                    self.assertTrue(checker.check(trace, result["certificate"], optimal=False)["accepted"])

    def test_public_certificate_and_fresh_mutable_calls(self):
        trace = trace_for(((0, 2), (0, 2)), ({0}, {1}, {1}))
        original = copy.deepcopy(trace)
        expected = reference(trace)
        self.assertEqual(producer.solve(trace)["certificate"], expected)
        intervals = [[e["start"], e["end"]] for e in expected["epochs"]]
        potentials = expected["potentials"]
        standalone = producer.make_certificate(trace, intervals, potentials)
        self.assertEqual(standalone, expected)
        self.assertIs(standalone["potentials"], potentials)
        self.assertEqual(trace, original)
        # Modify bindings and metadata BETWEEN calls; no acceptance/cache survives.
        for step in trace["steps"]:
            for binding in step["bindings"]:
                binding[2] = 1 - binding[2]
                binding[3] = trace["pages"][binding[2]]["content"]
        trace["pages"][0]["weight"] = 7
        trace["setup"] = 5
        self.assertEqual(producer.solve(trace)["certificate"], reference(trace))
        self.assertEqual(producer.make_certificate(trace, intervals, potentials),
                         producer.make_certificate(copy.deepcopy(trace), intervals, potentials))
        for kind in ("fresh", "greedy", "periodic", "single"):
            self.assertEqual(producer.baseline(trace, kind), producer.baseline(copy.deepcopy(trace), kind))

    def test_unchanged_checker_rejection_boundaries(self):
        trace = trace_for(((0, 0), (1, 2)), ({0}, {1}, {1}), recycled=True)
        cert = producer.solve(trace)["certificate"]
        for field, value, code in (("frontiers", [0, 1, 1], "causal_frontier"),
                                   ("total_cost", cert["total_cost"] + 1, "total_cost"),
                                   ("potentials", [0, 0, 0, 0], "primal_dual_gap")):
            bad = copy.deepcopy(cert)
            bad[field] = value
            self.assertEqual(checker.check(trace, bad)["code"], code)
        bad = copy.deepcopy(cert)
        bad["epochs"][0]["pages"][0][2] += 1
        self.assertEqual(checker.check(trace, bad)["code"], "descriptor_binding")
        bad = copy.deepcopy(trace)
        bad["pages"][1]["generation"] = 1
        self.assertEqual(checker.check(bad, cert)["code"], "generation_order")
        bad["setup"] = True
        self.assertEqual(checker.check(bad, cert)["witness"], "setup")


if __name__ == "__main__":
    unittest.main()
