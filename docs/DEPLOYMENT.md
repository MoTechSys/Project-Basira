# Deployment

> For whoever publishes Basira. Commands and outputs were verified against `main` on 2026-10-05.
> The product is **one container**: backend + built frontend + prebuilt corpus snapshot. No database, no cache.

## 0. Pre-flight checklist (do these, in order)

- [ ] `bash scripts/bootstrap.sh && make gates && make smoke && make eval-full` are green on the commit you deploy.
- [ ] Decide the public hostname (needed for CORS and for the MCP URL you publish).
- [ ] Know your load balancer / reverse-proxy address or CIDR (needed for **B12**, below). If you skip this the
      rate limiter sees every visitor as one IP and the site throttles itself under load.
- [ ] Have a Genspark (or any OpenAI-compatible) key ready to enter **once** in `/settings` after boot — or run
      rules-only (the product works without a model; it says so in `extraction_degraded`).

## 1. Build and run with Docker (recommended)

```bash
docker build -t basira:$(git rev-parse --short HEAD) --build-arg BUILD_SHA=$(git rev-parse --short HEAD) .
docker run -d --name basira -p 8000:8000 \
  -e BASIRA_CORS_ORIGINS=https://basira.example.org \
  -e BASIRA_TRUSTED_PROXIES=10.0.0.0/8 \
  -e FORWARDED_ALLOW_IPS=10.0.0.0/8 \
  -v basira-data:/data \
  --read-only --tmpfs /tmp \
  basira:$(git rev-parse --short HEAD)
```

or simply `docker compose up -d` (same settings via environment; see `docker-compose.yml`).

What the image does: multi-stage build → `npm run build` → `pip install backend[mcp]` → `corpus/fetch.py`
(sha256-verified) → `build_index.py` → snapshot → runtime image as non-root `basira`, read-only filesystem,
`/data` volume for the one file the app ever writes (`model.json`, mode 0600). Measured in CI: snapshot boot 0.78 s, RSS 314 MB.

Health: `GET /health` → `{"status":"ok","boot":"snapshot","index_sha256":"…"}`.

## 2. Environment variables that matter in production

| Variable | Set to | Why |
|---|---|---|
| `BASIRA_CORS_ORIGINS` | your public origin(s), comma-separated | Browser calls from the same origin need nothing; set it if the UI is served elsewhere |
| `BASIRA_TRUSTED_PROXIES` | LB / proxy IP or CIDR | **B12**: `X-Forwarded-For` is honoured only from these peers; empty = never |
| `FORWARDED_ALLOW_IPS` | **same value** as above | uvicorn's own proxy trust. Never `'*'` |
| `BASIRA_RATE_LIMIT_PER_MIN` | default 30 | Per client IP, fixed window; `X-Eval-Key` bypass for your own eval runs (`BASIRA_EVAL_KEY`) |
| `BASIRA_MCP` | `1` (image default) | MCP server at `/mcp`; set `0` to disable |
| `BASIRA_MODEL_CONFIG` | `/data/model.json` (image default) | Where `/settings` stores the operator's key; must be on a writable volume |
| `BUILD_SHA` | git short SHA | Shown in `/health` so a judge can tie a deployment to a commit |
| `LLM_*` / `VISION_*` | optional | Environment fallback when no key is saved from `/settings` |

Everything else has safe defaults (`.env.example`). **Do not** set `BASIRA_SNAPSHOT_WRITE=1` in the image — the
snapshot is prebuilt.

## 3. After first boot

1. Open `https://<host>/settings`, paste the Genspark key, choose a model (default `gpt-5.4-mini`, see
   `docs/MODELS.md`), click **تحقق واحفظ**. The server verifies the key upstream, saves it to `/data/model.json`,
   and hot-swaps the providers — no restart. `/health` now shows `openai-compatible:<model>`.
2. Verify the three live doors:
   ```bash
   H=https://<host>
   curl -s $H/v1/check -H 'Content-Type: application/json' -d '{"text":"قال تعالى: ﴿إن الله مع الصابرين﴾"}' | jq .quotes[0].status
   curl -s -X POST $H/mcp -H 'accept: application/json, text/event-stream' -H 'content-type: application/json' \
        -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | jq '.result.tools | length'      # 6
   curl -s $H/v1/receipt -H 'Content-Type: application/json' -d '{"text":"قال تعالى: ﴿إن الله مع الصابرين﴾"}' | jq .receipt_id
   ```
3. Publish the MCP config for assistants: `{"mcpServers":{"basira":{"type":"http","url":"https://<host>/mcp"}}}`.

## 4. Platform notes

* **Reference deployment** — https://basirapp.site runs on one VPS with Docker Compose and Caddy, and
  redeploys itself from `main` of this repository within a minute of each push. The exact files and install
  steps are in [`deploy/vps/`](../deploy/vps/README.md).
* **Any Docker host / VM** — the recipe above. Put TLS at the proxy; the app emits HSTS when it sees
  `X-Forwarded-Proto: https`.
* **Cloudflare / managed container platforms** — the image is stateless except `/data`. Mount a small persistent
  volume for it, or accept re-entering the key after each redeploy. Set the proxy variables to the platform's
  egress range.
* **Static-only hosts (Pages, Netlify)** are **not** suitable: the frontend needs the API on the same origin and
  the engine needs ≈ 300 MB RAM.
* **Local development** — `make serve` (or `make serve-mcp`) on port 8000; no process manager is needed.

## 5. Operating

* Logs contain method/path/status only — never user text, never keys.
* Rotate the model key from `/settings` (enter a new one) or remove it (**حذف المفتاح من الخادم**).
* Corpus update = change `corpus/manifest.json` pins → rebuild image. `index_sha256` in `/health` changes, and
  every `determinism_hash` changes with it — receipts issued on the old build replay as `stale`, by design.
* CI (`.github/workflows/ci.yml`) runs on every push to `main` and every pull request: lint, types, corpora →
  index → fixture (cached by manifest hash), pytest, eval `--fail-on-unsafe`, dependency audits, frontend gates,
  gitleaks, and a Docker build that boots the image and checks a known ayah.

## 6. Rollback

Images are immutable and tagged by commit. `docker run` the previous tag; the `/data` volume is forward- and
backward-compatible (one JSON file validated on load; an unknown model id is ignored and the app falls back to env
defaults).
