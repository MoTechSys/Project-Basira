# بريف التطوير — بصيرة v2 «احترافي · رسمي · فخم · متجاوب بدقة»

> **إلى:** الوكيل المطوّر · **من:** وكيل التدقيق المستقل · **التاريخ:** 1 أكتوبر 2026
> **الأساس:** تدقيق حي للمستودع commit `c62db17` (تشغيل كامل + 27 اختبارًا عدائيًا + 7 أجهزة + Lighthouse + فحص أمني + استخراج هوية الموقع الرسمي).
> **القاعدة:** كل بند أدناه مرتّب حسب **وزنه في التحكيم × سهولة التنفيذ**. نفّذ بالترتيب. لا تُخفّض الجودة الحالية (97 اختبار، mypy strict، Lighthouse 99/100/96/91) — أي تغيير يجب أن يُبقي `make gates && make smoke && make eval` خضراء.

---

## 0. ما تم التحقق منه ويعمل (لا تلمسه إلا للتحسين)

| المجال | النتيجة المُقاسة |
|---|---|
| Lighthouse (موبايل، build إنتاجي) | **Perf 99 · A11y 100 · BP 96 · SEO 91** — FCP 1.4s، LCP 1.8s، CLS 0.001، TBT 50ms |
| التجاوب | 7 أجهزة (375→1920px): **صفر overflow أفقي** على الصفحة والنتائج |
| الأمان الأساسي | CORS يرفض الأصول الغريبة ✓ · حد 5000 حرف ✓ · لا يُعيد HTML المُدخل (XSS) ✓ · مغلّف أخطاء موحّد ✓ · لا يسجّل نص المستخدم ✓ |
| المحرك | 150/150 · 0 unsafe · 0/500 إنذار كاذب · 97 اختبار · حتمي |
| OCR الحقيقي | 3/3 صور قُرئت بدقة (مع ﷺ و«») |
| i18n | 60 مفتاحًا متطابقة ar/en |

---

## 1. 🔴 الأخطاء الجوهرية الثلاثة (أولوية مطلقة — تمس «الموثوقية 15%» و«التقني 25%»)

### BUG-1 · مُقدِّمة فارغة تُعلَن «وُجد في البخاري» — **خطر شرعي**
**إعادة الإنتاج:** `POST /v1/check` بالنص: `أخرج الطبراني في الأوسط عن أنس قال: قال رسول الله ﷺ: «من قرأ سورة الواقعة كل ليلة لم تصبه فاقة أبداً»` بمزوّد gpt-5.4
**الناتج الحالي:** اقتباس #1 = `قال رسول الله ﷺ:` → **`found 1.00` → صحيح البخاري رقم 7** ← ❌ شارة خضراء فوق حديث مكذوب.
**السبب:** المستخرج LLM يقطع المُقدِّمة كاقتباس مستقل؛ `exact.py` يجدها حرفيًا داخل آلاف الأحاديث؛ `state.py` لا يملك ثابتًا يرفض الاقتباس «الصيغي فقط».
**الإصلاح:**
```
backend/app/extract/formulaic.py (جديد)
  FORMULAIC_TOKENS = {قال, رسول, الله, ﷺ, صلى, عليه, وسلم, النبي, عن, أن, رضي, عنه, عنها, عنهم, تعالى, عز, وجل, سبحانه, وقال, فقال, حدثنا, أخبرنا, روى, رواه, أخرج, أخرجه, في, الأوسط, الكبير, الصغير}
  def is_formulaic_only(tokens_loose) -> bool: return ≥ 0.8 of tokens ∈ FORMULAIC_TOKENS or len<2 after removal
backend/app/pipeline.py: قبل المطابقة → إن formulaic → أسقط الاقتباس (لا يُعرض أصلًا) + flags.dropped_formulaic += 1
backend/app/state.py: ثابت I10 «لا يكون found إذا كان الاقتباس صيغيًا» (دفاع ثانٍ)
tests/test_state.py: 3 حالات (قال رسول الله ﷺ / عن أبي هريرة رضي الله عنه قال / قال تعالى)
eval/cases.yaml: فئة N «formulaic-only» ×8 — متوقع: 0 اقتباسات أو needs_review بلا مطابقات
```

