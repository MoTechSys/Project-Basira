/** E-046 — lazy chunk: imported with `import("./share")` only when a share link is opened or created. */
/** Share link without storage (UX spec §5-B): the TEXT (not the result) travels in the URL hash,
 *  deflate-raw compressed and base64url encoded. The hash never reaches the server (no logs), and
 *  the recipient re-runs the check locally — determinism guarantees the same result.
 *
 *  Measured on non-repetitive Arabic prose: 5,000 chars → ~2,960-char link. Native
 *  CompressionStream (Chrome 80+, Firefox 113+, Safari 16.4+) → 0 kB of library code.
 *  On browsers without it we fall back to an uncompressed `#t0=` payload (still works, just longer).
 */

const B64 = { enc: (b: Uint8Array) => btoa(String.fromCharCode(...b)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "") };

function b64decode(s: string): Bytes {
  const pad = s.length % 4 === 0 ? "" : "=".repeat(4 - (s.length % 4));
  const bin = atob(s.replace(/-/g, "+").replace(/_/g, "/") + pad);
  const out = new Uint8Array(new ArrayBuffer(bin.length));
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

type Bytes = Uint8Array<ArrayBuffer>;

async function pipe(bytes: Bytes, stream: ReadableWritablePair<Uint8Array, BufferSource>): Promise<Bytes> {
  const src = new ReadableStream<BufferSource>({
    start(c) {
      c.enqueue(bytes);
      c.close();
    },
  }).pipeThrough(stream);
  const reader = src.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    chunks.push(value);
    total += value.byteLength;
  }
  const out = new Uint8Array(total);
  let off = 0;
  for (const c of chunks) {
    out.set(c, off);
    off += c.byteLength;
  }
  return out;
}

export const hasCompression = (): boolean => typeof CompressionStream === "function" && typeof DecompressionStream === "function";

export interface SharePayload {
  text: string;
  lang: "ar" | "en";
}

/** Build `#t=<b64(deflate-raw(utf8))>&l=ar&v=1` (or `#t0=<b64(utf8)>` without compression). */
export async function encodeShare(p: SharePayload): Promise<string> {
  const enc = new TextEncoder().encode(p.text);
  const utf8: Bytes = new Uint8Array(new ArrayBuffer(enc.byteLength));
  utf8.set(enc);
  if (hasCompression()) {
    const z = await pipe(utf8, new CompressionStream("deflate-raw"));
    return `#t=${B64.enc(z)}&l=${p.lang}&v=1`;
  }
  return `#t0=${B64.enc(utf8)}&l=${p.lang}&v=1`;
}

/** Parse a share hash. Returns null for anything unexpected (never throws, never executes). */
/** Upper bound on the fragment before any decoding: 5,000 Arabic chars compress to ≈3 kB; this leaves
 *  4× headroom and refuses oversized payloads before inflating them. */
export const MAX_HASH_CHARS = 12_000;

export async function decodeShare(hash: string, maxChars: number): Promise<SharePayload | null> {
  if (!hash.startsWith("#") || hash.length > MAX_HASH_CHARS) return null;
  const params = new URLSearchParams(hash.slice(1));
  const lang = params.get("l") === "en" ? "en" : "ar";
  try {
    let bytes: Bytes;
    if (params.has("t")) {
      if (!hasCompression()) return null;
      bytes = await pipe(b64decode(params.get("t") ?? ""), new DecompressionStream("deflate-raw"));
    } else if (params.has("t0")) {
      bytes = b64decode(params.get("t0") ?? "");
    } else return null;
    const text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
    if (!text.trim() || text.length > maxChars) return null;
    return { text, lang };
  } catch {
    return null;
  }
}

/** QR v40-M holds 2,331 bytes; above that the QR should carry the bare app URL instead. */
export const QR_MAX_URL_BYTES = 2300;
export const fitsQr = (url: string): boolean => new TextEncoder().encode(url).length <= QR_MAX_URL_BYTES;
