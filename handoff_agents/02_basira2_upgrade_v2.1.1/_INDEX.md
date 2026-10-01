# 02 — حزمة الترقية Basira2 v2.1.1 (Project-Basira2 @ 63dfda6)

**المصدر:** `https://github.com/MoTechSys/Project-Basira2` · `main` · **`63dfda6`** (16 commit، كلها 2026-10-01). خاص. نسخة كاملة بلا `.git` وبلا نسختي `official_template.pptx` (9.5 MB ×2؛ في المستودع الأصلي).
**طبيعته:** (أ) شجرة مرقّعة كاملة `upgrade/basira_patched/` مبنية على **`c62db17`** (قاعدة أقدم من `main`) — تمرّ بوّاباتها على قاعدتها هي؛ (ب) 11 وثيقة تحليل؛ (ج) هوية بصرية؛ (د) مواد المنظّم.

## الخريطة
| المسار | ماذا | حالته |
|---|---|---|
| `upgrade/basira_patched/INTEGRATION_v2.1.md` | **دليل الترحيل ملفاً-ملفاً** (§0 ما تغيّر عن Pack A، §0b E-037/E-038، §1 backend، §2 frontend، §3 Check.tsx، §4 ما بقي) | المرجع التنفيذي |
| `upgrade/basira_patched/{CHANGELOG,SAFETY,SOURCES,AI_USAGE,SECURITY}.md` | E-030..E-038، الثوابت **I1–I16** | I14–I16 جديدة غير مدموجة |
| `upgrade/basira_patched/{BASELINE,RUNBOOK}.md` | قوالب Terms §8/§13 | غير مدموجة؛ الوسم يوم 4 أكتوبر |
| `upgrade/basira_patched/backend/app/match/harakat.py` | **E-037** حركات حرفاً-بحرف ضد Tanzil Simple المشكول (`tv`) — equal/unvocalized/conflict/skeleton؛ لا يغيّر الحالة الأربعية (I14) | **غير مدموج — ⚠️ نفس اسم ملف موجود على main بمنطق مختلف (حزمة B)** |
| `upgrade/basira_patched/backend/app/match/splice.py` | **E-038** تفكيك اقتباس مركّب من ≥2 مقطع قرآني (greedy longest-run، MIN 2 tokens، ≤4 أجزاء) — I16 | غير مدموج؛ يحل B09/الحالة 19 |
| `upgrade/basira_patched/backend/app/{pipeline,schemas,store}.py` | `_harakat()`, `_splice()`, `_ayah_labels()`, `HarakatConflict`, `Match.harakat_*`, `SplicePart`, `Record.text_vocalized` | غير مدموج (الـstage مدموج في v4-ui) |
| `upgrade/basira_patched/corpus/{manifest.json,build_index.py}` | مصدر `tanzil_simple` sha256 `f3268cfe…`؛ `build_tanzil(..., src_voc)` يكتب `tv` بعد تحقق المحاذاة | غير مدموج؛ **يحتاج قرار `-k`** |
| `upgrade/basira_patched/backend/tests/test_harakat.py` | 26 اختباراً | غير مدموج |
| `upgrade/basira_patched/backend/app/csp.py` + hunks main.py | CSP nonce | **مرفوض** (E-044؛ نعتمد hash E-041) |
| `upgrade/basira_patched/frontend/src/components/HarakatView.tsx` + `__fixtures__/check_response_harakat.json` | عرض تعارض الحركات حرفاً-بحرف | غير مدموج |
| `upgrade/basira_patched/frontend/src/{components/AnnotatedText,AyahText,ProgressiveStatus}.tsx, useProgressiveCheck.ts, share.ts, print.css, ux_v21.test.tsx` | UX v2.1 | **مدموج مكيَّفاً في v4-ui** (E-044..E-046) — لا تُعِد |
| `docs/01..11_*.md` | تحليل المسابقة، الفكرة حرفياً، تحقق الادعاءات، تدقيق المستودع، بريفان، zero-defect audit، برومتان، UX spec، التحليل الشامل | مرجعية؛ **docs/11 §8 = قائمة التسليم الإلزامية** |
| `docs/evidence/` | لقطات 7 أجهزة، Lighthouse، `harakat_fa_check.py` (self=0, uthmani-vs-voc=0)، `harakat_{desktop,mobile}_35_28.png` | أدلة |
| `brand/{src,dist,tools}` | هوية v1.0: 40 أيقونة، tokens.css، خط، OG، manifest | **مطبّقة سابقاً** على الواجهة |
| `handoff/` | دليل المشارك PDF + نصه؛ أصول القالب الرسمي | **مواد المنظّم — لا تُنشر** |

## أوامر القبول التي يطلبها البرومت (لم تُشغَّل بعد على main)
```bash
make fetch && make index          # يجلب tanzil-simple.txt (TLS منتهية → -k) ويكتب tv
cd backend && pytest -q && ruff check app tests && mypy app
python eval/run_eval.py --index corpus/index --repeats 3 --false-alarm 500 --fail-on-unsafe
PYTHONPATH=backend python handoff_agents/02_basira2_upgrade_v2.1.1/docs/evidence/harakat_fa_check.py corpus/index   # self=0, uthmani-vs-voc=0
cd frontend && npm test && npx tsc -b && npm run build
```
(سطر `grep nonce-` من البرومت **لا ينطبق** — نحن على hash؛ البديل: `test_csp_hashes_cover_only_executable_inline_scripts` في `backend/tests/test_api.py`.)

## تحليلي
- **أعلى قيمة غير مدموجة:** E-037 + E-038. يجيبان مباشرة على طلب المالك «كل حرف وحركة ظاهران» وعلى B09.
- **خطر الدمج الأعمى:** الشجرة من `c62db17`؛ `main` تقدّم 12+ commit (كاشف المرتكزات، GS2/G2، snapshot v3، ورشة النتائج). **النسخ الكلي ممنوع** — البرومت نفسه يقول ذلك.
- **تعارض `harakat.py`:** محرك حزمة B (على main، E-039: `skeleton`/`word_conflicts`، يتجاوز الحرف الأخير) ≠ محرك E-037 (مقارنة ضد نص مشكول كامل `tv`). يجب اختبار الحالة 16 (35:28) و39:53 على كليهما قبل الاختيار أو التوحيد. **لا تستبدل الملف بلا هذا الجدول.**
- **I14/I16** تقول: الحركات/التركيب لا يغيّران الحالة الأربعية — متسق مع فلسفتنا؛ لكن حزمة 01 §3 تقول «لا تمنح اكتمالاً أخضر مع نقص ضبط في وضع تدقيق النشر» — **تعارض سياسة** يحسمه المالك/ADR (README §3).
- أرقام الحزمة (133 pytest، 85.84 kB) **على قاعدتها**؛ لا تنقلها كأرقام `main`.

## الخطوة الأولى عند العودة
1. قرار المالك على `-k`/مصدر Tanzil Simple. 2. جدول المقارنة الثلاثي لمحركات الحركات. 3. ثم ترحيل E-037 ملفاً-ملفاً على فرع `harakat-v2` بنفس بوّابات PR #2، ثم E-038.
