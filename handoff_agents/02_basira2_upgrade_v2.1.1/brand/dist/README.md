# بصيرة — Basira · Brand Kit v1.0

هوية بصرية كاملة، مبنية **حرفيًا على القالب الرسمي** لتحدي الذكاء الاصطناعي في خدمة المحتوى الإسلامي 2026
(ألوان `#12183F / #6150EA / #2EF2C2 / #F2F4FF` · خط Readex Pro · زوايا 10/16/24px)،
ومُحسَّنة لمعايير Google Core Web Vitals وWCAG 2.2 AA.

افتح **`preview.html`** لمعاينة كل شيء (وضع فاتح/داكن).

---

## 1) محتويات الحزمة

| المجلد | المحتوى | الاستخدام |
|---|---|---|
| `logo/` | 9 ملفات SVG محسَّنة (SVGO) | العلامة، الأفقي، العمودي، الكلمة العربية/اللاتينية — فاتح/داكن |
| `png/` | 15 PNG بدقّات 1x/2x/4x/طباعة | العرض التقديمي، الفيديو، الطباعة، المنصات التي لا تقبل SVG |
| `icons/` | 40 أيقونة SVG · 24×24 · خط 1.75 · `currentColor` | أيقونات خاصة بوظائف بصيرة |
| `sprite/icons.svg` | سبرايت واحد (7 KB) لكل الأيقونات | `<use href="#i-name">` — طلب شبكة واحد |
| `react/` | `Icon.tsx` + `Logo.tsx` + أنواع TypeScript صارمة | React 19 — مُختبَر `tsc --strict` |
| `css/tokens.css` | متغيرات CSS (ألوان، خطوط، مسافات، ظلال، حالات) + فاتح/داكن | `@import` في أعلى الـCSS |
| `css/fonts.css` | `@font-face` لـ Readex Pro (متغيّر) + Uthmanic HAFS | مع `preload` |
| `fonts/` | `ReadexPro[wght].woff2` **87 KB** (عربي+لاتيني، 160–700) + رخصة OFL | استضافة ذاتية — لا Google Fonts |
| `favicon/` | `favicon.ico` (16/32/48) · `favicon.svg` · `apple-touch-icon.png` · `safari-pinned-tab.svg` | المتصفحات وiOS وSafari |
| `pwa/` | 192/512 `any` · 192/512 `maskable` · 512 `monochrome` | `manifest.webmanifest` |
| `og/` | `og-image.jpg` 1200×630 (79 KB) · `twitter-square.jpg` 600×600 | المشاركة الاجتماعية |
| `manifest.webmanifest` | PWA جاهز (عربي RTL، اختصارات، share_target) | ضعه في الجذر |
| `head-snippet.html` | وسوم `<head>` كاملة: أيقونات، OG، hreflang، JSON-LD، theme-color | انسخ والصق |
| `CHECKSUMS.sha256` | بصمة كل ملف | التحقق من السلامة |

---

## 2) الشعار — المعنى والقواعد

**الفكرة:** *عين* (= بصيرة) تتشكّل من **قوسين كصفحتي مصحف مفتوح**؛ في بؤبؤها **نجمة ثمانية** من الزخرفة
الإسلامية تحمل **علامة تحقق** — "النظر في المصدر قبل القبول". التدرّج بنفسجي→كحلي من القالب الرسمي، النجمة بالتركواز الرسمي.

**هندسة دقيقة:** الشبكة 64×64، نصف قطر البلاطة 16 (= `--bs-radius-md`)، النجمة 16 رأسًا حقيقيًا (R=11.5، نسبة داخلية 0.78)، سماكة العين 3.4.

| الملف | متى تستخدمه | الحد الأدنى |
|---|---|---|
| `logo-mark.svg` | أيقونة التطبيق، الأفاتار، الـfavicon، الأزرار | 16 px |
| `logo-mark-ondark.svg` | على خلفيات كحلية/داكنة بدون بلاطة | 20 px |
| `logo-mark-mono.svg` | طباعة أحادية، ختم، `currentColor` | 20 px |
| `logo-horizontal-light/dark.svg` | رأس الموقع، تذييل، توقيعات | ارتفاع 32 px |
| `logo-stacked-light/dark.svg` | شاشة البداية، الشرائح، الفيديو | عرض 120 px |
| `wordmark-ar/en.svg` | عندما تكون العلامة ظاهرة بجوارها أصلًا | ارتفاع 20 px |

**افعل / لا تفعل**
- ✅ مساحة أمان حول الشعار = ارتفاع النجمة (≈ 36% من العلامة).
- ✅ استخدم `-dark` على أي خلفية أغمق من `#6150EA`.
- ❌ لا تغيّر الألوان، لا تدوّر، لا تُضف ظلًا خارجيًا أو حدودًا.
- ❌ لا تضع العلامة الملوّنة فوق صور مزدحمة — استخدم `-ondark` مع طبقة تعتيم 40%.
- ❌ لا تعِد كتابة الكلمة بخط آخر — الكلمة مُحوَّلة لمسارات من Readex Pro Bold 700 (عربي) وMedium 500 (لاتيني).

---

## 3) الأيقونات — 40 أيقونة خاصة بوظائف بصيرة

تصميم موحّد: شبكة 24، خط 1.75، أطراف وزوايا مستديرة، `fill="none" stroke="currentColor"` → تأخذ لون النص تلقائيًا وتعمل في الوضعين.

