"""Owned bounded C-ABI regressions; no timers, network, or external targets.

Compile allocator.cpp first, then supply that owned DLL/.so with --library.
The arrays below are allocated here. Invalid controls reject metadata before
loads; they do not issue invalid pointers or execute exploit payloads.
"""
import argparse
import ctypes as C
import unittest
from pathlib import Path


class Page(C.Structure):
    _fields_ = [(s, C.c_int32) for s in
                ('slot', 'generation', 'content', 'group', 'first', 'last', 'base', 'length', 'width')]


class Epoch(C.Structure):
    _fields_ = [(s, C.c_int32) for s in ('start', 'end', 'offset', 'count')]


class Descriptor(C.Structure):
    _fields_ = [(s, C.c_int32) for s in
                ('page', 'slot', 'generation', 'content', 'width', 'group', 'offset', 'length', 'start', 'end')]


class Counts(C.Structure):
    _fields_ = [(s, C.c_int64) for s in ('loads', 'bytes', 'publications', 'copies')] + [('sink', C.c_uint64)]


def value(page, lane):
    return (131 * page.content + 17 * page.generation + 7 * page.group + 29 * lane) & ((1 << (8 * page.width)) - 1)


class Projection(unittest.TestCase):
    library = None

    def execute(self, pages, frontiers, B, masks, spans, *, missing_after_good=False, bad_zero_cap=False):
        P, T = len(pages), len(frontiers)
        self.assertLessEqual(T * P * B, 64 * 256 * 128)
        ps = (Page * P)(*pages)
        fs = (C.c_int32 * T)(*frontiers)
        ms = (C.c_uint8 * len(masks))(*masks)
        error = C.create_string_buffer(256)
        context = self.library.nb_create(B, 64, T, P, ps, fs, ms, error, len(error))
        self.assertTrue(context, error.value)
        try:
            descriptors, epochs = [], []
            for start, end, selected in spans:
                epochs.append(Epoch(start, end, len(descriptors), len(selected)))
                for p in selected:
                    m = pages[p]
                    descriptors.append(Descriptor(p, m.slot, m.generation, m.content, m.width,
                                                  m.group, m.slot * 2 * B, m.length, start, end))
            es = (Epoch * len(epochs))(*epochs)
            ds = (Descriptor * len(descriptors))(*descriptors) if descriptors else None
            output = (C.c_uint32 * len(masks))(*([0xDEADBEEF] * len(masks)))
            expected_loads = expected_bytes = sink = 0
            for start, end, selected in spans:
                for t in range(start, end + 1):
                    for p in selected:
                        m = pages[p]
                        cap = min(m.length, max(0, frontiers[t] - m.base + 1))
                        for lane in range(cap):
                            expected_loads += 1
                            expected_bytes += m.width
                            sink = (sink * 1099511628211 + value(m, lane) + 1) & ((1 << 64) - 1)
            # A second replay must not depend on scratch from the first.
            for replay in range(2):
                counts = Counts()
                status = self.library.nb_run(context, es, len(es), ds, len(descriptors),
                                             output, C.byref(counts), None, error, len(error))
                self.assertEqual(status, 0, error.value)
                self.assertEqual((counts.loads, counts.bytes, counts.publications, counts.copies, counts.sink),
                                 (expected_loads, expected_bytes, len(spans), len(descriptors), sink))
                for k, mandatory in enumerate(masks):
                    self.assertEqual(output[k], value(pages[(k // B) % P], k % B) if mandatory else 0xDEADBEEF)
                if replay == 0 and missing_after_good:
                    empty = (Epoch * 1)(Epoch(0, T - 1, 0, 0))
                    self.assertEqual(self.library.nb_run(context, empty, 1, None, 0, output,
                                                        C.byref(Counts()), None, error, len(error)), 1)
                    self.assertEqual(error.value, b'mandatory lane missing')
                if replay == 0 and bad_zero_cap:
                    bad = (Descriptor * len(descriptors))(*descriptors)
                    bad[0].generation += 1
                    self.assertEqual(self.library.nb_run(context, es, len(es), bad, len(bad), output,
                                                        C.byref(Counts()), None, error, len(error)), 1)
                    self.assertEqual(error.value, b'resident incarnation')
            self.assertEqual(self.library.nb_guards(context, error, len(error)), 0, error.value)
        finally:
            self.library.nb_destroy(context)

    def fixture(self, dense=False):
        pages = [Page(p, 1, 40 + p, p, 0, 3, 0, 4, 1 + p % 2) for p in range(3)]
        masks = [int(dense or k % 12 in (0, 7, 10)) for k in range(48)]
        return pages, [3] * 4, 4, masks, [(0, 3, [0, 1, 2])]

    def test_sparse_projection_keeps_extra_loads(self):
        self.execute(*self.fixture())

    def test_dense_projection(self):
        self.execute(*self.fixture(dense=True))

    def test_missing_lane_rejected_after_successful_replay(self):
        self.execute(*self.fixture(), missing_after_good=True)

    def test_empty_null_descriptor_one_publication(self):
        self.execute([Page(0, 1, 40, 0, 0, 3, 0, 4, 2)], [0] * 4, 4, [0] * 16, [(0, 3, [])])

    def test_recycled_slot_and_zero_caps(self):
        pages = [Page(0, 1, 41, 0, 0, 1, 1, 4, 2), Page(0, 2, 42, 0, 2, 3, 1, 4, 1)]
        masks = [int((k // 8, (k // 4) % 2) in ((1, 0), (3, 1))) for k in range(32)]
        self.execute(pages, [0, 4, 0, 4], 4, masks, [(0, 1, [0]), (2, 3, [1])])

    def test_zero_cap_still_checks_resident_generation(self):
        self.execute([Page(0, 1, 41, 0, 0, 1, 1, 4, 2)], [0, 4], 4,
                     [0] * 4 + [1] * 4, [(0, 1, [0])], bad_zero_cap=True)

    def test_native_dimension_bounds_dense_and_sparse(self):
        # Native configuration axes, not a claim that a serialized graph can
        # simultaneously saturate every separate graph/binding admission cap.
        T, P, B = 64, 256, 128
        pages = [Page(p, 1, 100 + p, p % 32, 0, T - 1, 0, B, 1 + p % 2) for p in range(P)]
        for dense in (False, True):
            masks = [int(dense or (k // B) % P == 0) for k in range(T * P * B)]
            self.execute(pages, [B - 1] * T, B, masks, [(0, T - 1, list(range(P)))])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--library', type=Path, required=True)
    ns, extra = ap.parse_known_args()
    path = ns.library.resolve(strict=True)
    lib = C.CDLL(str(path))
    lib.nb_create.argtypes = [C.c_int, C.c_int, C.c_int, C.c_int, C.POINTER(Page), C.POINTER(C.c_int32),
                             C.POINTER(C.c_uint8), C.c_char_p, C.c_int]
    lib.nb_create.restype = C.c_void_p
    lib.nb_run.argtypes = [C.c_void_p, C.POINTER(Epoch), C.c_int, C.POINTER(Descriptor), C.c_int,
                          C.POINTER(C.c_uint32), C.POINTER(Counts), C.c_void_p, C.c_char_p, C.c_int]
    lib.nb_run.restype = C.c_int
    lib.nb_guards.argtypes = [C.c_void_p, C.c_char_p, C.c_int]
    lib.nb_guards.restype = C.c_int
    lib.nb_destroy.argtypes = [C.c_void_p]
    lib.nb_destroy.restype = None
    assert (C.sizeof(Page), C.sizeof(Epoch), C.sizeof(Descriptor), C.sizeof(Counts)) == (36, 16, 40, 40)
    Projection.library = lib
    unittest.main(argv=['projection-regressions'] + extra)


if __name__ == '__main__':
    main()
