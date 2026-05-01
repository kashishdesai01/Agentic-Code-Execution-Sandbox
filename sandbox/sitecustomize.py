"""
Import whitelist enforcement for sandboxed Python execution.
Loaded automatically by the Python interpreter before any user code via sitecustomize.
"""
import builtins
import sys

ALLOWED_MODULES = frozenset({
    # User-facing allowed modules
    "math", "json", "re", "collections", "itertools",
    "datetime", "string", "random",
    # Python internals that must not be blocked
    "builtins", "sys", "_thread", "_warnings", "_weakref",
    "abc", "io", "os.path", "posixpath", "genericpath",
    "encodings", "codecs", "functools", "operator", "types",
    "typing", "typing_extensions", "weakref", "warnings",
    "_io", "sitecustomize", "_collections_abc", "_abc",
    "collections.abc", "heapq", "bisect", "_bisect", "_heapq",
    "keyword", "reprlib", "enum", "_py_abc", "ntpath",
    "posix", "stat", "genericpath", "fnmatch", "linecache",
    "tokenize", "token", "copy", "copyreg", "_copyreg",
    "struct", "_struct", "contextlib", "functools", "operator",
    "itertools", "threading", "_threading_local", "traceback",
    "linecache", "tokenize", "pickle", "io",
    # Internal C extensions (names starting with _)
})

_real_import = builtins.__import__


def _guarded_import(name, *args, **kwargs):
    top_level = name.split(".")[0]

    # Always allow internal C extensions and private modules
    if top_level.startswith("_"):
        return _real_import(name, *args, **kwargs)

    if top_level in ALLOWED_MODULES:
        return _real_import(name, *args, **kwargs)

    raise ImportError(
        f"Import of '{name}' is blocked by sandbox policy. "
        f"Allowed modules: math, json, re, collections, itertools, datetime, string, random"
    )


builtins.__import__ = _guarded_import
