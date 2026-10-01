# Basira — Private independent audit / تدقيق داخلي

**ليس مخرجًا للمحكّمين، وليس نسخة تسليم، وليس شهادة سلامة دينية.** هذا مستودع خاص في حساب MoTechSys، لا حساب شخصي للمساعد. تاريخ التدقيق2026-10-01. راجع شروط المصادر قبل إعادة مشاركة الردود أو الصور؛ الحقوق للنصوص والأصول الأصلية باقية لأصحابها. لم تُنسخ قاعدة بيانات كاملة ولا ملفات المنظم الخاصة إلى هذا المجلد.

## التحديث الأحدث: التشكيل القرآني

**البرومت الموحد الحالي يحل محل السابق**؛ أُضيف طلب إظهار الحركات الناقصة والمخالفة، لا حذفها من المقارنة. اقرأ [بحث التشكيل والتجربة التقنية](DIACRITICS_RESEARCH_AR.md) ثم [البرومت الموحد](DEVELOPER_PROMPT_AR.md).

- المثال الحرفي: أربع علامات ضبط ناقصة + علامة وقف؛ الـAPI القديم لم يعرضها، والمقارن التجريبي الجديد يعرضها.
- نتائج المقارن: **58 اختبارًا مركزًا +31,177 فحصًا ميكانيكيًا للسجلات =31,235 تحققًا ناجحًا**. ليست دقة دينية100% ولا اختبارًا مستقلاً معمى، ولا إصلاحًا منشورًا للمنتج.
- [صورة جدول الفروق](evidence/diacritics_example.png)، [صفحة HTML محلية](evidence/diacritics_example.html)، [النتائج النهائية JSON](evidence/diacritics_results.json)، [سجل التشغيل](evidence/diacritics-tests-final.log).
- المصدر الثاني الذي أرسله المستخدم مرجع مقارنة، لا نسخة إملائية مشكولة اعتمدناها رسميًا. اختيار المصدر والقراءة ومحاذاة الرسمين ما زالت بوابات إنتاج إلزامية.
- التنفيذ: `diacritics_engine.py`، الاختبارات: `test_diacritics_engine.py`. المقارن منفصل ولم يعدّل المسوّدة القديمة. التشغيلان السابقان ذوا الإنذارات الزائدة محفوظان للشفافية؛ النتيجة النهائية هي الملف بلا first/second.

لإعادة تجربة التشكيل في بيئة Python مناسبة: ثبّت `regex==2026.7.19` في venv خاص بالتدقيق ثم شغّل:

```bash
python test_diacritics_engine.py /absolute/path/to/prototype/corpus/data/tanzil-uthmani.txt
```

يتحقق البرنامج من SHA256 كامل قبل قراءة6236 سجلًا؛ لا يعيد توزيع corpus. يسجل إصدار Unicode الفعلي. لا تخلط عدد فحوص هذا المقارن مع164 اختبارًا للمنتج القديم أو مع الحالات30.

## ابدأ هنا

1. [التقرير التنفيذي والثوابت والأداء](AUDIT_REPORT_AR.md)
2. [جدول الحالات30: المدخل، المتوقع، الفعلي، PASS/FAIL](CASES_RESULTS_AR.md) — [CSV](cases_results.csv)
3. [سجل العيوب وإعادة الإنتاج والإصلاح والسلامة](BUGS_AND_SAFETY_AR.md)
4. [جرد التسليم والتراخيص والدرجة التقديرية](DELIVERY_AND_SCORES_AR.md)
5. [بريف البناء الجديد والأولويات والخطة](DEVELOPER_BRIEF_AR.md)
6. **[البرومت الجاهز لإرساله للوكيل](DEVELOPER_PROMPT_AR.md)**
7. [الأدلة الخام](evidence/) — [بصمات الملفات](SHA256SUMS.txt)

## خلاصة

- المصدر المدقق: `MoTechSys/Project-Basira` عند `d285bf10e8a23b653b2f739ac7984bfc910afbd3`، دون تعديل تنفيذ المنتج.
- bootstrap أول تشغيل فعلي: نجاح113s؛ backend:164؛ eval الداخلي150/150 و0/500.
- حالات مستقلة:15 PASS/15 FAIL حسب توقعات المهمة6، مع تمييز سياسة الحالة/نقص الوظيفة/الخطر الصامت. لا نسبة إحصائية لأداء العالم الحقيقي.
- ثبت قبول تشكيل مخالف، ومادة دخيلة لاتينية/رقمية، وتجاوز تحقق التكرار. لا تُطلق بناءً على نجاح eval وحده.
- frontend build و8 tests ناجحة، lint فاشل. E2E1 ناجح بعد معالجة مكتبات بيئة المتصفح.
- أول إقلاع26.55s وpeak1071MiB؛ snapshot3.19s وpeak283MiB. `/health.boot_seconds` أقصر لأنه يقيس جزءًا من الإقلاع.
- جميع الاستدعاءات mock. الصورة رُفعت فعلًا، لكن OCR الحقيقي **لم يُقيّم**. لا تكلفة مدفوعة ولا ادعاء جاهزية AI حقيقي.
- تقدير غير رسمي55/100 الآن،87 مشروط بإغلاق العيوب واستكمال الأدلة، لا ضمان ترتيب.

## خريطة الأدلة

