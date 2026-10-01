# برومت للوكيل المطوّر — بصيرة Upgrade Pack v2

> **رابط التحميل المباشر للحزمة:** https://www.genspark.ai/api/files/s/TenDfUjm
> حمّلها، فكّها، واقرأ `README_UPGRADE_PACK.md` أولًا ثم `docs/07_ZERO_DEFECT_AUDIT.md`.

## السياق
مشروع «بصيرة» (مسار 4 — تحدي الذكاء الاصطناعي في خدمة المحتوى الإسلامي 2026): محقّق حتمي لنقل الآيات والأحاديث. FastAPI + React 19/Vite/TS strict. المبدأ الحاكم: **لا حكم شرعي، لا توليد، كل نص معروض byte-exact من المصدر بمعرّفه، بلطف دائمًا.**

## مهمتك
طبّق الحزمة **كاملة** على المستودود الجديد يوم 4 أكتوبر، ثم أكمل بنود P1 أدناه. لا تغيّر فلسفة الحالات الأربع ولا الثوابت I1–I11.

### 1) التطبيق (ساعة واحدة)
- انسخ `basira_patched/` كأساس المستودع الجديد (أو `patch -p1 < UPGRADE_v2.patch`).
- شغّل: `bash scripts/bootstrap.sh && cd backend && .venv/bin/pytest -q` → يجب **133 passed**.
- `make eval-full` → **150/150، 0 unsafe، 0/500**. `bash scripts/serve.sh` ثم `make scholar` → **18/18**.
- `docker compose up --build` → `/health` يعرض `"boot":"snapshot"` و`rss_mb` < 350.
- **Commits صغيرة متواصلة** برسائل واضحة (المحكّمون يفحصون تاريخ الـcommits). **لا squash.**

### 2) ما يجب أن تعرفه عن الكود الجديد
| ملف | ماذا يفعل | لا تلمس |
|---|---|---|
| `backend/app/state.py` | آلة الحالات. أُضيف I10 (`claimed_ayah_mismatch`) وI11 (`attribution_*`) كـ**ملاحظات فقط** — الحالة لا تتغير | منطق I1–I9 |
| `backend/app/extract/scan.py` | المسح الحتمي للمصحف (4-gram seed + امتداد جشع على فهرس المواضع). `QURAN_SCAN=1`, `QURAN_SCAN_MIN_TOKENS=4` | لا تخفض لـ3 بدون قياس إنذار كاذب على 500 نص نثري |
| `backend/app/extract/rules.py` | `asserted_kind()` يحدد ما تدّعيه الصياغة (قرآن/حديث/لا شيء)؛ مقدّمات إنجليزية؛ فلتر ضوضاء `_is_noise` | |
| `backend/app/snapshot.py` | حفظ/تحميل mmap للمخزن والمسترجع؛ يُبطَل بـsha المدوّنة؛ `LAST_BOOT` لـ`/health` | |
| `backend/app/pipeline.py` | `_quran_sweep`, `_quran_context_notices` (qiraah/partial/basmala), دمج التكرار, `determinism_hash` | ترتيب المراحل |
| `backend/app/main.py` | middleware رؤوس الأمان، خدمة `frontend/dist` من نفس الأصل، حقول health الجديدة | |
| `messages/{ar,en}.json` | 8 مفاتيح ملاحظات جديدة. **كل جملة جديدة تمرّ على المعجم الممنوع** (لا «خطأ/محرّف/صحيح/ضعيف») | |
| `frontend/src/components/QuoteCard.tsx` | متغيرات `claimed_ayah_mismatch` (`found_ref`, `claimed_ref`) | |

### 3) P1 — أكملها يومي 4–5 (بالترتيب)
1. **الواجهة:** اعرض `repeated_spans` كشارة «ورد ×2»؛ أظهر `qiraah_note`/`partial_ayah_context` بأيقونات `brand/icons/info.svg`؛ شارة `extraction_degraded` ظاهرة؛ `determinism_hash` مختصر في تذييل البطاقة مع زر نسخ.
2. **الهوية:** طبّق `brand/css/tokens.css` + `fonts.css` + `head-snippet.html` + `manifest.webmanifest`؛ الشعار `brand/logo/*`؛ الأيقونات من `brand/react/Icon.tsx`. Readex Pro للواجهة، KFGQPC HAFS لنص المصحف (lazy). الحالات الأربع بألوان tokens (needs_review بنفسجي لا أحمر).
3. **صفحات:** `/limits` (من `SAFETY.md §4` + جدول «لماذا تختلف أرقامنا؟»)، `/privacy`, `/api`, `/for-judges` (10 حالات N-* جاهزة للنقر + روابط eval + hash الفهرس + 3 أوامر تشغيل محلي), 404 بالهوية.
4. **SSE streaming** لـ`/v1/check`: أرسل نتائج rules+exact فورًا ثم نتائج LLM. الواجهة تُظهر البطاقات تدريجيًا.
5. **مزوّدان:** Gemini (أساسي) + Groq (بديل) على نفس 50 حالة → جدول في `eval/PROVIDERS.md`.
6. **IslamicEval 2025** بالسكربت الرسمي → `eval/ISLAMICEVAL.md` بصدق كامل.
7. `docs/SCHOLAR_REVIEW.md` (المرشد الشرعي) + `docs/UX_TESTING.md` (3 مستخدمين) — **حقيقيان بأسماء/أدوار وتاريخ**.
8. النشر: رابط حي + UptimeRobot + `/health` عام + خطة مناوبة 7–22 أكتوبر. اختبر من 4G وSafari.

### 4) قبل التسليم (يوم 6، تجميد 14:00)
- [ ] `pytest` 133+ · `make eval-full` · `make scholar` · `npm run build` · `docker compose up` كلها خضراء
- [ ] `CHANGELOG.md` محدَّث يوميًا · `SOURCES.md` مُعاد توليده · لا أسرار (`gitleaks`)
- [ ] فيديو ≤ 2:00 (تحقق بالثانية) يبدأ بالنتيجة · عرض 8 شرائح بالقالب الرسمي بالترتيب المطلوب
- [ ] أجوبة الأسئلة الـ20 (`docs/07 §5`) محفوظة بأسماء ملفات
- [ ] screenshot تأكيد التسليم + خطة B (بريد «تعذر التسليم – رقم المشاركة»)

### 5) قواعد لا تُكسر
- لا تكتب أي نص ديني في الكود أو الرسائل؛ المصدر فقط.
- لا كلمة من المعجم الممنوع في أي رسالة (`self_check_templates` يفشل الإقلاع إن حدث).
- بيانات اصطناعية فقط في الديمو/الاختبارات، معلَّمة `synthetic_badge`.
- لا تذكر أي مستودع/نسخة سابقة. المشروع يبدأ يوم 4.
