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
  /** B07: every ayah a multi-ayah quote covers, each a verbatim record (empty unless > 1 ayah). */
  source_segments: SourceSegment[];
}
export interface SourceSegment {
  ref: Record<string, string | number>;
  ref_label_ar: string;
  ref_label_en: string;
  source_text: string;
  source_url: string;
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
  english_candidates?: EnglishCandidate[];
  picker?: "" | "rule" | "model" | "none";
  determinism_hash?: string;
  matches: Match[];
  total_positions: number;
  external_search_links: Link[];
}
export interface EnglishCandidate {
  kind: "quran" | "hadith";
  ref: Record<string, string | number>;
  ref_label_ar: string;
  ref_label_en: string;
  arabic_text: string;
  translation_text: string;
  translation_source: string;
  score: number;
  source_url: string;
  selected: boolean;
}

export interface GuardResponse {
  verdict: "clear" | "flagged" | "no_quotes";
  counts: { quotes: number; found: number; flagged: number; by_status: Record<string, number> };
  flagged_quote_ids: string[];
  quotes: { id: string; quoted_text: string; status: Status; review_reason: string | null; matches?: { ref_label_ar?: string; ref_label_en?: string; source_url?: string }[] }[];
  summary_ar: string;
  summary_en: string;
  determinism_hash: string;
  corpus: Record<string, string>;
}

export interface Receipt {
  receipt_id: string;
  determinism_hash: string;
  issued_at: string;
  token: string;
  summary: { quotes: number; by_status: Record<string, number> };
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

/* ---------------------------------------------------------------- model config (E-051)
 * The Genspark key is entered once on /settings and saved on the SERVER. The browser never keeps it and
 * never sends it with checks; /v1/models only reports a masked tail. */
export interface ModelInfo {
  id: string;
  label: string;
  vendor: string;
  tier: "flagship" | "balanced" | "fast";
  cost_x: number;
  extract_exact: number;
  extract_total: number;
  extract_p50_ms: number;
  ocr_ok: boolean;
  ocr_ms: number | null;
  vision: boolean;
  note_ar: string;
  note_en: string;
  default: boolean;
}

export interface ModelConfigState {
  configured: boolean;
  model: string | null;
  key_masked: string | null;
  provider: string;
}

export interface ModelsCatalog {
  default: string;
  models: ModelInfo[];
  config: ModelConfigState;
}

export type SaveResult =
  | { saved: true; ok: true; model: string; latency_ms: number; config: ModelConfigState }
  | { saved: false; ok: false; reason: "auth" | "model" | "transport"; latency_ms?: number; config: ModelConfigState };

export async function models(): Promise<ModelsCatalog> {
  return parse<ModelsCatalog>(await fetch(`${API_BASE}/v1/models`));
}

export async function saveModelConfig(body: { api_key?: string; model: string }): Promise<SaveResult> {
  const r = await fetch(`${API_BASE}/v1/models/config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (r.ok || r.status === 400) {
    const j = (await r.json()) as SaveResult | ApiError;
    if ("error" in j) throw new BasiraError(r.status, j);
    return j;
  }
  return parse<SaveResult>(r);
}

export async function clearModelConfig(): Promise<{ saved: false; config: ModelConfigState }> {
  return parse(await fetch(`${API_BASE}/v1/models/config`, { method: "DELETE" }));
}

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

export async function guard(answer: string, ui_lang: Lang, signal?: AbortSignal): Promise<GuardResponse> {
  const r = await fetch(`${API_BASE}/v1/guard`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answer, ui_lang }),
    ...(signal ? { signal } : {}),
  });
  return parse<GuardResponse>(r);
}

export async function receipt(text: string, ui_lang: Lang): Promise<Receipt> {
  const r = await fetch(`${API_BASE}/v1/receipt`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, ui_lang }),
  });
  return parse<Receipt>(r);
}

export function receiptUrl(rc: Receipt): string {
  return `${location.origin}${API_BASE}/v/${rc.token}?h=${rc.determinism_hash}`;
}