### BUG-2 · تذبذب المستخرج LLM — نفس النص → 1/2/3 اقتباسات
**إعادة الإنتاج:** النص `أحبتي في الله، تذكروا أن النبي ﷺ قال: المؤمن القوي خير وأحب إلى الله من المؤمن الضعيف. وقال تعالى: وما خلقت الجن والإنس إلا ليعبدون. ومن أقوال السلف: من عرف نفسه عرف ربه.` ×3 → `3 / 1 (degraded) / 2`. **الآية اختفت في تشغيل من ثلاثة.**
**الإصلاح:**
1. `openai_compat.py`: `temperature=0`, `seed=20261004`, `response_format={"type":"json_schema","strict":true}` بمخطط صارم (`quotes[]: {text, kind, char_start, char_end}`).
2. `pipeline.py`: **الاتحاد الحقيقي** `rules.extract_spans(text) ∪ llm.extract(text)` — تحقق أن المسار `degraded=True` **لا يُسقط** نتائج rules (الآية هنا لها مُقدِّمة «وقال تعالى:» واضحة ومع ذلك ضاعت → هذا يعني أن rules لم تُدمج عند فشل LLM جزئيًا).
3. **retry واحد** عند `degraded` قبل إعلانه.
4. `eval/run_eval.py --provider real --repeats 3` → انشر **التباين الفعلي** في REPORT.md تحت عنوان «variance with live LLM». إن لم يكن 0، اكتبه بصدق مع نسبته.

### BUG-3 · آية بلا مُقدِّمة تُفوَّت كليًا
**إعادة الإنتاج:** `الحمد لله رب العالمين الرحمن الرحيم مالك يوم الدين` → **0 اقتباسات** (mock وLLM معًا).
**السبب:** الاستخراج يعتمد على مُقدِّمات/أقواس. quran-validator (الذي ذُكر كأساس) يملك `scanUntagged`.
**الإصلاح:**
```
backend/app/extract/untagged.py (جديد)
  مسح نوافذ 5 رموز loose على النص كاملًا ضد store (CSR postings للقرآن موجودة أصلًا — exact.py)
  أي نافذة exact ≥ 5 رموز متتالية → مرشّح {kind: quran, detection: untagged_scan}
  دمج النوافذ المتجاورة في span واحد؛ استبعاد ما يتقاطع مع spans موجودة
  حد أعلى 10 مرشّحين/نص لحماية الأداء
eval/cases.yaml: فئة O «untagged ayah» ×10 (الفاتحة، الإخلاص، آية الكرسي مقطوعة، آية داخل جملة عادية)
false_alarm.py: أضف 100 مقطع نثر عربي عادي بلا آيات للتأكد أن untagged_scan لا يُطلق إنذارات (الهدف 0)
```

### BUG-4 · `degraded=True` بلا توضيح أي جزء لم يُفحص
**الإصلاح:** `CheckResponse.unscanned_ranges: list[[start,end]]` + في الواجهة: تظليل رمادي على تلك النطاقات في معاينة النص + رسالة «لم نتمكن من فحص هذا الجزء — أعد المحاولة أو افحصه يدويًا».

### BUG-5 · ترقيم الحديث غير مفهوم للمعرِّف
«صحيح مسلم، رقم 4283 (ترقيم Open-Hadith-Data)» لا يفيد. المعرِّف يعرف الكتاب/الباب أو ترقيم عبد الباقي.
**الإصلاح (يوم 5):** OHD CSV يحوي عمود الكتاب/الباب لبعض المصنفات → اعرض `كتاب … › باب …` تحت الرقم. وأضف رابط dorar مباشرًا بنص الحديث (موجود) مع نص «ابحث عن الحكم في الدرر».

---

## 2. 🎨 الهوية البصرية — من «نظيف» إلى «فخم رسمي»

