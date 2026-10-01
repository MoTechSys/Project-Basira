# CI definition (kept outside `.github/workflows/` on purpose)

`github-ci.yml` is the full GitHub Actions pipeline (lint + types → fixture index → pytest → eval with
`--fail-on-unsafe` → pip-audit; frontend lint/typecheck/vitest/build; gitleaks; Docker build + smoke).

The agent's GitHub App token lacks the `workflows` permission, so GitHub rejects any push that creates
`.github/workflows/*.yml`. **Owner action (one time, from your own account or the GitHub web UI):**

```bash
mkdir -p .github/workflows && git mv ci/github-ci.yml .github/workflows/ci.yml && git commit -m "ci: activate" && git push
```
