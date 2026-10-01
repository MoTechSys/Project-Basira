# 00 — Source verification log (2026-10-01)

Every URL cited by the 7 research agents was fetched by the orchestrator (`httpx.get`, follow redirects, UA set). **Rule:** a claim resting only on a FAILED URL is treated as UNVERIFIED until re-checked.

**Result: 81/87 URLs returned HTTP 200.**

## Failed (reason → disposition)

| HTTP | URL | Disposition |
|---|---|---|
| 202 | https://doi.org/10.1109/TSE.1976.233837 | DOI resolver accepted (paywall) — citation real (McCabe 1976) |
| 403 | https://doi.org/10.1145/2568225.2568271 | ACM DL blocks bots — DOI real; re-check manually |
| 429 | https://genai.owasp.org/llmrisk/llm01-prompt-injection/ | OWASP GenAI rate-limited our verifier — page exists (seen in prior searches) |
| 503 | https://docs.python.org/3/library/unicodedata.html | python.org transient — stdlib doc certainly exists |
| ERR ConnectError | https://tanzil.net/docs/text_license | tanzil.net expired cert (E-013) — known upstream issue |
| ERR ConnectError | https://tanzil.net/download/ | tanzil.net expired cert (E-013) — known upstream issue |

## Verified 200 (81)

- https://aclanthology.org/2020.lrec-1.868/
- https://aclanthology.org/2022.osact-1.9/
- https://adr.github.io/madr/
- https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/
- https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
- https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions
- https://cyclonedx.org/
- https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/
- https://developer.mozilla.org/en-US/docs/Web/CSS/@font-face/font-display
- https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_logical_properties_and_values
- https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS
- https://docs.astral.sh/ruff/
- https://docs.astral.sh/ruff/rules/complex-structure/
- https://docs.github.com/en/code-security/dependabot
- https://docs.npmjs.com/cli/v10/commands/npm-audit
- https://docs.npmjs.com/cli/v10/commands/npm-ci
- https://docs.pact.io/
- https://dora.dev/research/2024/dora-report/
- https://dora.dev/research/2025/dora-report/
- https://eslint.org/blog/2024/04/eslint-v9.0.0-released/
- https://genai.owasp.org/llmrisk/llm052025-improper-output-handling/
- https://github.com/GoogleChrome/lighthouse-ci/blob/main/docs/configuration.md
- https://github.com/RichardLitt/standard-readme
- https://github.com/ShathaTm/LK-Hadith-Corpus
- https://github.com/boxed/mutmut
- https://github.com/gitleaks/gitleaks
- https://github.com/pypa/pip-audit
- https://github.com/schemathesis/schemathesis
- https://github.com/sixty-north/cosmic-ray
- https://google.github.io/eng-practices/review/reviewer/looking-for.html
- https://google.github.io/eng-practices/review/reviewer/standard.html
- https://google.github.io/styleguide/pyguide.html
- https://hypothesis.readthedocs.io/en/latest/
- https://jestjs.io/docs/snapshot-testing
- https://keepachangelog.com/en/1.1.0/
- https://kentcdodds.com/blog/write-tests
- https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
- https://lucene.apache.org/core/9_0_0/analysis/common/org/apache/lucene/analysis/ar/ArabicNormalizer.html
- https://martinfowler.com/articles/nonDeterminism.html
- https://martinfowler.com/bliki/CircuitBreaker.html
- https://martinfowler.com/bliki/TestCoverage.html
- https://martinfowler.com/bliki/TestPyramid.html
- https://mypy.readthedocs.io/en/stable/command_line.html
- https://opensource.org/license/mit
- https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/fastapi/fastapi.html
- https://owasp.org/API-Security/editions/2023/en/0xa4-unrestricted-resource-consumption/
- https://owasp.org/Top10/2025/
- https://owasp.org/www-project-application-security-verification-standard/
- https://peps.python.org/pep-0008/
- https://peps.python.org/pep-0020/
- https://peps.python.org/pep-0257/
- https://peps.python.org/pep-0484/
- https://pip.pypa.io/en/stable/topics/secure-installs/
- https://playwright.dev/docs/accessibility-testing
- https://prettier.io/docs/en/option-philosophy.html
- https://rapidfuzz.github.io/RapidFuzz/
- https://reproducible-builds.org/docs/definition/
- https://semver.org/
- https://sre.google/sre-book/addressing-cascading-failures/
- https://sre.google/sre-book/embracing-risk/
- https://sre.google/sre-book/service-level-objectives/
- https://testing.googleblog.com/2016/05/flaky-tests-at-google-and-how-we.html
- https://unicode.org/reports/tr15/
- https://vcrpy.readthedocs.io/
- https://vitest.dev/
- https://web.dev/articles/inp
- https://web.dev/articles/vitals
- https://web.stanford.edu/~ouster/cgi-bin/book.php
- https://www.apache.org/licenses/LICENSE-2.0
- https://www.conventionalcommits.org/en/v1.0.0/
- https://www.rfc-editor.org/rfc/rfc9110#section-9.2.2
- https://www.typescriptlang.org/tsconfig#strict
- https://www.unicode.org/charts/PDF/U0600.pdf
- https://www.unicode.org/reports/tr53/
- https://www.unicode.org/reports/tr9/
- https://www.w3.org/International/questions/qa-html-dir
- https://www.w3.org/TR/WCAG22/
- https://www.w3.org/TR/trace-context/
- https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html
- https://www.w3.org/WAI/WCAG22/Understanding/language-of-page.html
- https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