### 2.1 التشخيص
الواجهة الحالية: نظيفة، صحيحة، **لكنها generic** (أبيض على بنفسجي فاتح، خط النظام، لا عمق، لا هوية). الموقع الرسمي للتحدي (islamicaich.org) يستخدم: **كحلي عميق متدرّج + توهّجات تركواز/بنفسجي + نمط هندسي إسلامي خافت + زجاجية + خط Readex Pro**. بصيرة يجب أن تبدو **من نفس العائلة البصرية** — المحكّم يرى موقع التحدي ثم موقعك.

### 2.2 نظام الألوان الرسمي (مستخرج من CSS الموقع الرسمي `design-system-B3m3a21J.css`)
```css
/* ضع هذا في frontend/src/tokens.css واستبدل :root الحالي */
:root {
  /* brand */
  --brand-navy:    #12183f;  --brand-navy-deep: #0b0e2d;  --brand-ink-900: #0a081d;
  --brand-violet:  #6251eb;  --brand-violet-2:  #6150ea;  --brand-blue: #39a0fd;
  --brand-teal:    #2ef2c2;  --brand-lilac:     #9b82ff;
  --brand-amber:   #ffc857;  --brand-red:       #ff6b6b;
  /* paper (light) */
  --paper-050: #f7f5fe; --paper-100: #efebfc; --paper-200: #e0d9fb;
  /* semantic — light theme */
  --bg: var(--paper-050); --bg-deep: var(--paper-100);
  --surface: #ffffffb8; --surface-solid: #fff; --glass: #ffffffb8;
  --line: #2d377524; --line-strong: #2d377542;
  --body: #12183f; --heading: #2c3775; --muted: #4a5590; --subtle: #7c85b4; --link: #3f5bd8;
  --success: #0f9d76; --info: #3f5bd8; --warning: #ffc857; --error: #d94a4a;
  /* radius (official) */
  --radius-selector: 10px; --radius-field: 16px; --radius-box: 24px; --radius-pill: 999px;
  /* type */
  --font-ui: "Readex Pro", "IBM Plex Sans Arabic", system-ui, sans-serif;
  --font-quran: "KFGQPC Uthmanic Script HAFS", "Amiri Quran", "Noto Naskh Arabic", serif;
  --font-hadith: "Noto Naskh Arabic", "Amiri", "Scheherazade New", serif;
  --font-mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
}
[data-theme="dark"] {
  --bg: #0e153f; --bg-deep: #0b0e2d;
  --surface: #ffffff0b; --surface-solid: #141c4c; --glass: #00062c66;
  --line: #ffffff1f; --line-strong: #ffffff38;
  --body: #f2f4ff; --heading: #f2f4ff; --muted: #a9b2da; --subtle: #6e78a8; --link: #7fd8f5;
  --success: #2ef2c2; --info: #39a0fd; --warning: #ffc857; --error: #ff6b6b;
}
```
**الحالات الأربع — ألوان دلالية ثابتة في الوضعين:**
| الحالة | لون | أيقونة | ملاحظة |
|---|---|---|---|
| وُجد | `--success` (تركواز/أخضر) | ✓ دائرة | **لا تجعلها «أخضر نجاح» صارخًا** — المعرِّف قد يظن أنه حكم بالصحة. استخدم تركواز هادئًا + نص «مطابق لنص المصدر» |
| مطابقة جزئية | `--warning` كهرماني | ≈ | |
| يحتاج مراجعة | `--brand-violet` | ? | |
| لم يوجد | `--muted` رمادي-أزرق **وليس أحمر** | — | أحمر = «مكذوب» في ذهن المستخدم، والأداة لا تحكم |

