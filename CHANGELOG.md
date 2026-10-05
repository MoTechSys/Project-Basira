# سجل التغييرات — بصيرة

## [0.1.0] — 2026-10-06 (إصدار مسابقة IslamicAIch 2026)

### أُضيف
- واجهة خلفية FastAPI كاملة: `/check`, `/health`, MCP stdio
- محرك مطابقة حتمي (exact + harakat + sliding window + diff)
- استرجاع هجين (BM25 + fuzzy) على Tanzil + OHD + HadeethEnc
- 4-state model مع ثوابت I1-I9 شرعية صلبة
- واجهة أمامية React 19 بـ RTL كامل + PWA + i18n ar/en
- BYOK (مفاتيح مستخدم لكل طلب، بدون تسجيل)
- CSP صارمة + headers أمان + rate limiting
- حزمة اختبارات: 100+ (backend) + تغطية ~82%
- Playwright e2e + Vitest للـ frontend
- Dockerfile متصلّب + docker-compose + GitHub Actions CI
- Eval harness متوافق مع IslamicEval الرسمي

### القيود (Known limitations)
- لا تخريج ولا إفتاء — عرض فقط للـ provenance
- يحتاج snapshot حديث من المصادر الأربعة
- English input يمر عبر translation_assisted mode

---

### الختم
تم ختم الإصدار قبل الموعد النهائي (23:59 بتوقيت الرياض — 6 أكتوبر 2026)
بـ 110+ commit على `main`، بدون تعديلات غير موثّقة، وبسلامة الـ hashes.

التسليم: MoTechSys.
