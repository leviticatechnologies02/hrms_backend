"""Detect duplicate FastAPI routes and operation IDs in the app.

Usage:
    python scripts/find_duplicate_routes.py

This imports `app.main:app` by default (adjust `APP_IMPORT` if your app is located elsewhere).
"""
from collections import defaultdict
import importlib
import sys

APP_IMPORT = "app.main:app"


def load_app(spec: str):
    module_name, attr = spec.split(":")
    m = importlib.import_module(module_name)
    return getattr(m, attr)


def inspect_app(app):
    by_op = defaultdict(list)
    by_path = defaultdict(list)
    for r in getattr(app, 'routes', []):
        try:
            name = getattr(r, 'name', None)
            methods = sorted([m for m in getattr(r, 'methods', []) if m not in ('HEAD', 'OPTIONS')])
            path = getattr(r, 'path', None)
            op = getattr(r, 'operation_id', None)
            by_op[op].append((path, methods, name))
            by_path[(path, tuple(methods))].append((op, name))
        except Exception:
            continue

    print("Duplicate operation_id entries:\n")
    for op, entries in by_op.items():
        if op and len(entries) > 1:
            print(f"operation_id={op} -> {entries}")

    print("\nDuplicate path+methods entries:\n")
    for k, entries in by_path.items():
        if len(entries) > 1:
            print(f"path={k[0]} methods={k[1]} -> {entries}")


if __name__ == '__main__':
    try:
        app = load_app(APP_IMPORT)
    except Exception as e:
        print(f"Failed to import app: {e}")
        sys.exit(1)
    inspect_app(app)