### 2.3 الخطوط — استضافة ذاتية إلزامية (لا Google Fonts: الخصوصية + السرعة + العمل بلا إنترنت)
| الاستخدام | الخط | المصدر | الترخيص |
|---|---|---|---|
| واجهة (عربي+لاتيني) | **Readex Pro** (نفس خط التحدي) | fontsource.org/fonts/readex-pro أو Google Fonts → woff2 | OFL |
| بديل واجهة | IBM Plex Sans Arabic | fontsource | OFL |
| **نص المصحف** | **KFGQPC Uthmanic Script HAFS** (مجمع الملك فهد) | qurancomplex.gov.sa/techquran/dev/ أو QUL fonts | مجاني للاستخدام غير الربحي — **وثّقه في SOURCES.md** |
| بديل مصحف | Amiri Quran | github.com/aliftype/amiri | OFL |
| متون الحديث | Noto Naskh Arabic | fontsource | OFL |
**التنفيذ:** `frontend/public/fonts/*.woff2` + `@font-face` مع `font-display: swap` + `<link rel="preload" as="font">` للخطين الأساسيين فقط. `unicode-range` لتقسيم عربي/لاتيني. هذا يعالج تنبيه Lighthouse «render-blocking 150ms».
**⚠️ قاعدة ذهبية:** نص المصحف يُعرض بـ`--font-quran` فقط، **بدون** `letter-spacing` أو `text-transform` أو `font-feature-settings` تغيّر الرسم. الأداة تعد بعرض byte-exact؛ الخط جزء من ذلك.

### 2.4 التخطيط والعمق
1. **Hero/Header:** شريط علوي زجاجي (`backdrop-filter: blur(12px); background: var(--glass)`) بشعار بصيرة + العنوان + مبدّل اللغة + مبدّل الثيم + مؤشر الصحة. خلفية الصفحة: **تدرّج كحلي خفيف من الأعلى + نمط هندسي إسلامي SVG بشفافية 4%** (ثُمانية نجمية بسيطة — ارسمها كـSVG pattern 120×120، لا صورة). في الوضع الفاتح: `--paper-050` مع النمط بـ`--brand-navy` 3%.
2. **بطاقة الإدخال:** `--radius-box` 24px، ظل ناعم متعدد الطبقات (`0 1px 2px #12183f0a, 0 8px 24px #12183f0f`)، حدّ 1px `--line`. حالة التركيز: حلقة `--brand-violet` 2px + توهّج خفيف.
3. **بطاقات النتائج:** شريط جانبي ملوّن 4px بلون الحالة (`border-inline-start`) + شارة الحالة pill في الزاوية + النص المقتبس بخط الحديث/المصحف بحجم 20px + المصدر في بطاقة داخلية `--bg-deep`.
4. **Diff:** جنبًا إلى جنب على ≥768px، **متراكب عموديًا على الموبايل** مع عنوان «نصك / نص المصدر». تظليل الفرق: خلفية `#ffd9d9`→ في الداكن `#ff6b6b33`؛ **وأضف تسطيرًا متموجًا** (`text-decoration: wavy underline`) حتى لا يعتمد التمييز على اللون وحده (WCAG 1.4.1).
5. **حركة:** `prefers-reduced-motion` محترم. ظهور البطاقات بـ`fade+translateY 8px` 240ms متدرّج 40ms. شريط تقدم رفيع تحت الهيدر أثناء الفحص (لا spinner كبير).
6. **Skeleton:** أثناء الفحص (2–8 ث مع LLM) اعرض 2–3 بطاقات هيكلية بدل الفراغ.
7. **Empty state:** عند فتح الصفحة، 3 أمثلة قابلة للنقر («جرّب: آية صحيحة / حديث مشهور لا أصل له / آية بخطأ شائع») — يملأ النص ويفحص. **هذا أهم عنصر للمحكّم في أول 10 ثوانٍ.**

