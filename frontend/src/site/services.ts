import type { BasiraIconName } from "../brand";
import type { SiteKey } from "./strings";

/** The single list of services. `live` is the truth: only `true` when the feature runs on the engine today. */
export interface Service {
  id: string;
  live: boolean;
  icon: BasiraIconName;
  title: SiteKey;
  desc: SiteKey;
  out: SiteKey;
  href: string;
}

export const SERVICES: Service[] = [
  { id: "text", live: true, icon: "paste-text", title: "svc_text_t", desc: "svc_text_d", out: "svc_text_out", href: "/check" },
  { id: "image", live: true, icon: "ocr-scan", title: "svc_image_t", desc: "svc_image_d", out: "svc_image_out", href: "/check?mode=image" },
  { id: "english", live: true, icon: "language", title: "svc_en_t", desc: "svc_en_d", out: "svc_en_out", href: "/check?mode=english" },
  { id: "guard", live: true, icon: "shield-verify", title: "svc_guard_t", desc: "svc_guard_d", out: "svc_guard_out", href: "/check?mode=guard" },
  { id: "api", live: true, icon: "api", title: "svc_api_t", desc: "svc_api_d", out: "svc_api_out", href: "/developers" },
  { id: "receipt", live: true, icon: "share-link", title: "svc_receipt_t", desc: "svc_receipt_d", out: "svc_receipt_out", href: "/check" },
  { id: "trust", live: true, icon: "limits", title: "svc_trust_t", desc: "svc_trust_d", out: "svc_trust_out", href: "/trust" },
];
