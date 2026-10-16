"""Explicit scientific evidence gates; independent of Python optimization.

These are data checks, not assertions about a trusted internal invariant.
Historical measured sources and records are not rewritten by this module.
"""
import json
import math


def require(condition, reason='evidence check failed'):
    if not condition:
        raise AssertionError(reason)


def same(actual, expected):
    """JSON structural equality without Python's False == 0 / True == 1."""
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(same(actual[k], v) for k, v in expected.items())
    if isinstance(expected, (list, tuple)):
        return len(actual) == len(expected) and all(same(a, b) for a, b in zip(actual, expected))
    return actual == expected


def object_fields(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, ('duplicate evidence key', key))
        result[key] = value
    return result


def loads(text):
    def nonfinite(value):
        raise AssertionError(('nonfinite evidence number', value))
    def finite_float(value):
        number = float(value)
        require(math.isfinite(number), ('nonfinite evidence number', value))
        return number
    return json.loads(text, object_pairs_hook=object_fields,
                      parse_constant=nonfinite, parse_float=finite_float)