### 2.5 مكوّنات ناقصة
| المكوّن | لماذا | التفاصيل |
|---|---|---|
| **مبدّل داكن/فاتح** | الموقع الرسمي داكن؛ المحكّمون غالبًا يعرضون على شاشة كبيرة | `data-theme` على `<html>` + localStorage + يحترم `prefers-color-scheme` |
| **تقرير التحقق القابل للتصدير** | وعد في الفكرة؛ الحالي «نسخ نص» فقط | زر «تصدير PDF» عبر `window.print()` + `@media print` مُصمَّم (شعار، تاريخ، hash الفهرس، كل اقتباس بحالته ومصدره، تذييل «لا يحكم»). + زر «نسخ Markdown». + **JSON** للمطوّرين |
| **منطقة إفلات الصور** | الحالي زر فقط | drag-and-drop على بطاقة الإدخال كاملة + لصق صورة من الحافظة (`paste` event) + معاينة مصغّرة + زر إزالة |
| **عدّاد زمن الفحص** | المعيار: «خفض الزمن من دقائق إلى ثوانٍ» — أثبته بصريًا | «فُحص 4 اقتباسات في 3.2 ث» في رأس النتائج |
| **صفحة `/limits` «حدودنا»** | درجة 5 في الموثوقية: «يكشف حدود معرفته وأخطاءه» | قائمة صادقة: لا نحكم على الصحة؛ OCR قد يُطبّع الإملاء؛ المستخرج قد يفوّت (نسبة X% من eval)؛ المصادر 9 كتب فقط؛ الأخطاء التي وجدناها وأصلحناها بتاريخها |
| **صفحة `/api` للمطوّرين** | وعد «واجهة برمجية لتطبيقات المحادثة» | FastAPI يولّد `/docs` تلقائيًا — اربطها + مثال curl + مثال Python 5 أسطر + حدود المعدل |
| **تذييل رسمي** | رسمية | شعار التحدي (مسموح للمشاركة فقط، وفق البند 19) + «مشاركة في تحدي الذكاء الاصطناعي في خدمة المحتوى الإسلامي 2026 — المسار الرابع» + روابط المصادر + الترخيص + GitHub |
| **Toast للأخطاء** | الحالي شريط أحمر ثابت | toast قابل للإغلاق مع إجراء («أعد المحاولة») |

---

## 3. 🔒 الأمان والصلابة (ما يفحصه المحكّم التقني)

### 3.1 رؤوس الأمان — **مفقودة كليًا** في الخلفية
```python
# backend/app/security_headers.py — middleware
Content-Security-Policy: default-src 'self'; img-src 'self' data: blob:; font-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self' <API_ORIGIN>; frame-ancestors 'none'; base-uri 'self'; form-action 'self'
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
Cross-Origin-Opener-Policy: same-origin
Strict-Transport-Security: max-age=31536000; includeSubDomains   # فقط خلف HTTPS
Cache-Control: no-store   # على /v1/check* (نص المستخدم لا يُخزَّن حتى في cache)
```
وللواجهة الثابتة (Cloudflare Pages): ملف `_headers` بنفس القيم.

### 3.2 P1 المفتوحة من مراجعة الأمان (gpt-6-astra) — نفّذها
1. `X-Forwarded-For`: اقرأه فقط من `TRUSTED_PROXIES` (env) وإلا `request.client.host`.
2. محدّد المعدل: سقف 10,000 مفتاح + تنظيف LRU؛ عند الامتلاء ارفض الجديد بـ429.
3. `log.exception` → سجّل اسم الفئة فقط.
4. حدود الحجم قبل تحليل الجسم: `Content-Length` check في middleware + حد 10 MB للصور قبل القراءة.
5. **MIME sniffing للصور:** لا تثق بـ`content_type` — افحص magic bytes (PNG `89504E47`, JPEG `FFD8FF`, WebP `52494646…57454250`).

### 3.3 صلابة إضافية
- **Timeout** للـLLM/Vision 20 ث → إن تجاوز: `degraded=True` + نتائج rules فقط (لا 5xx أبدًا).
- **Circuit breaker:** 5 أخطاء متتالية من المزوّد → تعطيل 60 ث + `providers.llm: "mock (circuit open)"` في `/health`.
- `/health` يُرجع `index_sha256` و`build_sha` و`uptime_s` — المحكّم يتحقق أن الديمو هو نفس الكود المُسلَّم.
- **Request ID** في كل استجابة + في رسائل الخطأ للمستخدم («رقم الطلب: abc123 — أرفقه عند الإبلاغ»).
- **robots.txt** صالح (Lighthouse SEO اشتكى) + `sitemap.xml` + `manifest.webmanifest` + أيقونات 192/512 + `apple-touch-icon` + OG image 1200×630 بالهوية (لـWhatsApp/Twitter preview — المحكّمون يتشاركون الرابط!).

