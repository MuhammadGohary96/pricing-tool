#!/usr/bin/env python3
"""Fail if anything the backend imports is missing from the environment.

This exists because of a production outage on 2026-08-22. `openpyxl` was
imported at module scope by services/excel_report.py, which routers/commercial.py
imports, which main.py imports -- but it was never added to
backend/requirements.txt. It worked for weeks locally, because the dev machine's
system python already had it. In the image it did not exist, so main.py never
finished importing, uvicorn never bound :8000, and the gateway served
"no healthy upstream". With strategy: Recreate the old pod was already gone, so
it was a full outage rather than a failed rollout.

Two things make the naive version of this check useless:

1.  A STATIC scan of requirements.txt is not enough. It passed while
    `google-cloud-bigquery-storage` was missing, because that one is imported
    inside a function behind `except ImportError`. Nothing failed -- the
    BigQuery load silently fell back to the REST iterator and a ~2 minute Arrow
    pull became 1,603 seconds for 3M rows.

2.  Checking on the DEV MACHINE is not enough, and is in fact the whole bug:
    the dev python had both packages. The only environment whose answer matters
    is the built image.

So: walk every .py file, collect every imported name at ANY indentation, and
actually import each one here -- wherever "here" is. Run it inside the image.

    python3 scripts/check_imports.py                 # walk ./backend
    python3 scripts/check_imports.py /app/backend    # walk an explicit root
"""
from __future__ import annotations

import ast
import importlib
import pathlib
import sys

# First-party packages, which are importable by definition and not deps.
LOCAL = {"backend", "mcp_server", "scripts", "frontend"}


def imported_names(root: pathlib.Path) -> dict[str, set[str]]:
    """Every third-party name imported anywhere under `root`, at any depth."""
    found: dict[str, set[str]] = {}

    def note(name: str, where: str) -> None:
        if name.split(".")[0] in LOCAL:
            return
        if name.split(".")[0] in sys.stdlib_module_names:
            return
        found.setdefault(name, set()).add(where)

    for f in sorted(root.rglob("*.py")):
        try:
            tree = ast.parse(f.read_text())
        except SyntaxError as e:
            print(f"  !! could not parse {f}: {e}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    note(a.name, f"{f.name}:{node.lineno}")
            # level 0 only: a relative import is first-party by construction.
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                note(node.module, f"{f.name}:{node.lineno}")
                for a in node.names:
                    # `from google.cloud import bigquery_storage` -- the thing
                    # that matters is the submodule, not the package.
                    note(f"{node.module}.{a.name}", f"{f.name}:{node.lineno}")
    return found


def main() -> int:
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "backend").resolve()
    if not root.is_dir():
        print(f"no such directory: {root}")
        return 1

    # `python /scripts/check_imports.py` puts /scripts on sys.path[0], not the
    # app root, so `import backend.main` would fail for the wrong reason. Put
    # the package's parent first regardless of where this file lives.
    sys.path.insert(0, str(root.parent))

    names = imported_names(root)
    missing: list[tuple[str, str]] = []

    for name in sorted(names):
        try:
            importlib.import_module(name)
        except ModuleNotFoundError as exc:
            # `from x import SomeClass` yields "x.SomeClass", which is an
            # attribute rather than a module. Not a missing dependency.
            parent, _, attr = name.rpartition(".")
            if parent:
                try:
                    if hasattr(importlib.import_module(parent), attr):
                        continue
                except Exception:
                    pass
            missing.append((name, str(exc)))
        except Exception:
            # Imports fine but raises on init (needs config, a client, a
            # display). Present is all we are asserting here.
            pass

    print(f"checked {len(names)} imported names under {root}")

    # The real end-to-end assertion: the thing uvicorn actually loads. Catches
    # an import chain that individually resolves but collapses together.
    # Reported alongside `missing` rather than short-circuiting it -- when the
    # app fails to import, the missing dependency IS the diagnosis.
    app_error = None
    try:
        importlib.import_module(f"{root.name}.main")
        print(f"  {root.name}.main imports OK")
    except Exception as exc:
        app_error = f"{type(exc).__name__}: {exc}"
        print(f"\n{root.name}.main FAILED to import: {app_error}")
        print("This is what takes the pod down -- uvicorn cannot load the app.")

    if missing:
        print(f"\n{len(missing)} imported name(s) not available here:\n")
        for name, err in missing:
            print(f"  {name}")
            print(f"      {err}")
            for where in sorted(names[name])[:3]:
                print(f"      imported at {where}")
        print("\nAdd the package to backend/requirements.txt. If it is optional,")
        print("it still belongs there -- a silent except ImportError fallback")
        print("cost 25 minutes of cold-start time once already.")

    if missing or app_error:
        return 1

    print("OK — everything the backend imports is present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
