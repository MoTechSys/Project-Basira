# نص الفكرة كما قُدِّم في التسجيل (حرفيًا)

المشروع: بصيرة · المسار الرابع


المسار الرابع: أدوات المعرفة والتحقق لتمكين المعرِّفين بالإسلام.

**المشكلة:** تنتشر في المحتوى الدعوي المتداول — المنشورات والصور ورسائل المجموعات — آيات محرّفة بكلمة أو أكثر و«أحاديث» لا توجد في كتب الحديث المعروفة، ولا توجد أداة تفحص منشورًا كاملًا وتكشف كل اقتباس فيه على حدة وتُظهر مصدره وحالته. المعرِّف بالإسلام يبحث يدويًا عن كل اقتباس في مواقع متفرقة أو ينشر دون تحقق. وقد بيّنت مهمة IslamicEval 2025 أن النماذج اللغوية تخطئ في اقتباس الأحاديث أكثر من الآيات، وبيّنت دراسة منشورة في مؤتمر FAccT 2025 أن المستخدم لا يُعتمد عليه في تمييز جودة الإجابات الدينية المولَّدة.

**الحل:** «بصيرة» أداة ويب يلصق فيها المستخدم نصًا أو يرفع صورة منشور، فتستخرج كل استشهاد وتطابقه مع نص المصحف (Tanzil) ومتون كتب الحديث (Open-Hadith-Data وموسوعة الأحاديث النبوية HadeethEnc)، وتعرض لكل اقتباس حالة من أربع: وُجد، مع النص الأصلي ومصدره ورقمه؛ مطابقة جزئية، مع الفرق مُظلَّلًا حرفًا بحرف؛ لم يوجد في مصادرنا — وهذا ليس حكمًا عليه — مع الإحالة إلى قواعد التخريج والمختص؛ يحتاج مراجعة. الأداة لا تحكم على صحة أي حديث ولا تُفتي ولا تولّد نصًا شرعيًا؛ كل نص يُعرض من المدوّنة بمعرّفه، وحكم الحديث يُنقل منسوبًا إلى مصدره المرخّص إن وُجد منشورًا. وتُصدر تقرير تحقق يوثّق ما راجعه المعرِّف قبل النشر.

**التقنيات:** نموذج لغوي بمخرجات مهيكلة لاستخراج الاستشهادات وتصنيفها (آية، متن، إسناد، مصدر مُدَّعى)؛ نموذج رؤية لقراءة الصور والخط المزخرف؛ تطبيع عربي ومطابقة حتمية ثم تقريبية بعتبات معلنة؛ استرجاع هجين نصي ومتجهي لترشيح المرشحين؛ مدقّق لاحق يرفض أي مخرج يحوي اقتباسًا لا يطابق المدوّنة حرفيًا؛ واجهة ويب عربية وإنجليزية مفتوحة المصدر. نبني على مكتبة quran-validator مفتوحة المصدر ونتائج IslamicEval 2025 المنشورة، والجديد هو فحص المنشور كاملًا نصًا وصورة، وشمول الأحاديث، والفرق حرفًا بحرف، والقياس المنشور.

**الأثر المتوقع:** خفض زمن التحقق من دقائق لكل اقتباس إلى ثوانٍ لكل منشور، بمصدر قابل للتتبع ودون أي حكم من الأداة. يُقاس بدقة واستدعاء الكشف على مجموعة اختبار موثقة من 150 حالة، ومعدل الإنذار الكاذب على 500 مقطع صحيح، وأداء الكاشف على بيانات IslamicEval 2025 المنشورة مقارنةً بأفضل نتيجة معلنة فيها، مع نشر النتائج كاملة. منتج متكامل يعمل بنهاية 6 أكتوبر، منخفض التكلفة، تستطيع أي جمعية دعوية تشغيله، وامتداده واجهة برمجية تفحص مخرجات أي تطبيق محادثة إسلامي قبل عرضها.

---

## Promise-by-promise audit against `main` (2026-10-01, commit cb73c64 + this file)

Source of truth for «what we promised» is the text above (sha256 `21a3a9b190017512…`). Status is what is *in the repo and measured*, not planned.

