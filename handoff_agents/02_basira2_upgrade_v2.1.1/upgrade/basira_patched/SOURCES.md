# SOURCES.md — سجل المصادر (generated from `corpus/manifest.json`)

> المنظّم يطلب حرفيًا «سجل المصادر والأدوات والتراخيص». هذا الملف هو سجل **المصادر النصية**؛
> الأدوات في `THIRD_PARTY_NOTICES.md`، والنماذج في `AI_USAGE.md`.
> يُعاد توليده بـ `python corpus/gen_sources_md.py` — لا تحرّره يدويًا.

## المبدأ

- كل نص ديني معروض في بصيرة يأتي **حرفيًا (byte-exact)** من أحد المصادر أدناه بمعرّفه، ويتحقق المدقّق اللاحق (V1) من ذلك في كل رد.
- لا يُعدَّل أي نص مصدر. التطبيع (إسقاط التشكيل، توحيد الهمزات) يُستخدم **للفهرسة والمقارنة فقط**.
- ملفات البيانات غير مضمّنة في المستودع؛ `corpus/fetch.py` ينزّلها ويتحقق من sha256 ويفشل عند أي اختلاف.

## المصادر

| المصدر | id | الإصدار | الرخصة | رابط | الاستخدام | التعديلات | sha256 | تاريخ التنزيل |
|---|---|---|---|---|---|---|---|---|
| **Tanzil Quran Text (Uthmani, Hafs) v1.1** | `tanzil_uthmani` | 1.1 | CC BY 3.0 — verbatim copies only; CHANGING IT IS NOT ALLOWED | [license](https://tanzil.net/docs/text_license) | display (verbatim) + index | none; basmala stripped in index only for ayah 1 (except 1:1) | `bf4f57b968d03f41…` | 2026-09-30 |
| **Tanzil Quran Text (Simple Clean, Hafs) v1.1** | `tanzil_simple_clean` | 1.1 | CC BY 3.0 — verbatim copies only; CHANGING IT IS NOT ALLOWED | [license](https://tanzil.net/docs/text_license) | index only (second rasm) | none | `228df2a717671aeb…` | 2026-09-30 |
| **Tanzil Quran Text (Simple, vocalized, Hafs) v1.1** | `tanzil_simple` | 1.1 | CC BY 3.0 — verbatim copies only; CHANGING IT IS NOT ALLOWED | [license](https://tanzil.net/docs/text_license) | harakat reference layer (per-letter vowel comparison; never indexed, never displayed as source text) | none | `f3268cfe7a400add…` | 2026-10-01 |
| **Open-Hadith-Data (mhashim6) — nine books** | `ohd` | 1515f6cb | ODbL 1.0 (database) + DbCL 1.0 (contents) | [license](https://github.com/mhashim6/Open-Hadith-Data/blob/master/LICENSE) | display (mushakkala, verbatim; U+200F removed at display) + index (plain) | none | `per-book…` | 2026-09-30 |
| **HadeethEnc — Arabic file v1.7.0 (2025-11-12)** | `hadeethenc_ar` | 1.7.0 | Redistribution terms (7 conditions: no modification, cite source + version, keep version info …). Scope for the Arabic file UNVERIFIED — terms mention 'translations'. | [license](https://hadeethenc.com/ar/home) | grade + takhrij + link (attributed). MODE=link by default: full hadith_text is linked, not embedded. | none | `d5d397cb9fc8ddd5…` | 2026-09-30 |

### Open-Hadith-Data (mhashim6) — nine books — books (commit `1515f6cb`)

| key | الاسم | tier | rows | sha256 (plain) |
|---|---|---|---|---|
| `sahih_al-bukhari` | صحيح البخاري | sahihain | 7008 | `e78f8ea42c4bdf58…` |
| `sahih_muslim` | صحيح مسلم | sahihain | 5362 | `dfa4ba5de748f213…` |
| `sunan_abu-dawud` | سنن أبي داود | other_nine | 4590 | `60ab2b9684161c54…` |
| `sunan_al-tirmidhi` | سنن الترمذي | other_nine | 3891 | `2a7a0d041bc859fd…` |
| `sunan_al-nasai` | سنن النسائي | other_nine | 5662 | `b04f7fbebf59c46a…` |
| `sunan_ibn-maja` | سنن ابن ماجه | other_nine | 4332 | `d64184e8a33f4312…` |
| `maliks_muwataa` | موطأ مالك | other_nine | 1594 | `b1f81e8f50516e2d…` |
| `musnad_ahmad` | مسند أحمد | other_nine | 26363 | `569770d15a7876bc…` |
| `sunan_al-darimi` | سنن الدارمي | other_nine | 3367 | `de2ebe287de41345…` |

**Chain of title:** https://github.com/ceefour/hadith-islamware (Unlicense file; README asserts 'Copyright (C) 2006-2014 Islam Ware') — chain of title UNRESOLVED

**Numbering:** collection-internal (NOT canonical edition numbering)

## ما لا نفعله بالمصادر

- **لا نعرض حكمًا على حديث** إلا نصًّا منقولًا حرفيًا من موسوعة الأحاديث النبوية (HadeethEnc) منسوبًا إليها بإصدارها (`notice.grade_line`). في الوضع الافتراضي `HADEETHENC_MODE=link` نعرض الحكم والتخريج ورابط الموسوعة ولا نضمّن نص الحديث من عندهم.
- **لا نعيد توزيع قاعدة بيانات مشتقة** من OHD (شرط ODbL): الفهرس يُبنى محليًا وقت التشغيل ولا يُنشر.
- **لا نغيّر نص Tanzil** (شرط رخصتهم: «CHANGING IT IS NOT ALLOWED»).

## قيود معروفة (مذكورة في `/limits`)

1. **ترقيم الأحاديث** = ترقيم مجموعة Open-Hadith-Data الداخلي، لا ترقيم الطبعات المعتمدة؛ نُصرّح بذلك في كل بطاقة (`notice.ohd_numbering`).
2. **سلسلة حقوق OHD** غير محسومة عند المصدر الأصلي (Islam Ware). مفتاح `OHD_MODE=off` يحوّل عرض نص الحديث إلى «موضع فقط» في دقائق إن لزم.
3. **رواية حفص فقط** للقرآن؛ القراءات الأخرى تُلتقط كرسم مختلف مع ملاحظة وصفية (`notice.qiraah_note`) لا كخطأ.
4. **الكتب التسعة فقط** للحديث؛ ما خارجها → «لم نجده في مصادرنا» + إحالة للدرر السنية/الشاملة — **وليس حكمًا عليه**.

---
*Generated 2026-10-01 from manifest schema v1.*
