# Basira Telegram bot

A thin client over the public Basira API. Send or forward a text or an image that quotes the Quran or Hadith; the
bot replies with the status, the source text **verbatim**, its reference, the differing words in **bold** (from the
API `diff`), source/search links and the transparency line. Live: **[@BasiraCheckBot](https://t.me/BasiraCheckBot)**.

## What the bot does not do
- It holds no model and writes no religious text. Every sentence about a quotation is a template from
  `messages/ar.json` (served by `GET /v1/messages/ar`); `source_text` / `ref_label_ar` are inserted as received.
- It issues no judgement; `tests/test_strings.py` and `tests/test_render.py` run the backend lexicon scanner.
- It stores nothing (ADR-004): no database, no files; image bytes live in a `BytesIO` closed after the request;
  logs carry chat type, input kind, status counts and latency only (`test_logs_never_contain_user_text_or_ids`).
- An image is never `found` (the API enforces it; the bot shows the OCR text first, under «راجعه»).

## Create a bot (@BotFather)
1. `/newbot` → name → username ending in `bot`.
2. Copy the token into `.env` as `TELEGRAM_BOT_TOKEN` (never into git).
3. `/setprivacy` → Enable (the bot then sees only commands and replies in groups).

## Run
```bash
make bot-install && make bot-test                  # from the repo root
cd integrations/telegram && cp .env.example .env    # fill the token
set -a; . ./.env; set +a; .venv/bin/python -m bot.main          # long polling
docker compose --profile bot up -d                   # with the API container (BASIRA_API_URL=http://basira:8000)
```
Webhook mode: set `TELEGRAM_WEBHOOK_URL` and `TELEGRAM_WEBHOOK_SECRET` (16–256 chars); the bot listens on `PORT`
at `/telegram`.

## Usage and limits
| Input | Behaviour |
|---|---|
| `/start`, `/help` | welcome, transparency and privacy lines from `messages/ar.json`, site button |
| text / forward | `POST /v1/check` → one reply per result, split on block boundaries under 4096 chars |
| photo or PNG/JPEG/WebP document ≤ 6 MB | `POST /v1/check/image` (field `image`) → OCR text, then results |
| `/limits`, `/sources` | `GET /v1/rules?ui_lang=ar` (first 1500 chars), `GET /v1/sources` |
| groups | `/check <text>` or `/check` as a reply to a text/photo; plain messages are ignored |
| > 5000 chars | refused locally with `errors.text_too_long` |
| API 413/422/429/503 | `error.message_ar` verbatim (429 adds «حاول بعد دقيقة») |

Rate limit 10 messages/minute/user (in memory). Timeouts: 30 s text, 60 s image; a «جارٍ الفحص…» placeholder is
edited into the result. **Known limit:** with privacy mode on, Telegram does not deliver plain `@mention` messages
to bots (measured: 0 updates), so in groups use `/check`; mentions work only if privacy is disabled or the bot is
an admin.

## Measured (2026-10-06)
- `ruff check . && ruff format --check . && mypy --strict . && pytest -q` → **73 passed**, 0 lint/type errors.
- Live, real account → @BasiraCheckBot → https://basirapp.site (`scripts/live_e2e.py`): 11/11 private scenarios
  (start, found, needs_review with bold «علي»/«عَلَىٰ», not_found + links, partial_match, refusal, no quotes,
  sources, limits, unsupported file, image → `needs_review/image_unconfirmed`), plus channel forward (2 × found),
  group `/check` reply, group plain text ignored, group `/check` usage. Bot latency 1.9–9.0 s per check.
