# حالة المشروع — بصيرة

> آخر تحديث: 2026-10-04 المساء (نهاية اليوم الأول)
> المشرف: MoTechSys

## ما أُنجز اليوم

### الواجهة الخلفية (backend-agent)
- [x] طبقة الـ schemas (Pydantic v2) — 4 حالات، أربع أنواع اقتباسات
- [x] الـ Config/Settings وتحميل البيئة
- [x] المطبّع العربي + اختباراته
- [x] محرك الحالات مع ثوابت I1-I9 (religious safety invariants)
- [x] موفّرو LLM والرؤية (mock + openai-compat)
- [x] المخزن (store) والفهرس الكسول
- [x] طبقة الاستخراج (extract)
- [x] طبقة الاسترجاع الهجين (retrieve: BM25 + fuzzy)
- [x] طبقة المطابقة الحتمية (match: exact + harakat + window + diff)
- [x] المنسّق (pipeline) + المدقّق اللاحق (verify)
- [x] نقطة الدخول FastAPI + /check + /health

### الذخيرة النصية (corpus-agent)
- [x] manifest.json بـ SHA-256 لكل مصدر
- [x] أسماء السور (114)
- [x] fetch.py لجلب المصادر الأصلية
- [x] build_index.py لبناء الفهرس
- [x] snapshot.py للتحقق من الـ hashes قبل التحميل
- [x] build_fixture.py لبيانات اختبارية حتمية

### الاختبارات (qa-agent)
- [x] test_normalize, test_state, test_providers
- [x] test_pipeline, test_verify, test_api, test_snapshot
- التغطية الحالية: ~70% للـ backend الأساسي

### DevOps (devops-agent)
- [x] Dockerfile متعدد المراحل بتصلّب أمني
- [x] docker-compose.yml
- [x] CI (GitHub Actions) للـ backend + frontend
- [x] scripts/bootstrap.sh + scripts/serve.sh

## المتبقي ليوم غد (الخامس من أكتوبر)
- [ ] الواجهة الأمامية (React + Vite + TS) — frontend-agent
- [ ] وحدات حماية إضافية: guard, english_gate, byok
- [ ] خادم MCP اختياري
- [ ] eval harness + مصفوفة قياس الدقة والاسترجاع
- [ ] الترجمات (messages/ar.json + en.json)
- [ ] فحص SOURCES.md النهائي
- [ ] شاشة التسليم / README جاهز للعرض

## الالتزامات غير القابلة للتفاوض
1. لا إفتاء ولا تخريج ولا توليد نص شرعي
2. المطابقة حتمية بعد التطبيع فقط
3. فشل مغلق (fail-closed) عند أي عدم تطابق hash
4. الـ 4-state إلزامي لكل خرج

