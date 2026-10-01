# Review of the two agent packs (2026-10-01) — verified, not trusted

Both packs were cut from `main@5fb118f`-era code (85 tests, before E-023..E-038). Every claim below was re-run on the **current** `main` (d04d2c1) in a git worktree; nothing is quoted from the packs' own reports.

## Pack B — `basira_pro_v3` (OfGrP2rM) → **MERGED into main (af98ecb)**

| Claim | Verified | Result |
|---|---|---|
| Two patches apply cleanly | ✓ | `git am --3way` onto d04d2c1: clean (one auto-merge in rules.py) |
| Live bug: hadith «اطلبوا العلم ولو في الصين» got `not_found_quran` | ✓ reproduced on main | fixed by **I10** (`not_found` wording follows claimed kind; `unknown` → `not_found_any`) |
| «حُرِّمَ … الْمَيْتَةَ» was `found` | ✓ reproduced on main | fixed by **I11** diacritic gate (`match/harakat.py`): Quran only, absence never counts, final letter never judged |
| ruff/mypy/pytest | ✓ | clean · **129/129** |
| eval-full | ✓ | 150/150 · 0 unsafe · FA 0/500 (7.9 s) |
| smoke | ✓ | OK |
| IslamicEval 2025 1B | ✓ | 89.07 % (was 89.47) — the −1 is **B-Q23_7**, where gold writes «شِيْءٍ» (kasra) and the Mushaf «شَىْءٍ»; verified byte-level in `dev_SubtaskB.xml`. Our flag is correct; the gold is wrong. |
| IslamicEval 2026 Task 2 | ✓ reproduced | Ayah **98.71** (n=698), matn 93.20 |
| IslamicEval 2026 Task 1 | ✓ reproduced with the **official** `task1_scoring.py` | **F1 0.6446** (pack said 64.30; difference = scorer rounding/version) |
| Anchor detector false alarms | ✓ own probe: 12 hand-written religious prose sentences | 1 hit — «الحمد لله رب العالمين», which **is** 1:2 → not a false alarm. 5 000 chars in 18 ms |

Not verified: «1462 ayat + 400 hadith, 0 FA» (their harness not included). Numbers kept out of our docs until re-run.

## Pack A — `basira_upgrade_pack_v2` (XKWJ1R1F) → **ported to branch `review/packA` (6fc203a), NOT merged yet**

| Claim | Verified | Result |
|---|---|---|
| Diff applies | ✗ as shipped (diff -ruN, 5 rejects in rules.py/pipeline.py/messages/Makefile) | hand-ported; 2 integration gaps fixed: `snapshot.py` lacked GS2/G2 (E-024) → `SNAPSHOT_VERSION=3`; one `_gather_evidence` return path |
| Snapshot boot 1.9 s / 250–283 MB | ✓ | **2.3 s / 249 MB** (full build on same box: 23.3 s / peak 1 005 MB) |
| Snapshot ≡ full build | ✓ | identical fingerprint over 8 exact+BM25 queries (`1cecb27f590cec86`) |
| pytest | ✓ | 149/149 on the ported tree; mypy clean |
| eval-full | ✓ | 150/150 · 0 unsafe · FA 0/500 |
| `scan.py` (unmarked Quran) | ✓ same prose probe | identical behaviour to B's anchor detector → **redundant**; drop in favour of B (`anchor.py` also covers hadith) |
| Security headers CSP | ⚠ | `script-src 'self'` **breaks** `index.html`'s inline theme-pre-paint and JSON-LD scripts → needs a nonce/hash or `'unsafe-inline'` for those two blocks before enabling |
| Dockerfile | ⚠ not built | `COPY brand/dist/` assumes a `brand/` dir at repo root that main doesn't have (brand lives in `frontend/public/brand`); `rm -rf corpus/data` fine; 1 worker ✓ (E-038) |
| 9 delivery docs | ✓ present | LICENSE/SOURCES/THIRD_PARTY/AI_USAGE/SAFETY/SECURITY/CHANGELOG/Dockerfile/CI — review wording against SAFETY §1.3 before merge |

### Merge plan for pack A onto main (now = main+B)
Conflicts seen in a trial merge: `config.py`, `pipeline.py`, `schemas.py`, `state.py`, `messages/*.json`, `eval/REPORT.md`.
1. **Renumber** A's invariants: A-I10 → **I12** (claimed ayah ref mismatch), A-I11 → **I13** (attribution cross-notice). B's I10/I11 keep their numbers (status-affecting beats descriptive).
2. `config.py`: keep B `anchor_detect`; take A `static_dir`, `snapshot_write`; **drop** `quran_scan*`.
3. `pipeline.py`: keep B import `segments`; call order `d = self._diacritic_gate(...)` **then** `self._quran_context_notices(...)`; keep both `_augment_spans` (B) and `_determinism_hash` (A); delete `_quran_sweep` + `scan.py` + `quran_scan_found` key + the 3 asserts in `test_scholar_lens.py` that reference it.
4. `schemas.py`: keep both `segments` and `repeated_spans`.
5. `messages`: union of keys (A adds 8 notice keys).
6. Fix CSP for the two inline scripts; fix Dockerfile `brand/` path; then `make gates && make smoke && make eval-full`, `npm run build && vitest`, E2E.
7. **Never** symlink `.venv`/`corpus/index` inside a worktree whose tree tracks them as untracked — `git add -A` will commit the symlinks (happened once, fixed in 6fc203a).

## Decision summary
- B in; A next, by the plan above (≈1–2 h).
- Both packs' *UI* work is prompts, not code — nothing to merge there.
