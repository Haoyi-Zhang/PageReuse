"""Bounded CUDA Driver API adapter for an owned sequential byte arena."""
import ctypes as c
import ctypes.util
import os
import sys
from pathlib import Path

SENTINEL = 0xDEADBEEF


class PageDevice:
    def __init__(self):
        if sys.byteorder != 'little' or c.sizeof(c.c_void_p) != 8:
            raise RuntimeError('This bounded adapter requires a little-endian 64-bit host')
        self.context, self.module, self.function = c.c_void_p(), c.c_void_p(), c.c_void_p()
        self.buffers = []
        library = 'nvcuda.dll' if os.name == 'nt' else ctypes.util.find_library('cuda')
        if not library:
            raise RuntimeError('CUDA driver is required; no CPU fallback')
        self.d = c.WinDLL(library) if os.name == 'nt' else c.CDLL(library)
        v, p = c.c_void_p, c.POINTER
        api = {
            'cuInit': [c.c_uint], 'cuDeviceGet': [p(c.c_int), c.c_int],
            'cuDriverGetVersion': [p(c.c_int)],
            'cuDeviceGetName': [c.c_char_p, c.c_int, c.c_int],
            'cuDeviceGetAttribute': [p(c.c_int), c.c_int, c.c_int],
            'cuCtxCreate_v2': [p(v), c.c_uint, c.c_int], 'cuCtxDestroy_v2': [v],
            'cuModuleLoadData': [p(v), v], 'cuModuleUnload': [v],
            'cuModuleGetFunction': [p(v), v, c.c_char_p],
            'cuMemAlloc_v2': [p(c.c_uint64), c.c_size_t], 'cuMemFree_v2': [c.c_uint64],
            'cuMemcpyHtoD_v2': [c.c_uint64, v, c.c_size_t],
            'cuMemcpyDtoH_v2': [v, c.c_uint64, c.c_size_t],
            'cuLaunchKernel': [v] + [c.c_uint] * 7 + [v, p(v), p(v)],
            'cuCtxSynchronize': []}
        for name, signature in api.items():
            fn = getattr(self.d, name)
            fn.argtypes, fn.restype = signature, c.c_int
        try:
            self.call('cuInit', 0)
            device, version, major, minor = (c.c_int() for _ in range(4))
            self.call('cuDeviceGet', c.byref(device), 0)
            self.call('cuDriverGetVersion', c.byref(version))
            name = c.create_string_buffer(256)
            self.call('cuDeviceGetName', name, len(name), device)
            self.call('cuDeviceGetAttribute', c.byref(major), 75, device)
            self.call('cuDeviceGetAttribute', c.byref(minor), 76, device)
            if (major.value, minor.value) < (6, 1):
                raise ValueError('PTX target requires compute capability 6.1 or later')
            self.info = dict(name=name.value.decode(), driver_api=version.value,
                             compute_major=major.value, compute_minor=minor.value)
            self.call('cuCtxCreate_v2', c.byref(self.context), 0, device)
            source = c.create_string_buffer(Path(__file__).with_name('page_loads.ptx').read_bytes())
            self.call('cuModuleLoadData', c.byref(self.module), source)
            self.call('cuModuleGetFunction', c.byref(self.function), self.module, b'page_loads')
            for size in (65536 + 64, 256 * 16, 256 * 24, (256 * 128 + 2) * 4):
                address = c.c_uint64()
                self.call('cuMemAlloc_v2', c.byref(address), size)
                self.buffers.append(address)
        except BaseException:
            self.close()
            raise

    def call(self, name, *args):
        code = getattr(self.d, name)(*args)
        if code:
            raise RuntimeError(f'{name}: CUDA error {code}')

    def upload(self, index, raw, offset=0):
        limits = (65600, 4096, 6144, 131080)
        if (type(index) is not int or not 0 <= index < 4 or
                not isinstance(raw, bytes) or type(offset) is not int or
                not 0 <= offset <= limits[index] - len(raw)):
            raise ValueError('bounded owned upload')
        if raw:
            data = c.create_string_buffer(raw)
            self.call('cuMemcpyHtoD_v2', self.buffers[index].value + offset, data, len(raw))

    def read(self, index, length):
        limits = (65600, 4096, 6144, 131080)
        if (type(index) is not int or not 0 <= index < 4 or type(length) is not int or
                not 0 <= length <= limits[index]):
            raise ValueError('bounded owned read')
        data = (c.c_uint8 * length)()
        self.call('cuMemcpyDtoH_v2', data, self.buffers[index], length)
        return bytes(data)

    def query(self, descriptors, B, frontier, arena_bytes):
        if (type(descriptors) is not list or not 0 <= len(descriptors) <= 256 or
                type(B) is not int or not 1 <= B <= 128 or
                type(frontier) is not int or not 0 <= frontier < 2**31 or
                type(arena_bytes) is not int or not 1 <= arena_bytes <= 65536):
            raise ValueError('bounded owned query')
        for d in descriptors:
            if (type(d) is not list or len(d) != 6 or any(type(x) is not int for x in d) or
                    not 0 <= d[0] < 256 or not 0 <= d[1] < 256 or
                    not 1 <= d[2] < 2**31 or d[3] not in (1, 2) or
                    not 1 <= d[4] <= B or not 0 <= d[5] < 2**31 or
                    d[1]*2*B+d[3]*d[4] > arena_bytes):
                raise ValueError('descriptor extent and types')
        if not self.context:
            raise RuntimeError('CUDA context is closed')
        n = len(descriptors) * B
        output = (c.c_uint32 * (n + 2))(*([SENTINEL] * (n + 2)))
        self.upload(3, bytes(output))
        if n:
            args = [c.c_uint64(self.buffers[0].value + 32), self.buffers[1], self.buffers[2],
                    c.c_uint64(self.buffers[3].value + 4), c.c_uint32(len(descriptors)),
                    c.c_uint32(B), c.c_uint32(frontier), c.c_uint32(arena_bytes)]
            pointers = (c.c_void_p * len(args))(*(c.cast(c.byref(a), c.c_void_p) for a in args))
            self.call('cuLaunchKernel', self.function, (n + 127)//128, 1, 1,
                      128, 1, 1, 0, None, pointers, None)
            self.call('cuCtxSynchronize')
        self.call('cuMemcpyDtoH_v2', output, self.buffers[3], c.sizeof(output))
        if output[0] != SENTINEL or output[-1] != SENTINEL:
            raise RuntimeError('device output canary')
        return list(output)[1:-1]

    def close(self):
        errors = []
        for address in self.buffers:
            try:
                self.call('cuMemFree_v2', address)
            except RuntimeError as exc:
                errors.append(str(exc))
        self.buffers.clear()
        for name, obj in (('cuModuleUnload', self.module), ('cuCtxDestroy_v2', self.context)):
            if obj:
                try:
                    self.call(name, obj)
                except RuntimeError as exc:
                    errors.append(str(exc))
                obj.value = None
        if errors:
            raise RuntimeError('; '.join(errors))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