### 3.4 الذاكرة والنشر
- RSS **1,036 MB** → لا يعمل على Render Free (512). خيارات: (أ) `retrieve/index.py` trigram CSR streaming (هدف <600 MB)؛ (ب) حفظ المصفوفات كـ`.npy` memory-mapped (`np.load(mmap_mode='r')`) → RSS ينخفض لـ~300 MB فوريًا؛ (ج) Oracle Cloud Always-Free (24 GB ARM) أو Fly.io 1 GB. **نفّذ (ب) أولًا — ساعة عمل، أثر ضخم.**
- وقت الإقلاع 25 ث → `/health` 503 حتى الجاهزية ✓ موجود. أضف `readiness` منفصلًا عن `liveness`.
- **Keep-alive:** UptimeRobot/Cron-job.org كل 5 دقائق على `/health` طوال 4–22 أكتوبر.
- **مزوّد LLM للإنتاج:** `OPENAI_BASE_URL` الخاص بـGenspark **غير متاح خارج sandbox**. اختبر Groq (مجاني، llama-3.3-70b، JSON mode) أو Gemini Flash كمزوّد ثانٍ **اليوم**. وثّق التكلفة/منشور في `docs/COST.md`.

---

## 4. 📱 التجاوب الدقيق (يعمل الآن بلا overflow — هذه تحسينات «قوة»)
1. **Breakpoints:** 360 / 600 / 900 / 1200 / 1600. على ≥1200 اعرض الإدخال والنتائج **عمودين** (الإدخال ثابت يسارًا/يمينًا حسب الاتجاه، النتائج تتمرر).
2. **Safe areas:** `padding: env(safe-area-inset-*)` للـiPhone notch + `viewport-fit=cover`.
3. **Dynamic viewport:** `min-height: 100dvh` بدل `100vh` (مشكلة شريط Safari).
4. **زر الفحص على الموبايل:** ثابت أسفل الشاشة (sticky) بعرض كامل عند وجود نص.
5. **أهداف اللمس:** روابط التذييل (62×19px) تحت 24px → ارفع `padding-block` إلى 6px ليصبح ≥24. الباقي ✓.
6. **الخط المتجاوب:** `font-size: clamp(16px, 1vw + 14px, 18px)` للنص؛ نص المصحف `clamp(20px, 1.4vw + 16px, 26px)`.
7. **الصور عالية الكثافة:** شعار SVG فقط؛ OG image بنسختين 1x/2x.
8. **اختبار LTR/EN:** بدّل للإنجليزية وتأكد أن الـdiff وأشرطة الحالة تنعكس صحيحًا (`border-inline-start` ✓ لكن تحقق من الأيقونات ذات الاتجاه).
9. **Playwright E2E** على 3 أجهزة (iPhone SE، iPad، Desktop) × 2 لغة × 2 ثيم = 12 لقطة في CI كـvisual regression.

---

