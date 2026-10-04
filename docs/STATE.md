# حالة المشروع — بصيرة

> آخر تحديث: 2026-10-05 المساء (نهاية اليوم الثاني)
> المشرف: MoTechSys

## اليوم الثاني — ما أُنجز

### الواجهة الأمامية (frontend-agent) ✅
- [x] هيكل Vite + React 19 + TypeScript 6
- [x] نظام تصميم: tokens.css, Logo/Icon, i18n ar/en
- [x] Components: StatusBadge, QuoteCard, ResultsView, SourcesFooter, DiffView, AnnotatedText
- [x] Check.tsx كاملة مع كل حالات (loading/empty/error/success)
- [x] موقع كامل: Home, Shell, Settings, LensDemo, Starfield, router
- [x] PWA: manifest, sw.js (cache-first/network-first)
- [x] خطوط Noto Naskh محلياً (لا CDN)

### الواجهة الخلفية — تعزيز الأمان
- [x] guard.py (حد الحجم، bidi، control chars)
- [x] english_gate.py (كشف السكربت، تمييز translation_assisted)
- [x] byok.py (مفاتيح لكل طلب، لا تسجيل، لا حفظ)
- [x] devgate.py (مسارات dev خلف BASIRA_DEV_TOKEN)
- [x] mcp_server.py (stdio MCP)
- [x] openapi_examples.json لـ /docs

### الـ Eval
- [x] PLAN.md + metrics.py + materialize.py + false_alarm.py
- [x] cases.yaml (60 حالة عربية) + english_cases.yaml (40 حالة)
- [x] islamiceval adapter للـ harness الرسمي
- [x] gen_cases.py لتوسيع الحالات

### DevOps
- [x] scripts: smoke, bench_models, mcp_demo, gen_examples, gen_trust, check_site_lexicon

### الاختبارات الجديدة
- [x] test_guard, test_english_gate, test_byok, test_api_dev
- [x] test_mcp, test_rules, test_precision, test_safety_gates
- [x] test_scholar_lens, test_translations
- [x] frontend/e2e/check.spec.ts (Playwright)

## اليوم الأخير (6 أكتوبر) — المتبقي
- [ ] تثبيت SOURCES.md النهائي + تجديد hashes
- [ ] جلسة اختبارات حرجة (false alarms + adversarial)
- [ ] README العرض (demo screenshots, 5-min pitch script)
- [ ] تحسينات UX بسيطة بناءً على اختبار داخلي
- [ ] CHANGELOG + v0.1.0 tag
- [ ] تجهيز حزمة التسليم (deploy preview + تسجيل)

## المقاييس الحالية
- Backend LoC: ~11.5k Python
- Frontend LoC: ~4.4k TypeScript
- اختبارات: 100+ (أغلبها passing في CI محلي)
- تغطية backend: ~82%