| الملفات تحت evidence | ما تثبته |
|---|---|
| environment.txt, python-freeze.txt, index-meta.json | البيئة والإصدارات وبصمة الفهرس |
| bootstrap-actual-first.log | أول تشغيل bootstrap الفعلي الناجح |
| bootstrap-first.log | فشل أداة قياس مفقودة قبل التشغيل؛ ليس فشل منتج |
| make-test.log, test-total.txt | نجاح الأمر و164 اختبارًا مجموعًا |
| eval-full-first.log, internal-eval.json, internal-eval-report.md | نتيجة التقييم الداخلي وتعريفاته |
| health-cold.json, health-warm.json, health-after-load.json | الزمن والذاكرة current/peak |
| cases_actual.json, probes_actual.json, http-audit.log | ردود30 حالة و14 مجسًا إضافيًا |
| performance.json | عينات60 طلبًا وتزامن4 محليًا |
| whitebox_security.json, whitebox-final.log | **النتائج الصحيحة النهائية** للمدقق والمعدل والصور |
| whitebox-invalid-field-attempt.json, whitebox.log | محاولة أداة التدقيق بحقل multipart خاطئ؛422 هنا لا يُنسب للمنتج |
| case28.png | صورة حرفية اصطناعية للحالة28؛ لا توليد نموذج |
| browser_results.json, browser-final.log, browser-case*.png | DOM/XSS/RTL/LTR/قالب الحكم/عرض المصدر |
| browser.log | خطأ تهيئة axe في أداة التدقيق الأولى، وليس المنتج |
| frontend.log | build/test ناجح وlint غير ناجح |
| frontend-e2e.log | نقص مكتبات نظام المتصفح في البيئة |
| frontend-e2e-retry.log | نجاح الاختبار الأصلي بعد توفير المكتبات محليًا |
| delivery-inventory.json | جرد الملفات المتتبعة ذات الصلة |
| completion.json | تحقق نهائي من عدد الحالات، نظافة المصدر وخصوصية الوجهة |

## إعادة الإنتاج

استخدم checkout منفصلًا للمصدر مثبتًا على SHA أعلاه. لا تجعل مجلد audit web root ولا تنشره عامًا. المتطلبات: Python≥3.12، Node22، git، شبكة لتنزيل البيانات والاعتماديات.

```bash
git clone https://github.com/MoTechSys/Project-Basira.git prototype
git -C prototype checkout d285bf10e8a23b653b2f739ac7984bfc910afbd3
cd prototype
bash scripts/bootstrap.sh
LLM_PROVIDER=mock VISION_PROVIDER=mock make test
LLM_PROVIDER=mock VISION_PROVIDER=mock make eval-full
# الأمر السابق يعيد توليد eval/REPORT.md؛ احفظه ولا تخلطه بتعديل تنفيذ.
cd frontend
npm ci
npm run build
npm test
npm run lint  # الفشل المتوقع للنسخة المدققة موثق، لا تخفه
cd ../backend
LLM_PROVIDER=mock VISION_PROVIDER=mock BASIRA_EVAL_KEY=local-audit-only \
  .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

في طرفية أخرى داخل **نسخة قابلة للكتابة من هذا المجلد**، بعد حفظ evidence الأصلية إن أردت عدم استبدالها:

```bash
python3 run_http_audit.py http://127.0.0.1:8000
# متصفح Playwright مع مكتبات نظام التشغيل المناسبة:
node browser_audit.cjs /absolute/path/to/prototype
/absolute/path/to/prototype/backend/.venv/bin/python \
  whitebox_security.py /absolute/path/to/prototype
# الاختبار الأصلي:
cd /absolute/path/to/prototype/frontend
E2E_BASE=http://127.0.0.1:8000 npm run e2e
```

المفتاح `local-audit-only` قيمة اختبار اصطناعية معلنة، **ليس سرًا إنتاجيًا**. لا تفعّله على خدمة عامة. browser_audit ينشئ صورة الحالة28، ثم whitebox يرفعها بالحقل الصحيح `image`. استدعاء API بديل للنص لا يثبت OCR. لا تستخدم scripts/serve.sh دون ضبط provider صراحة؛ قد يفعّل مزودًا حقيقيًا إذا ورث مفاتيح من البيئة.

لإعادة قياس الإقلاع: استخدم أول تشغيل بلا snapshot في checkout/فهرس منفصل، قِس الوقت من إنشاء العملية حتى أول health200، واحفظ `/proc/PID/status` وhealth. أوقف العملية ثم أعد تشغيلها بنفس الإعدادات مع snapshot. لا تحذف بيانات/نسخًا مستخدمة، ولا تسم cache نظام التشغيل الدافئ «باردًا»؛ معيارنا هنا غياب/وجود snapshot فقط.

`run_http_audit.py` يجمع النتائج لا يصدر حكم نجاح آليًا؛ جدول PASS/FAIL مراجعة بشرط التوقعات الموثقة. `whitebox_security.py` اختبارات وحدة وصور وطلبات اصطناعية محدودة، لا إثبات استغلال عن بعد. إعادة تشغيل البرامج تستبدل نتائجها؛ قارنها ببصمات النسخة المرجعية قبل الاستنتاج.

## ما بقي خارج المهمة المنفذة

إصلاح المنتج نفسه، بناء جديد أيام التحدي، اختبار مزود حقيقي/صور مزخرفة، مراجعة علمية موقعة، حسم الحقوق، تجربة مستفيدين، قياس إنتاج وDocker/pentest شامل، وإعداد/رفع عرض وفيديو التسليم. هذه أعمال الوكيل التالي وليست نتائج ادعينا إنجازها. كل ما في هذا المستودع تدقيق داخلي قابل للفحص، والخادم التجريبي مؤقت ويُوقف بعد القياس.
