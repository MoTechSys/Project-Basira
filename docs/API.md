# مرجع واجهة بصيرة (API Reference)

## نقاط النهاية (Endpoints)

### `POST /v1/check`
التحقّق من اقتباسات داخل نص عربي أو إنجليزي.

**الطلب:**
```json
{
  "text": "قال تعالى: إن الله مع الصابرين",
  "ui_lang": "ar",
  "source_modality": "text",
  "options": { "max_candidates": 3 }
}
```

**الرد (مثال FOUND):**
```json
{
  "quotes": [{
    "span": {"start": 11, "end": 36},
    "kind": "quran",
    "status": "found",
    "match": {
      "source_id": "tanzil-uthmani",
      "ref": "2:153",
      "verbatim": "إِنَّ ٱللَّهَ مَعَ ٱلصَّـٰبِرِينَ"
    }
  }],
  "determinism_hash": "a3f2c1..."
}
```

### `GET /health`
فحص الصحّة.

**الرد:**
```json
{
  "status": "ready",
  "boot_seconds": 2.4,
  "corpus_sha": "c7f8..."
}
```

### `POST /v1/check` (image modality)
نفس البنية لكن `source_modality="image"` و`text` يحمل base64.

## الـ 4-state Model
| القيمة | المعنى |
|--------|--------|
| `found` | مطابقة تامّة في مصدر معتمد |
| `partial_match` | مطابقة قريبة مع diff |
| `not_found` | غير موجود في الذخيرة المعتمدة |
| `needs_review` | إشارة منخفضة الثقة — تدخّل بشري |

## رؤوس خاصة (Custom Headers)
- `X-Basira-Provider-Key`: مفتاح موفّر LLM/Vision للطلب (BYOK)
- `X-Eval-Key`: مفتاح harness الرسمي (bypass rate limit)

## رموز الخطأ
| HTTP | الوصف |
|------|--------|
| 413 | النص يتجاوز 5000 حرف |
| 422 | جسم الطلب غير صالح |
| 429 | تجاوز حد المعدّل |
| 503 | الذخيرة قيد التحميل |

## الـ MCP (Model Context Protocol)
الـ server يعمل عبر stdio ويعرض tool واحد: `check_text` بنفس بنية الـ HTTP.

تشغيل:
```bash
BASIRA_MCP=1 python -m app.mcp_server
```
