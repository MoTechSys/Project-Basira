# 01 — التدقيق الداخلي المستقل + بحث التشكيل (Basira-Internal-Audit-20261001)

**المصدر:** `https://github.com/MoTechSys/Basira-Internal-Audit-20261001` · فرع `genspark_ai_developer` · commit `33f823f` (2026-10-01). المستودع **خاص**؛ هذه نسخة كاملة بلا `.git`.
**ما دقّقه:** `MoTechSys/Project-Basira` عند **`d285bf1`** — أي **قبل** دمج حزمتَي A/B (E-039..E-041) وقبل ورشة النتائج (E-042/E-043) وقبل `v4-ui`. بعض ملاحظاته قد تكون تغيّرت؛ README.md الأعلى يحدّد حالة كل عيب على `main` الآن.
**طبيعته:** تقارير + أدلة خام + محرك تجريبي. **لا كود منتج.**

## ترتيب القراءة (كما يطلبه البرومت)
1. `README.md` — ملخص + خريطة الأدلة + أوامر إعادة الإنتاج.
2. `DIACRITICS_RESEARCH_AR.md` — المثال الحرفي (39:53)، ثلاث طبقات لا تُخلط، UAX29/15/53، لماذا strip-diacritics ليس دليلاً.
3. `AUDIT_REPORT_AR.md` — التقرير التنفيذي، الثوابت، الأداء (إقلاع بارد 26.55 s / ذروة 1071 MiB؛ snapshot 3.19 s / 283 MiB).
4. `CASES_RESULTS_AR.md` + `cases_results.csv` — 30 حالة: المدخل، المتوقع، الفعلي، PASS/FAIL (15/15).
5. `BUGS_AND_SAFETY_AR.md` — **B01–B13** بإعادة الإنتاج والسبب (ملف:سطر) والإصلاح المقترح ومعيار القبول. **هذا الملف هو قلب الحزمة.**
6. `DELIVERY_AND_SCORES_AR.md` — جرد التسليم مقابل دليل المسابقة، التراخيص (OHD = ODbL لا MIT؛ HadeethEnc link-mode)، تقدير 55/100.
7. `DEVELOPER_BRIEF_AR.md` — بريف البناء الجديد.
8. `DEVELOPER_PROMPT_AR.md` — نسخة الوكيل من البرومت. **المعتمد هو `_PROMPT_FROM_OWNER.md`** (قارن).

## الكود التجريبي
- `diacritics_engine.py` — مقارن حركات حرفاً-بحرف (grapheme clusters, canonical). **تجربة منهجية، ليس للإنتاج** (بنص البرومت).
- `test_diacritics_engine.py` — 58 اختباراً مركّزاً + فحص ميكانيكي 31,177 سجلاً. يحتاج `regex==2026.7.19` وملف `tanzil-uthmani.txt` (يتحقق من SHA256 قبل القراءة). النصّان الحرفيان للمثال محفوظان فيه — **لا تُعِد صياغتهما**.
- `run_http_audit.py` — يعيد الـ30 حالة + 14 مجساً على `/v1/check`.
- `whitebox_security.py` — المدقق، rate limiter (XFF)، الصور.
- `browser_audit.cjs` — DOM/XSS/RTL/قالب الحكم.

## الأدلة (`evidence/`)
`cases_actual.json` و`probes_actual.json` (ردود API كاملة) · `diacritics_results.json` (النهائي؛ `_first`/`_second` تشغيلان سابقان بإنذارات زائدة محفوظان للشفافية) · `diacritics_old_api.json` (الـAPI القديم: found بلا فروق للنصين) · `diacritics_example.{html,png}` · `whitebox_security.json` · `health-{cold,warm,after-load}.json` · `performance.json` · `browser-case{12,16,20,30}.png` · `SHA256SUMS.txt` لكل الملفات.

## تحليلي (ما استنتجتُه)
- **القيمة:** أعلى حزمة صرامة؛ B01–B05 عيوب سلامة حقيقية وقابلة لإعادة الإنتاج على `main` اليوم (تحقّقتُ من مواضعها في الكود: `seen_loose` في pipeline، تجاوز الحرف الأخير في harakat.py، `verify.py` لا يطابق request slice، `_guard` يثق بـXFF).
- **ما يجب الحذر منه:** الوكيل يوصي ببناء **مستودع جديد** ويعتبر `main` «مسوّدة للتعلّم». هذا قرار استراتيجي للمالك (README §5). لا تنفّذه من تلقاء نفسك.
- **تعارض مع حزمة 02:** 01 يرفض تجاوز TLS لجلب مصدر جديد؛ 02 يجلب Tanzil Simple بـ`-k`. انظر README §3.
- **أرقام يجب ألا تُخلط:** 164 اختبار منتج قديم ≠ 30 حالة تدقيق ≠ 31,235 فحص المقارن التجريبي.

## الخطوة الأولى عند العودة
اكتب اختبارات **فاشلة** لـ B01–B05 في `backend/tests/` من `cases_results.csv` (الحالات 16، HELLO/123، التكرار المزدوج، whitebox proof، 3/13/25/27) — ثم اعرض على المالك قبل أي إصلاح يمس `state.py` أو `harakat.py`.
