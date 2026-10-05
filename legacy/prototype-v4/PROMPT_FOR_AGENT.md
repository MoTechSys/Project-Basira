# برومبت للوكيل — دمج Basira v4

أنت تعمل على مستودع `MoTechSys/Project-Basira00` (main عند `b801da5` أو بعده). المطلوب دمج حزمة **v4** الجاهزة والمختبرة، ثم التحقق والنشر على الخادم الحي.

## 1) اسحب الحزمة
```bash
git clone https://github.com/MoTechSys/Project-Basira00.git /tmp/basira3
ls /tmp/basira3/basira-v4    # README.md  STRATEGY_AR.md  PROMPT_FOR_AGENT.md  apply.sh  patch/  files/  shots/
```
اقرأ `/tmp/basira3/basira-v4/README.md` أولاً، ففيه التحليل البصري (قبل/بعد) وكل قرار.

## 2) طبّق
```bash
cd <Project-Basira00>
bash /tmp/basira3/basira-v4/apply.sh
```
السكربت ينشئ فرع `v4-ui` من `origin/main`، ويطبّق 4 patches بـ `git am --3way`. وإن تعارضت الـ patches، ينسخ الملفات الكاملة من `files/`.
**إن حدث تعارض:** القاعدة أن كود main البعيد مقدَّم، إلا في الملفات الجديدة (`XRay.tsx`، `lib/xray.ts`، `lib/ranges.ts`، `XRay.test.tsx`).

## 3) البوابات: كلها يجب أن تكون خضراء قبل الدمج
```bash
cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy app && .venv/bin/pytest -q   # 130+ passed
cd .. && make eval-full PY=backend/.venv/bin/python     # 150/150 · unsafe 0 · FA 0/500 · variance 0
git checkout eval/REPORT.md                              # eval-full يعيد كتابة التوقيت فقط؛ لا تُدرجه
cd frontend && npx tsc -b && npx oxlint && npx vitest run && npm run build   # 17+ passed, 0 lint errors
```

## 4) ما الذي تغيّر (لا تعدّل المنطق دون سبب)
| الملف | التغيير |
|---|---|
| `backend/app/schemas.py` | `CheckOptions.extract: "full"\|"fast"` (افتراضي full) · `CheckResponse.phase` |
| `backend/app/pipeline.py` | `fast` يتخطى استدعاء نموذج اللغة كلياً؛ **لا تغيير في المطابقة أو القرار** |
| `backend/app/main.py` | دلو تقييد مستقل للمرحلة السريعة (×4)؛ الفحص ثنائي المرحلة = وحدة واحدة من الحد |
| `frontend/src/components/XRay.tsx` + `lib/xray.ts` | «نصك تحت الفحص»: نص المستخدم كاملاً، وكل اقتباس ملوّن بحالته ومرقّم ويقفز إلى بطاقته |
| `frontend/src/components/DiffView.tsx` + `lib/ranges.ts` | الحرف المختلف مؤطّر **داخل** علامة الكلمة (`quote_letters`/`source_letters`)؛ والآيات لا تُقص (`whole`) |
| `frontend/src/components/QuoteCard.tsx` | بطاقة مرقّمة بـ `id`؛ الموضع الأول مفتوح، والبقية في `<details>` |
| `frontend/src/Check.tsx` | `runTwoPhase()`: سريع ثم كامل؛ ولا تظهر «لم نعثر» أثناء المرحلة الكاملة |
| `frontend/src/i18n.ts` · `index.css` | مفاتيح جديدة (ar/en متطابقة) وأنماط v4 (تباين AA في الوضعين) |

## 5) بعد الدمج: تحقق على الخادم الحي (أبلغ بالأرقام كما هي)
1. أعد تشغيل backend وfrontend على 5173.
2. منشور الاختبار: `قرأت اليوم: قال تعالى: ﴿وَقُل رَّبِّ زِدْنِي عِلْمًا﴾، وقال ﷺ: «طلب العلم فريضة على كل مسلم»، وقال تعالى: ﴿إن الله علي كل شيء قدير﴾ وقال ﷺ «إنما الأعمال بالنيات» رواه البخاري`
   - قِس **زمن أول نتيجة** (fast) و**زمن النتيجة الكاملة** على الخادم الحي مع نموذج اللغة الحقيقي.
   - تحقّق أن البطاقة 3 تُظهر الياء مؤطّرة في «علي» والألف المقصورة مؤطّرة في «عَلَىٰ».
   - تحقّق أن «مواضع أخرى للنص نفسه (2 من 11)» مطوية.
3. Lighthouse (جوال وسطح مكتب) على `vite preview`؛ والسابق 99–100. **أبلغ بأي نزول.**
4. axe WCAG 2.2 AA على صفحة **النتائج** (لا الرئيسية فقط) في الوضعين: صفر مخالفات محلياً.
5. نص يحوي آية طويلة (2:282) مع خطأ حرف: يجب أن تُعرض الآية **كاملة**.

## 6) لا تفعل
- لا تغيّر `state.py` أو العتبات أو V1–V5.
- لا تجعل `extract="fast"` افتراضياً في الـ API (أدوات التقييم تعتمد على full).
- لا تستعمل الأحمر على نص المصدر القرآني (قرار شرعي، انظر STRATEGY_AR.md د-7).
- لا تدمج إلى main دون موافقة صاحب المشروع؛ افتح PR من `v4-ui`.

## 7) قرار معلّق لصاحب المشروع (لا تنفّذه دون إذن)
**د-6 في STRATEGY_AR.md:** شارة «وُجد» الخضراء لحديث خارج الصحيحين دون حكم من الموسوعة توحي بصريّاً بالتصحيح. المقترح: لون محايد لهذه الحالة. **انتظر القرار.**
