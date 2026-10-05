/** E-056 — the seal must stay an 8-fold khatam (two squares), never a hexagram (two triangles).
 *  Parses the outline that Logo.tsx actually ships and the favicon file, and measures the tips. */
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

function tips(svgPath: string): number[] {
  const pts = [...svgPath.split("M")[1]!.split("Z")[0]!.matchAll(/(-?[\d.]+) (-?[\d.]+)/g)].map((m) => [Number(m[1]), Number(m[2])] as const);
  const r = pts.map(([x, y]) => Math.hypot(x - 12, y - 12));
  const max = Math.max(...r);
  return pts
    .filter((_, i) => r[i]! > max - 0.01)
    .map(([x, y]) => Math.round(((Math.atan2(y - 12, x - 12) * 180) / Math.PI + 360) % 360))
    .sort((a, b) => a - b);
}
const gaps = (a: number[]) => [...new Set(a.map((v, i) => (a[(i + 1) % a.length]! - v + 360) % 360))];

describe("seal geometry (E-056)", () => {
  for (const [name, file, re] of [
    ["Logo.tsx", "src/brand/Logo.tsx", /const STAR = "([^"]+)"/],
    ["favicon.svg", "public/brand/favicon/favicon.svg", /<path d="([^"]+)" fill="#F6F2E9"/],
  ] as const) {
    it(`${name}: 8 tips every 45° (a hexagram would be 6 at 60°)`, () => {
      const d = re.exec(readFileSync(file, "utf8"))![1]!;
      const t = tips(d);
      expect(t).toEqual([0, 45, 90, 135, 180, 225, 270, 315]);
      expect(gaps(t)).toEqual([45]);
    });
  }
});
