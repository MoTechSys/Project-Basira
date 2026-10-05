# THIRD_PARTY_NOTICES.md — سجل الأدوات والتراخيص

> الجزء الثاني من «سجل المصادر والأدوات والتراخيص» الذي يطلبه المنظّم. المصادر النصية في `SOURCES.md`، النماذج في `AI_USAGE.md`.
> كود بصيرة نفسه مرخّص بـ **Apache-2.0** (انظر `LICENSE`).

## Backend (Python ≥ 3.12) — runtime dependencies

| Name             | Version | License                                            | URL                                                        |
|------------------|---------|----------------------------------------------------|------------------------------------------------------------|
| RapidFuzz        | 3.14.6  | MIT                                                | https://github.com/rapidfuzz/RapidFuzz                     |
| anyio            | 4.15.1  | MIT                                                | https://anyio.readthedocs.io/en/stable/versionhistory.html |
| fastapi          | 0.142.2 | MIT                                                | https://github.com/fastapi/fastapi                         |
| httpx            | 0.28.1  | BSD License                                        | https://github.com/encode/httpx                            |
| numpy            | 2.5.3   | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | https://numpy.org                                          |
| openpyxl         | 3.1.5   | MIT License                                        | https://openpyxl.readthedocs.io                            |
| pydantic         | 2.13.5  | MIT                                                | https://github.com/pydantic/pydantic                       |
| python-multipart | 0.0.32  | Apache-2.0                                         | https://github.com/Kludex/python-multipart                 |
| starlette        | 1.7.0   | BSD-3-Clause                                       | https://github.com/Kludex/starlette                        |
| uvicorn          | 0.54.0  | BSD-3-Clause                                       | https://uvicorn.dev/                                       |

جميعها تراخيص متساهلة (MIT / BSD / Apache-2.0) متوافقة مع Apache-2.0 ومع شرط «الاستخدام غير الربحي» للمؤسسة.

## Frontend (Node 20+) — runtime dependencies

| Name | Version | License |
|---|---|---|
| react | 19.x | MIT |
| react-dom | 19.x | MIT |

**لا مكتبة UI خارجية ولا أيقونات خارجية**: الأيقونات والهوية من `brand/` (ملك فريق المشروع).

## Frontend — dev/test only (لا تُشحن للمستخدم)

vite (MIT) · typescript (Apache-2.0) · vitest (MIT) · @playwright/test (Apache-2.0) · @axe-core/playwright (MPL-2.0) · @testing-library/* (MIT) · oxlint (MIT) · jsdom (MIT)

## Fonts

| Font | License | Usage |
|---|---|---|
| Readex Pro (variable, subset) | SIL OFL 1.1 — `brand/dist/fonts/OFL-ReadexPro.txt` | واجهة المستخدم (عربي + لاتيني)، وحروف الشعار محوّلة لمسارات |
| KFGQPC Uthmanic Script HAFS | مجمع الملك فهد — مجاني للاستخدام غير التجاري | نص المصحف فقط؛ يُحمَّل عند الحاجة. غير مضمّن في المستودع |

## External services (اختيارية، قابلة للتعطيل)

| Service | Purpose | Data sent | Toggle |
|---|---|---|---|
| OpenAI-compatible LLM (Gemini / Groq / OpenAI) | تحديد مواضع الاقتباس في النص فقط — **لا يكتب نصًا دينيًا** | نص المستخدم (بدون تخزين عندنا) | `LLM_PROVIDER=mock` |
| Vision model | قراءة النص من الصورة (OCR) | الصورة | `VISION_PROVIDER=mock` |
| dorar.net / shamela.ws / quranpedia.net / quranenc.com | روابط إحالة خارجية فقط (لا استدعاء API) | لا شيء | — |

## Competition brand assets

ألوان وخط وزوايا الهوية الرسمية لـ«تحدي الذكاء الاصطناعي في خدمة المحتوى الإسلامي 2026» مستخدمة **لأغراض المشاركة فقط** وفق شروط التحدي. خلفية صورة المشاركة (OG) من القالب الرسمي تُستبدل عند أي نشر خارج المسابقة.

## كيفية إعادة التوليد

```bash
cd backend && .venv/bin/pip-licenses --format=markdown --with-urls
cd frontend && npx license-checker --production --summary
```