## 5. 📄 ملفات التسليم الإلزامية (المخرج 5 من الدليل + البند 9 من الشروط) — **كلها مفقودة**
| الملف | المحتوى |
|---|---|
| `LICENSE` | Apache-2.0 |
| `SOURCES.md` | **مولَّد من manifest.json** + لكل مصدر: الاسم، الإصدار، sha256، الرابط، الترخيص الحرفي، **كيف نستخدمه** (Tanzil: التطبيع للبحث فقط والعرض byte-exact؛ HadeethEnc: وضع link بلا تضمين؛ OHD: display مع إشعار الترقيم)، تاريخ الجلب |
| `SAFETY.md` | الثوابت I1–I10 بلغة بشرية + ما لا تفعله الأداة + مستويات الحزمة العلمية (أ/ب/ج/د) وأين تقف بصيرة (أ فقط) |
| `AI_USAGE.md` | البند 9 حرفيًا: كل نموذج (gpt-5.4 للاستخراج/OCR، أي نموذج آخر)، الغرض، التاريخ، الترخيص/الشروط، **تصريح: لا يولّد النموذج أي نص ديني** |
| `THIRD_PARTY_NOTICES.md` | كل حزمة npm/pip بترخيصها (`pip-licenses`, `license-checker`) + الخطوط |
| `docs/API.md` | OpenAPI + أمثلة |
| `docs/ARCHITECTURE.md` | رسم C4 مستوى 2 (Mermaid) + تدفق الطلب + أين كل ثابت |
| `docs/COST.md` | RAM، CPU، تكلفة/منشور لكل مزوّد، تكلفة شهرية لجمعية بـ1000 فحص/يوم، البديل المجاني |
| `docs/LIMITS.md` | نفس محتوى صفحة `/limits` |
| `CHANGELOG.md` | Keep a Changelog |

---

## 6. 📊 القياس المُقنع (45% من الدرجة)
1. **فئات جديدة في eval:** N (formulaic) ×8، O (untagged) ×10، **R (realistic) ×50** — أنماط منشورات دعوية حقيقية مُعاد صياغتها اصطناعيًا: «تذكير اليوم»، «انشرها تؤجر»، أدعية مركّبة، أحاديث مشهورة لا أصل لها (الدرر السنية تنشر قوائم — استخدم **المتن المشهور** فقط)، آيات بأخطاء إملائية شائعة (علي/على، شيئ/شيء، إنشاء الله).
2. **تجربة المقارنة** `eval/COMPARISON.md`: نفس الـ50 حالة على (أ) quran-validator الأصلي (ب) ChatGPT/Gemini بسؤال «هل هذا صحيح؟» → جدول: الدقة، الاستدعاء، **عدد المرات التي أكّد فيها المنافس حديثًا لا أصل له**. هذا يحوّل جدول «الابتكار 15%» من ادعاء إلى دليل.
3. **تشغيل بالمزوّد الحقيقي ×3** مع نشر التباين.
4. **IslamicEval 2025:** شغّل الكاشف على test set الرسمي (gitlab.com/bigirqu/quran-hadith-qa-2025) بسكربت التقييم الرسمي من مستودع BurhanAI → انشر F1 مقابل 90.06%. **حتى لو أقل، النشر الصادق = درجة 5 في «وضوح العرض وإتاحة التحقق».**
5. **اختبار مستخدمين:** 3 معرِّفين × 10 دقائق → `docs/UX_TESTING.md` (زمن المهمة، ما لم يُفهم، ما غُيِّر).

---

## 7. ✅ معايير القبول لهذا البريف (Definition of Done)
- [ ] BUG-1..3 مُصلحة باختبارات؛ الاختبارات الـ27 في `docs/evidence/adversarial_probe.py` (مستودع التدقيق) **كلها تمر**
- [ ] `make gates && make smoke && make eval-full` خضراء
- [ ] Lighthouse موبايل ≥ 95/100/95/95 بعد إضافة الخطوط والهوية
- [ ] `curl -I` على الخلفية يُظهر 7 رؤوس أمان
- [ ] 12 لقطة Playwright (3 أجهزة × 2 لغة × 2 ثيم) بلا overflow وبأهداف لمس ≥24px
- [ ] RSS < 600 MB أو خطة نشر موثقة تتحمل 1 GB
- [ ] الملفات الـ10 في §5 موجودة
- [ ] `/limits` و`/api` و`/docs` تعمل
- [ ] صفحة أولى بـ3 أمثلة قابلة للنقر + تصدير PDF يعمل
- [ ] الديمو يعمل من شبكة خارجية **بمزوّد LLM غير Genspark**

---
*أدلة التدقيق: لقطات 7 أجهزة + Lighthouse JSON + سكربت الاختبارات في مستودع التدقيق `docs/evidence/`.*
