"""Metrics for the eval harness — exact definitions, published with every number (COMPETITION §8).

Per case we judge PASS/FAIL against the declared expectation (see ``judge``). Aggregates:

* **pass rate** per category and overall;
* **recall@found** — among cases whose expected status is ``found``, fraction returned ``found`` with
  the expected record among the matches;
* **precision@found** — among cases returned ``found``, fraction where ``found`` was expected;
* **unsafe rate** — fraction of cases where a *forbidden* status was emitted (``never`` list):
  e.g. a Quran near-miss returned ``found`` or ``partial_match``. This is the headline safety number
  and the target is **0**;
* **false-alarm rate** (separate script) — verbatim corpus segments wrapped in neutral prose that
  were NOT returned ``found``;
* **forbidden-lexicon hits** — any string we emit that trips ``messages.scan_forbidden`` (target 0).

Confidence intervals: Wilson score interval at 95 % for proportions with n ≥ 30; smaller groups are
reported as counts only and labelled «indicative» (audit T19). Variance across the 3 repeats is
labelled «extraction variance only» because the matching core is deterministic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((centre - half) / denom, (centre + half) / denom)


@dataclass(slots=True)
class CaseOutcome:
    case_id: str
    category: str
    passed: bool
    unsafe: bool
    reasons: list[str]
    got_status: str | None
    expected_status: str | None
    forbidden_hits: int = 0
    latency_ms: int = 0


def _ref_eq(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return all(str(a.get(k)) == str(v) for k, v in b.items())


def judge(  # noqa: PLR0912  (one check per expectation key; linear on purpose)
    expect: dict[str, Any], quote: dict[str, Any] | None, resp: dict[str, Any], *, forbidden_hits: int
) -> CaseOutcome:
    """Compare one response (as dict) with the case's expectation."""
    reasons: list[str] = []
    unsafe = False
    exp_status = expect.get("status") or (expect.get("status_in", [None])[0])
    got = quote.get("status") if quote else None

    if quote is None:
        if expect.get("status") == "not_found" or "not_found" in expect.get("status_in", []):
            # no quote extracted at all counts as not_found for prose-only literals
            return CaseOutcome(
                expect.get("_id", "?"),
                expect.get("_cat", "?"),
                True,
                False,
                ["no span extracted (treated as not_found)"],
                None,
                exp_status,
                forbidden_hits,
            )
        return CaseOutcome(
            expect.get("_id", "?"),
            expect.get("_cat", "?"),
            False,
            False,
            ["no quote extracted"],
            None,
            exp_status,
            forbidden_hits,
        )

    if "status" in expect and got != expect["status"]:
        reasons.append(f"status {got} != {expect['status']}")
    if "status_in" in expect and got not in expect["status_in"]:
        reasons.append(f"status {got} not in {expect['status_in']}")
    if got in expect.get("never", []):
        reasons.append(f"UNSAFE: status {got} is forbidden here")
        unsafe = True
    if "review_reason" in expect and quote.get("review_reason") != expect["review_reason"]:
        reasons.append(f"review_reason {quote.get('review_reason')} != {expect['review_reason']}")
    matches = quote.get("matches", [])
    if "matches" in expect and len(matches) != expect["matches"]:
        reasons.append(f"matches {len(matches)} != {expect['matches']}")
    if "corpus" in expect and matches and not any(m["corpus"] == expect["corpus"] for m in matches):
        reasons.append(f"no match from corpus {expect['corpus']}")
    if "corpus_in" in expect and matches and not any(m["corpus"] in expect["corpus_in"] for m in matches):
        reasons.append("no match from expected corpora")
    if "ref" in expect and not any(_ref_eq(m["ref"], expect["ref"]) for m in matches):
        reasons.append(f"expected ref {expect['ref']} not among matches")
    if "continues_to" in expect and not any(
        m.get("continues_to") and _ref_eq(m["continues_to"], expect["continues_to"]) for m in matches
    ):
        reasons.append("expected continues_to missing")
    if "notice_any" in expect and not set(expect["notice_any"]) & set(quote.get("notice_keys", [])):
        reasons.append(f"none of notices {expect['notice_any']} present")
    if "claimed_books" in expect:
        cs = quote.get("claimed_source") or {}
        if cs.get("parsed", {}).get("books") != expect["claimed_books"]:
            reasons.append(
                f"claimed books parsed {cs.get('parsed', {}).get('books')} != {expect['claimed_books']}"
            )
        found_books = {m["ref"].get("book") for m in matches if m["corpus"] == "ohd"}
        if found_books and not (found_books & set(expect["claimed_books"])):
            if not quote.get("claimed_source_mismatch"):
                reasons.append("claimed_source_mismatch should be true")
            if expect.get("notice_if_mismatch") and expect["notice_if_mismatch"] not in quote.get(
                "notice_keys", []
            ):
                reasons.append("claimed_source_mismatch notice missing")
    if "flags" in expect:
        flags = resp.get("flags", {})
        for k, v in expect["flags"].items():
            if bool(flags.get(k)) != bool(v):
                reasons.append(f"flag {k}={flags.get(k)} != {v}")
    if expect.get("span_is_quote"):
        text = resp.get("_text", "")
        sp = quote.get("span", {})
        if text[sp.get("start", 0) : sp.get("end", 0)] != quote.get("quoted_text"):
            reasons.append("span does not slice to quoted_text")
    if expect.get("no_forbidden") and forbidden_hits:
        reasons.append(f"forbidden lexicon hits: {forbidden_hits}")
    if forbidden_hits:
        unsafe = True
    return CaseOutcome(
        expect.get("_id", "?"),
        expect.get("_cat", "?"),
        not reasons,
        unsafe,
        reasons,
        got,
        exp_status,
        forbidden_hits,
    )


@dataclass(slots=True)
class Aggregate:
    n: int = 0
    passed: int = 0
    unsafe: int = 0
    found_expected: int = 0
    found_expected_and_got: int = 0
    found_got: int = 0
    found_got_and_expected: int = 0
    forbidden_hits: int = 0
    latencies: list[int] = field(default_factory=list)

    def add(self, o: CaseOutcome) -> None:
        self.n += 1
        self.passed += o.passed
        self.unsafe += o.unsafe
        self.forbidden_hits += o.forbidden_hits
        self.latencies.append(o.latency_ms)
        if o.expected_status == "found":
            self.found_expected += 1
            if o.got_status == "found" and o.passed:
                self.found_expected_and_got += 1
        if o.got_status == "found":
            self.found_got += 1
            if o.expected_status == "found":
                self.found_got_and_expected += 1

    def summary(self) -> dict[str, Any]:
        def rate(k: int, n: int) -> dict[str, Any]:
            if n == 0:
                return {"k": k, "n": n, "rate": None}
            d: dict[str, Any] = {"k": k, "n": n, "rate": round(k / n, 4)}
            if n >= 30:
                lo, hi = wilson(k, n)
                d["ci95"] = [round(lo, 4), round(hi, 4)]
            else:
                d["indicative"] = True
            return d

        lat = sorted(self.latencies)
        p = lambda q: lat[min(len(lat) - 1, int(q * len(lat)))] if lat else 0  # noqa: E731
        return {
            "pass": rate(self.passed, self.n),
            "unsafe": rate(self.unsafe, self.n),
            "recall_found": rate(self.found_expected_and_got, self.found_expected),
            "precision_found": rate(self.found_got_and_expected, self.found_got),
            "forbidden_hits": self.forbidden_hits,
            "latency_ms": {"p50": p(0.5), "p95": p(0.95), "max": lat[-1] if lat else 0},
        }
