#!/usr/bin/env python3
"""Fail if any tooltip has grown past the cap.

Tooltips rot in one direction. Every caveat looks worth adding at the moment it
is written, and nobody ever deletes one, so the corpus was ~3,000 words and the
longest hover ran to 524 characters before this existed.

The cap is 220 characters: formula, one clause of consequence, and at most one
caveat that changes how the number is READ. Everything else -- worked examples,
provenance, mechanism -- belongs in the view's DefinitionsPanel, which is a place
people read once rather than hover repeatedly.

    python3 scripts/check_tooltips.py            # check
    python3 scripts/check_tooltips.py --report   # full length distribution
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

CAP = 220
ROOT = Path(__file__).resolve().parent.parent / "frontend" / "src"

# `text="..."` on a HelpTooltip, and native title= attributes (static or
# template-literal). Row-level :title="fn(row)" is a function call, not prose,
# so it is out of scope -- those build their text in JS where a cap cannot be
# read off the source.
PATTERNS = [
    (re.compile(r'<HelpTooltip[^>]*?text="([^"]*)"', re.S), "HelpTooltip"),
    (re.compile(r'(?<!:)\btitle="([^"]{40,})"', re.S), "title="),
    (re.compile(r':title="`([^`]{40,})`"', re.S), "title=`"),
]


def collect() -> list[tuple[int, str, str, str]]:
    out = []
    for f in sorted(ROOT.rglob("*.vue")):
        src = f.read_text()
        for rx, kind in PATTERNS:
            for m in rx.finditer(src):
                text = m.group(1)
                line = src.count("\n", 0, m.start()) + 1
                out.append((len(text), f"{f.relative_to(ROOT)}:{line}", kind, text))
    return out


def main() -> int:
    found = collect()
    if not found:
        print("no tooltips found — has the markup changed?")
        return 1

    if "--report" in sys.argv:
        lens = sorted(n for n, *_ in found)
        n = len(lens)
        print(f"{n} tooltips · median {lens[n // 2]} · mean {sum(lens) // n} · max {lens[-1]}")
        for size, where, kind, text in sorted(found, reverse=True)[:15]:
            print(f"  {size:4}  {where:52} {text[:60]}…")

    over = [f for f in found if f[0] > CAP]
    if over:
        print(f"\n{len(over)} tooltip(s) over {CAP} characters:\n")
        for size, where, kind, text in sorted(over, reverse=True):
            print(f"  {size} chars · {where} ({kind})")
            print(f"    {text}\n")
        print("Trim to formula + one clause. Move examples, provenance and mechanism")
        print("into the view's DefinitionsPanel instead of deleting them.")
        return 1

    print(f"OK — {len(found)} tooltips, none over {CAP} characters.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
