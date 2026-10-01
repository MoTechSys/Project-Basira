/** UI strings = messages/{ar,en}.json (single source of truth, E-009) + a small UI-chrome catalogue below.
 *  Templates use {var}; filled only from corpus/matcher fields. The frontend never writes religious text. */

import ar from "../../messages/ar.json";
import en from "../../messages/en.json";
import type { Lang } from "./api";

type Catalog = Record<string, Record<string, string>>;
const MESSAGES: Record<Lang, Catalog> = {
  ar: ar as unknown as Catalog,
  en: en as unknown as Catalog,
};

/** UI chrome (buttons, headings) — not part of the backend's message contract. Keys identical in both. */
export const UI: Record<Lang, Record<string, string>> = {
  ar: {
    app_name: "بصيرة",
    tagline: "تحقّق من نقل الآيات والأحاديث في نصك — بلا حكم، بلا توليد.",
    input_label: "الصق النص الذي تريد فحصه",
    input_placeholder: "مثال: قال تعالى: ﴿إن الله مع الصابرين﴾ … أو منشور كامل يحتوي اقتباسات",
    check: "افحص",
    checking: "جارٍ الفحص…",
    clear: "مسح",
    upload_image: "أو ارفع صورة",
    chars: "{n} / {max} حرفًا",
    your_text: "نصك",
    source_text: "نص المصدر",
    diff_legend: "الكلمات المظلّلة هي مواضع الاختلاف بين نصك ونص المصدر.",
    positions: "المواضع",
    links: "روابط",
    sources_title: "المصادر",
    sources_hint: "كل نص مصدر يُعرض حرفيًا من هذه المصادر بإصدارها المذكور.",
    status_loading: "الخادم يحمّل المدوّنة…",
    status_ok: "جاهز",
    status_down: "الخادم غير متاح",
    lang_switch: "English",
    no_quotes_title: "لم نعثر على اقتباس",
    summary: "{n} اقتباس",
    summary_plural: "{n} اقتباسات",
    report: "أبلغ عن خطأ",
    copy_report: "نسخ تقرير الفحص",
    copied: "نُسخ",
    processing_time: "زمن المعالجة {ms} م.ث",
    flags_title: "ملاحظات على النص",
    license: "رخصة",
    version: "الإصدار",
    records: "سجلًا",
    skip_to_results: "انتقل إلى النتائج",
    error_network: "تعذّر الاتصال بالخادم.",
    review_reason: "سبب المراجعة",
    reason_near_miss: "اختلاف في الكلمات",
    reason_orthographic_difference: "اختلاف إملائي",
    reason_short_quote: "اقتباس قصير",
    reason_stage_failure: "تعطّل مرحلة",
    reason_validator_reject: "رفض المدقق",
    reason_non_arabic: "نص غير عربي",
    reason_image_unconfirmed: "نص من صورة",
    grade_source: "موسوعة الأحاديث النبوية",
    ocr_title: "النص كما قُرئ من الصورة — تأكد منه قبل الاعتماد على النتيجة",
  },
  en: {
    app_name: "Basira",
    tagline: "Check how verses and hadiths are quoted in your text — no verdicts, no generation.",
    input_label: "Paste the text to check",
    input_placeholder: "e.g. a post containing quoted verses or hadiths",
    check: "Check",
    checking: "Checking…",
    clear: "Clear",
    upload_image: "or upload an image",
    chars: "{n} / {max} characters",
    your_text: "Your text",
    source_text: "Source text",
    diff_legend: "Highlighted words are where your text differs from the source.",
    positions: "Positions",
    links: "Links",
    sources_title: "Sources",
    sources_hint: "Every source text is shown verbatim from these sources at the stated version.",
    status_loading: "Server is loading the corpus…",
    status_ok: "Ready",
    status_down: "Server unavailable",
    lang_switch: "العربية",
    no_quotes_title: "No quotation found",
    summary: "{n} quotation",
    summary_plural: "{n} quotations",
    report: "Report an error",
    copy_report: "Copy check report",
    copied: "Copied",
    processing_time: "Processed in {ms} ms",
    flags_title: "Notes on the text",
    license: "License",
    version: "Version",
    records: "records",
    skip_to_results: "Skip to results",
    error_network: "Could not reach the server.",
    review_reason: "Review reason",
    reason_near_miss: "word differences",
    reason_orthographic_difference: "spelling difference",
    reason_short_quote: "short quote",
    reason_stage_failure: "stage failure",
    reason_validator_reject: "validator reject",
    reason_non_arabic: "non-Arabic text",
    reason_image_unconfirmed: "text from image",
    grade_source: "Prophetic Hadiths Encyclopedia",
    ocr_title: "Text as read from the image — verify it before relying on the result",
  },
};

export function fill(tpl: string, vars: Record<string, string | number> = {}): string {
  return tpl.replace(/\{(\w+)\}/g, (m, k: string) => (k in vars ? String(vars[k]) : m));
}

export function msg(lang: Lang, section: string, key: string, vars?: Record<string, string | number>): string {
  const tpl = MESSAGES[lang][section]?.[key];
  return tpl === undefined ? `${section}.${key}` : fill(tpl, vars);
}

export function has(lang: Lang, section: string, key: string): boolean {
  return MESSAGES[lang][section]?.[key] !== undefined;
}

export function ui(lang: Lang, key: string, vars?: Record<string, string | number>): string {
  const tpl = UI[lang][key];
  return tpl === undefined ? key : fill(tpl, vars);
}

export const MAX_CHARS = 5000;