| # | Promise in the submitted idea | Status | Evidence |
|---|---|---|---|
| 1 | Paste text **or upload an image** of a post | ✅ | `POST /v1/check`, `POST /v1/check/image` (real OCR via gpt-5.4, `ocr_text` echoed, ADR-003) |
| 2 | Extract **every** citation and match against Tanzil + Open-Hadith-Data + HadeethEnc | ✅ | rules ∪ LLM proposals ∪ corpus-anchored detector (E-039); 3 corpora in `/v1/sources` |
| 3 | Four states: found / partial / **not found ≠ verdict** / needs review | ✅ | `state.py` I1–I11; E-032 neutral slate for not_found; I10 wording follows claimed kind |
| 4 | **Letter-by-letter** highlighted difference | ✅ since E-039 | `match/diff.py::letter_diff` (grapheme-aware, inside replaced words); was word-level before pack B |
| 5 | Never grades a hadith, never issues fatwa, never generates religious text; grade quoted *attributed* to licensed source | ✅ | SAFETY §1.3, verify.py V1–V5, forbidden-lexicon test, `grade_line` from HadeethEnc only; **Q2 open** (full text vs link) |
| 6 | Issue a **verification report** documenting what was reviewed | ⚠ partial | «نسخ التقرير» copies a plain-text report (`buildReport`); no PDF/permalink yet (INTEGRATIONS §3.3) |
| 7 | LLM with structured output classifying ayah / matn / **isnad** / **claimed source** | ✅ since E-039 | JSON-schema extraction + `extract/segments.py` (isnad, claimed_source) — IslamicEval 2026 Task 1 F1 0.6446 (official scorer) |
| 8 | Vision model for images and **ornamental calligraphy** | ⚠ | OCR works on 5 manual-test images; calligraphy not separately measured — needs a labelled mini-set before claiming |
| 9 | Arabic normalisation, **deterministic then approximate** matching with **published thresholds** | ✅ | two-tier normalisation (E-023/E-024), thresholds 0.75/0.70/0.60 in `config.py` + tests at ±0.002 |
| 10 | **Hybrid lexical + vector** retrieval for candidates | ❌ deviates | retrieval is BM25 words + char-trigram CSR only — **no embeddings**, by decision (deterministic, I7 reproducibility; INTEGRATIONS §3.4). Must be stated openly in the deck (D-012). |
| 11 | Post-validator that **rejects any output containing a quote not byte-equal** to the corpus | ✅ | `verify.py`; test injects a forbidden word → rejected |
| 12 | Open-source Arabic/English web UI | ✅ | React 19, RTL/LTR, Lighthouse 99–100/100/100/100, axe 0 (UX_LOG); licence Apache-2.0 placeholder (**Q1 open**) |
| 13 | Build on **quran-validator** and IslamicEval 2025 results | ⚠ | IslamicEval 2025 1A/1B + 2026 T1/T2 run with official scorers ✅; **quran-validator three-way comparison not yet run** (deck slide 8 — STATE NEXT (0)) |
| 14 | Novelty: whole post (text+image), hadith coverage, letter diff, **published measurement** | ✅ | all four present; measurements in `eval/REPORT.md`, `eval/islamiceval/REPORT_*.md` |
| 15 | Metric: precision/recall on **150 documented cases** | ✅ | `make eval-full`: 150/150, recall@found 1.0, precision 1.0, 3 repeats, variance 0 |
| 16 | Metric: false-alarm rate on **500 correct segments** | ✅ | 0/500 |
| 17 | Metric: detector on IslamicEval 2025 **vs best published** | ✅ honest | 1B dev 89.07 vs published test 89.82/88.60/86.14 (not same split — say so); 1A rules 62.96 / +LLM 67.48 vs 90.06 published |
| 18 | Complete product **by end of Oct 6**, low cost, any da'wah org can run it | ✅ on track | boot 23 s (2.3 s with pack A snapshot), 738 MB steady → Lite 4 GB OK (E-038); Docker in pack A pending merge |
| 19 | Extension: **API that checks any Islamic chatbot's output** before display | ⚠ designed | `/v1/check` is that API already; MCP server designed (INTEGRATIONS §3.1), not implemented (**Q5 open**) |

**Deviations to disclose in the deck (D-012):** #10 (no vector retrieval — deliberate), #13 (quran-validator comparison still owed), #8 (calligraphy unmeasured). Everything else is delivered or stronger than promised (#4, #7 were upgraded by pack B).
