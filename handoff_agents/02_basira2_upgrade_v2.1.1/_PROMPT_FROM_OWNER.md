# البرومت كما أرسله المالك (حرفياً، 2026-10-01) — يرافق حزمة Project-Basira2 @ 63dfda6

> ملاحظة الوكيل الموثِّق: منقول حرفياً من رسالة المالك. لا تعديل.

---

# مهمة: دمج ترقية بصيرة v2.1.1 في المستودع الرئيسي

## المصدر (اقرأ بالترتيب)
المستودع: https://github.com/MoTechSys/Project-Basira2 — فرع `main` — commit `63dfda6`
(خاص؛ استخدم صلاحية الفريق.)

1. `upgrade/basira_patched/INTEGRATION_v2.1.md` — دليل الدمج ملفًا-ملفًا (الأقسام 0، 0b، 1، 2، 3). هذا هو المرجع التنفيذي.
2. `upgrade/basira_patched/CHANGELOG.md` — ما تغيّر ولماذا (E-030 إلى E-038).
3. `upgrade/basira_patched/SAFETY.md` — الثوابت I1–I16 واختباراتها.
4. `docs/11_FULL_SPECTRUM_ANALYSIS_v2.1.md` §8 — قائمة التسليم الإلزامية من الشروط.
5. `docs/10_UX_SPEC_inline_highlight_progressive_share.md` — مواصفة UX (مرجع لما بُني ولما بقي).

## ما في الشجرة `upgrade/basira_patched/`
نسخة مرقّعة كاملة من `c62db17`. **لا تنسخها فوق `main` بالجملة** — `main` تحرّك (كاشف ضمني، GS2/G2، وضع ليلي، علامة). رحّل ملفًا-ملفًا كما في INTEGRATION.

### Backend
- `app/csp.py` (جديد) + 3 hunks في `main.py`: CSP بـ nonce لكل طلب يُختم على `<script>` المضمّنة.
- `app/schemas.py`: `CheckOptions.stage`, `CheckResponse.extraction_stage`, `HarakatConflict`, `Match.harakat_*`, `SplicePart`, `QuoteResult.splice_parts`.
- `app/pipeline.py`: `_extract(text, stage)`, `_harakat()`, `_splice()`, `_ayah_labels()`.
- `app/match/harakat.py` (جديد) — مقارنة الحركات حرفًا-بحرف ضد المصحف المشكول (E-037).
- `app/match/splice.py` (جديد) — تفكيك الاقتباس المركّب من آيات متفرقة (E-038).
- `app/store.py`: `Record.text_vocalized` من حقل `tv`.
- `corpus/manifest.json`: مصدر جديد `tanzil_simple` (Tanzil Simple vocalized، sha256 `f3268cfe…`).
- `corpus/build_index.py`: `build_tanzil(..., src_voc)` يكتب `tv` بعد التحقق من المحاذاة.
- `messages/{ar,en}.json`: `harakat_conflict`, `harakat_consistent`, `spliced_quote` (متغير `{n}`).
- اختبارات: `tests/test_api.py` (CSP ×2)، `tests/test_scholar_lens.py` (stage ×2)، `tests/test_harakat.py` (26).
- `Dockerfile`: نسخ `brand/` اختياري. `BASELINE.md`, `RUNBOOK.md` قوالب جديدة.

### Frontend
انسخ كما هي: `src/components/{AnnotatedText,AyahText,ProgressiveStatus,HarakatView}.tsx`, `src/useProgressiveCheck.ts`, `src/share.ts`, `src/print.css`, `src/ux_v21.test.tsx`, `src/__fixtures__/check_response_harakat.json`.
ادمج: `src/api.ts`, `src/i18n.ts` (كتلة v2.1 في ar وen)، `components/{QuoteCard,DiffView}.tsx`, `Check.tsx` (INTEGRATION §3)، `index.css` (الكتل المضافة)، `main.tsx`.

## القواعد
1. حافظ على أرقامكم: Lighthouse ≥99 جوال، axe صفر، أهداف ≥24px، 320–1440 بلا تجاوز أفقي، JS ≤ 90 kB gz (الحزمة الآن 85.84).
2. نص المصدر بايت-ببايت؛ لا تصحيح تلقائي؛ لا تخزين؛ «لم يوجد» رمادي.
3. الحالة الأربعية لا تتغير بسبب الحركات أو التركيب (I14، I16) — تنبيه وصفي فقط.
4. النهائي يستبدل الأولي كاملًا؛ النسخ/المشاركة/PDF معطّلة حتى النهائي.
5. داخل `_extract`: استدعِ كاشفكم الضمني فقط عند `stage=="full"`.
6. أضف مصفوفات GS2/G2 إلى `snapshot._ARRAYS`.
7. قبل أول commit يوم 4 أكتوبر: `git tag baseline-2026-10-04` واملأ `BASELINE.md` (الشروط §8).

## اختبارات القبول بعد الدمج (كلها يجب أن تمرّ)
```bash
make fetch && make index                      # يجلب tanzil-simple.txt ويكتب tv (tanzil.net: شهادة TLS منتهية 2026-10-01 → -k موثّق في fetch.py)
cd backend && pytest -q && ruff check app tests && mypy app
python eval/run_eval.py --index corpus/index --repeats 3 --false-alarm 500 --fail-on-unsafe   # 150/150, FA 0/500
PYTHONPATH=backend python ../docs/evidence/harakat_fa_check.py corpus/index                   # self=0, uthmani-vs-voc=0
cd frontend && npm test && npx tsc -b && npm run build
curl -s -D - -o /dev/null localhost:8000/ | grep -i content-security-policy                    # يحتوي 'nonce-'
```