| المجموعة | الأسماء |
|---|---|
| **حالات التحقق الأربع** | `state-found` `state-partial` `state-review` `state-notfound` |
| **المصادر** | `quran` `hadith` `source-link` `grade-quoted` |
| **الإجراءات** | `check-run` `paste-text` `upload-image` `ocr-scan` `diff-words` `report-export` `copy` `share-link` `clear` |
| **الضمانات (مبادئ المشروع)** | `no-generation` `no-judgment` `byte-exact` `shield-verify` `privacy-nostore` `deterministic` `refer-scholar` `search-external` |
| **النظام** | `api` `health` `limits` `hijri-date` `language` `theme` `keyboard` `github` |
| **واجهة** | `menu` `close` `arrow-start` `chevron-down` `info` `warning` `spinner` |

**استخدام:**
```html
<!-- سبرايت (ضمّنه مرة في body) -->
<svg class="bs-icon"><use href="#i-state-found"/></svg>
```
```tsx
import { Icon, LogoMark } from './brand/react';
<Icon name="state-found" title="مطابقة تامة" />   {/* بعنوان = قابلة للوصول */}
<Icon name="copy" />                              {/* بدون عنوان = زخرفية aria-hidden */}
<Icon name="arrow-start" flipInRtl />             {/* تنقلب تلقائيًا في RTL */}
<LogoMark size={40} variant="tile" />
```
- الأيقونات **الاتجاهية** (`arrow-start`) أضف `flipInRtl` / `.bs-icon--rtl-flip`.
- حجم اللمس للأزرار الأيقونية ≥ **44×44 px** (`--bs-touch-min`) — WCAG 2.2 (2.5.8).
- لا تُصغّر تحت 16 px؛ عند 16 px استخدم `stroke-width: 2`.

---

## 4) الخطوط

- **Readex Pro** (OFL) — واجهة كاملة عربي+لاتيني. ملف **متغيّر واحد 87 KB** مُقتطَع (subset) إلى: لاتيني أساسي، عربي، ملحقات عربية، أشكال عرض عربية، علامات ترقيم.
  استخدم `<link rel="preload" ... as="font" crossorigin>` + `font-display: swap`.
- **KFGQPC Uthmanic Script HAFS** — لنص المصحف فقط، حمّله **عند الحاجة** (ليس في الصفحة الرئيسية).
  غير مرفق هنا (يُحمّل من موقع مجمع الملك فهد: `fonts.qurancomplex.gov.sa`).
- `.bs-mushaf` في `tokens.css` يمنع `letter-spacing` و`font-synthesis` ويضبط `unicode-bidi: isolate`.

---

## 5) معايير الأداء المُحقَّقة

| البند | القيمة |
|---|---|
| العلامة SVG | **930 B** (571 B gzip) |
| 40 أيقونة | **12.2 KB** (1.75 KB gzip) · السبرايت 7 KB |
| الشعار الأفقي SVG | 4.3 KB (2.0 KB gzip) |
| الخط المتغيّر | 87 KB woff2 (بدل ~280 KB TTF أو 4 ملفات ثابتة) |
| OG JPEG | 79 KB (progressive, 4:4:4) |
| favicon.ico | 706 B |
| كل الـSVG | SVGO multipass، دقة 2 أرقام، `viewBox` محفوظ، بلا `width/height` ثابتة |
| إمكانية الوصول | كل الشعارات لها `<title>`+`<desc>`؛ الأيقونات `aria-hidden` إلا بعنوان |
| التباين | نص `#12183F` على `#F2F4FF` = **15.6:1** · `#F2F4FF` على `#12183F` = **15.6:1** · أبيض على بنفسجي 5.5:1 · شارات الحالات ≥ 4.5:1 |

**Cache-Control** الموصى به: `public, max-age=31536000, immutable` لكل `brand/**` و`fonts/**` (ضع بصمة في الاسم أو مجلد إصدار).

---

## 6) الألوان (مرجع سريع)

| الرمز | HEX | الاستخدام |
|---|---|---|
| `--bs-navy` | `#12183F` | النص الأساسي، خلفية داكنة، `theme-color` |
| `--bs-violet` | `#6150EA` | الأزرار الأساسية، الروابط، التركيز |
| `--bs-teal` | `#2EF2C2` | التمييز، النجمة، الخطوط الفاصلة |
| `--bs-offwhite` | `#F2F4FF` | خلفية فاتحة، نص على الداكن |
| `--bs-state-found` | `#16B892` | مطابقة تامة |
| `--bs-state-partial` | `#D98E04` | مطابقة جزئية |
| `--bs-state-review` | `#6150EA` | يحتاج مراجعة |
| `--bs-state-notfound` | `#C62C45` | غير موجود |

> **ملاحظة مهمة:** حالة `needs_review` تأخذ البنفسجي (لون العلامة) عمدًا — لا الأحمر — لأنها ليست "خطأ" بل دعوة للرجوع لأهل العلم.

---

## 7) تثبيت سريع (Vite/React)

```
public/
  favicon.ico              ← favicon/favicon.ico
  manifest.webmanifest
  brand/{logo,icons,favicon,pwa,og,css}/
  fonts/ReadexPro[wght].woff2
src/brand/react/{Icon.tsx,Logo.tsx,index.ts}
```
ثم الصق `head-snippet.html` في `index.html` وعدّل الروابط المطلقة.

راجع `LICENSE-NOTES.md` قبل النشر.
