# بصيرة (Basira) — أداة التحقق من الاقتباسات القرآنية والحديثية

مشاركة في **تحدي الذكاء الاصطناعي في خدمة المحتوى الإسلامي 2026** (IslamicAIch.org) — المسار الرابع: أدوات المعرفة والتحقق لتمكين المعرِّفين بالإسلام.

## الوثائق
- [`docs/01_hackathon_analysis.md`](docs/01_hackathon_analysis.md) — تحليل كامل للتحدي: المسارات، الجوائز، الخط الزمني، معايير التحكيم، الشروط
- [`docs/02_submitted_idea_verbatim.md`](docs/02_submitted_idea_verbatim.md) — نص الفكرة المُقدَّم حرفيًا + قائمة الالتزامات
- [`docs/03_claims_verification.md`](docs/03_claims_verification.md) — التحقق من كل ادعاء ومصدر مذكور في الفكرة
- [`docs/04_repo_audit_Project-Basira.md`](docs/04_repo_audit_Project-Basira.md) — **تدقيق مستقل لمستودع MoTechSys/Project-Basira**: 27 اختبارًا عدائيًا، 3 أخطاء جوهرية، مطابقة المعايير، خطة الفوز
- [`docs/05_DEV_BRIEF_for_agent.md`](docs/05_DEV_BRIEF_for_agent.md) — **بريف التطوير للوكيل المطوّر**: الأخطاء الثلاثة، الهوية البصرية الرسمية (tokens مستخرجة)، الأمان، التجاوب، ملفات التسليم، القياس
- [`docs/06_MASTER_BRIEF_first_place.md`](docs/06_MASTER_BRIEF_first_place.md) — **البريف الرئيسي للمركز الأول**: تحليل القالب الرسمي حرفيًا، معايير Google/DGA/WCAG 2.2/i18n، 10 ابتكارات، سيناريو الفيديو، 8 شرائح، 10 أسئلة متوقعة
- [`handoff/template/`](handoff/template/) — القالب الرسمي + أصول الهوية المستخرجة (خلفيات، شعارات، أيقونات)
- [`docs/evidence/`](docs/evidence/) — لقطات 7 أجهزة + الموقع الرسمي + Lighthouse + سكربت الاختبارات العدائية
- [`handoff/`](handoff/) — دليل المشارك الرسمي (PDF) ونصه المستخرج

## الحالة
- 1 أكتوبر 2026: توثيق وتحليل. حزمة `basira_handoff_v1.3.zip` انتهت صلاحيتها على tmpfiles.org — بانتظار إعادة الرفع.

- `docs/07_ZERO_DEFECT_AUDIT.md` — تدقيق «صفر مآخذ»: أدبيات التحكيم العالمية + IslamicMMLU + 28 اختبارًا بعين شرعية (6 ثغرات) + 9 ملفات إلزامية غائبة + 20 سؤالًا بأجوبة

## 🎨 brand/ — الهوية البصرية (v1.0)
- `brand/src/` مصادر SVG (العلامة، التراكيب، 40 أيقونة) · `brand/dist/` الحزمة النهائية المحسَّنة (شعار، أيقونات، سبرايت، React، tokens.css، خط woff2، favicon/PWA/OG، manifest، head-snippet، preview.html)
- البناء: `npx svgo -f brand/src -o brand/dist --config brand/svgo.config.mjs` · `python3 brand/tools/build_og.py`
- الحزمة المضغوطة تُولَّد بـ `cd brand/dist && zip -r -9 ../basira_brand_kit_v1.0.zip .`
- `docs/10_UX_SPEC_inline_highlight_progressive_share.md` — مواصفة UX تنفيذية: تظليل داخل النص، استجابة تدريجية، بطاقة الجوال، الرئيسية الحية، PDF/مشاركة/QR، a11y.
- `docs/11_FULL_SPECTRUM_ANALYSIS_v2.1.md` — التحليل الشامل v2.1: تحديثات الشروط (§8 baseline، §9 سجل المصادر)، IslamicEval 2026 + مسح يونيو 2026، ما بُني فعلًا، أمن/أداء/شرعي، قائمة التسليم النهائية.
- `upgrade/basira_patched/` — الشجرة المرقّعة v2.1 (كود حقيقي backend + frontend + اختبارات). ابدأ من `upgrade/basira_patched/INTEGRATION_v2.1.md`.
