#!/usr/bin/env python3
"""E-037 false-alarm check over the whole Quran (run from upgrade/basira_patched with PYTHONPATH=backend).

1) every vocalized ayah vs itself must be 'consistent';
2) the Uthmani display text (as if a user pasted it) vs the vocalized simple text must never be 'conflict'
   (rasm differences are letter questions, skipped by design).
Result on 2026-10-01: ayat=6236 self-conflicts=0 uthmani-vs-vocalized conflicts=0 (4.8 s).
"""
import sys, time
from pathlib import Path
from app.snapshot import load_or_build
from app.normalize import tokenize
from app.match.harakat import compare_quote

store, _ = load_or_build(Path(sys.argv[1] if len(sys.argv) > 1 else "corpus/index"), write=False)
t0 = time.perf_counter(); n = bad = uth = 0
for r in store.records:
    if r.corpus != "tanzil" or not r.text_vocalized:
        continue
    n += 1
    v = r.text_vocalized; vt = tokenize(v); sp = [(t.start, t.end) for t in vt]
    if compare_quote(v, sp, v, sp)[0] == "conflict": bad += 1
    u = r.display; ut = tokenize(u)
    if len(ut) == len(vt) and compare_quote(u, [(t.start, t.end) for t in ut], v, sp)[0] == "conflict": uth += 1
print(f"ayat={n} self-conflicts={bad} uthmani-vs-vocalized conflicts={uth} in {time.perf_counter()-t0:.1f}s")
sys.exit(1 if (bad or uth) else 0)
