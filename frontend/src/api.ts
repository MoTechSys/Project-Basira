/** Typed client for the Basira API (mirrors backend/app/schemas.py). No religious text is produced here. */

export type Status = "found" | "partial_match" | "needs_review" | "not_found";
export type Kind = "quran" | "hadith_matn" | "isnad" | "attributed_saying" | "unknown";
export type Lang = "ar" | "en";

export interface DiffOp {
  op: "equal" | "replace" | "insert" | "delete";
  quote_range: [number, number];
  source_range: [number, number];
  quote_chars: [number, number];
  source_chars: [number, number];
}
export interface Grade {
  text: string;
  takhrij: string;
  source: "HadeethEnc";
  version: string;
  url: string;
}
export interface Link {
  name: string;
  url: string;
}
export interface Match {
  corpus: "tanzil" | "ohd" | "hadeethenc";
  ref: Record<string, string | number>;
  ref_label_ar: string;
  ref_label_en: string;
  collection_tier: "quran" | "sahihain" | "other_nine" | "hadeethenc";
  source_text: string;
  source_text_range: [number, number] | null;
  source_url: string;
  links: Link[];
  diff: DiffOp[];
  diff_kinds: string[];
  score: number;
  grade: Grade | null;
  continues_to: Record<string, number> | null;
}
export interface QuoteResult {
  id: string;
  span: { start: number; end: number };
  quoted_text: string;
  kind: Kind;
  language: "ar" | "en" | "other";
  source_modality: "text" | "image";
  claimed_source: { raw: string; parsed: Record<string, unknown> } | null;
  claimed_source_mismatch: boolean;
  status: Status;
  review_reason: string | null;
  score: number;
  message_key: string;
  notice_keys: string[];
  repeated_spans?: { start: number; end: number }[];
  segments?: { type: "Ayah" | "matn" | "isnad" | "claimed_source"; start: number; end: number }[];
  determinism_hash?: string;
  matches: Match[];
  total_positions: number;
  external_search_links: Link[];
}
export interface CheckResponse {
  request_id: string;
  disclaimer_key: string;
  transparency_key: string;
  corpus: Record<string, string>;
  extraction_degraded: boolean;
  extraction_provider: string;
  flags: { chain_message: boolean; refusal: boolean; pii_suspected: boolean };
  quotes: QuoteResult[];
  validator_rejections: number;
  timings_ms: { extract: number; retrieve: number; match: number; total: number };
  ocr_text?: string | null;
}
export interface ApiError {
  error: { code: string; message_ar: string; message_en: string };
}
export interface SourceInfo {
  id: string;
  name: string;
  type: string;
  url: string;
  version: string;
  license: string;
  license_url: string;
  purpose: string;
  records: number;
}
export interface Health {
  status: "ok" | "loading" | "degraded";
  build_sha: string;
  corpus: Record<string, string>;
  corpus_loaded: boolean;
  counts: Record<string, number>;
  rss_mb: number;
}

export const API_BASE: string = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

export class BasiraError extends Error {
  readonly status: number;
  readonly body: ApiError | null;
  constructor(status: number, body: ApiError | null) {
    super(body?.error.code ?? `http_${status}`);
    this.status = status;
    this.body = body;
  }
}

async function parse<T>(r: Response): Promise<T> {
  if (r.ok) return (await r.json()) as T;
  let body: ApiError | null = null;
  try {
    body = (await r.json()) as ApiError;
  } catch {
    body = null;
  }
  throw new BasiraError(r.status, body);
}

export async function check(text: string, ui_lang: Lang, signal?: AbortSignal): Promise<CheckResponse> {
  const r = await fetch(`${API_BASE}/v1/check`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, ui_lang, source_modality: "text", options: { max_candidates: 3 } }),
    ...(signal ? { signal } : {}),
  });
  return parse<CheckResponse>(r);
}

export async function checkImage(file: File, ui_lang: Lang, signal?: AbortSignal): Promise<CheckResponse> {
  const fd = new FormData();
  fd.append("image", file);
  fd.append("ui_lang", ui_lang);
  const r = await fetch(`${API_BASE}/v1/check/image`, { method: "POST", body: fd, ...(signal ? { signal } : {}) });
  return parse<CheckResponse>(r);
}

export async function sources(): Promise<SourceInfo[]> {
  return parse<SourceInfo[]>(await fetch(`${API_BASE}/v1/sources`));
}

export async function health(): Promise<Health> {
  const r = await fetch(`${API_BASE}/health`);
  return (await r.json()) as Health; // 503 while loading still carries a body
}
