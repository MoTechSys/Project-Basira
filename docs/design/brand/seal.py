"""«ختم المعارضة» — the Basira seal. Single source of truth for the mark's geometry.

Construction (24-unit grid, centre 12,12):
  khatam  two squares of half-side h = 7.6, one rotated 45°  → 8-pointed star, 16 vertices, tips every 45°.
          (Not a hexagram: 6 tips every 60° from two triangles. Verified by `python3 seal.py --check`.)
  dāra    circular window r = 5 cut through the star (even-odd fill) — Ibn al-Ṣalāḥ, al-Muqaddima, type 25:
          a circle between two hadiths, left empty; a dot is placed in it once the text is collated.
  nuqta   gold rhombus, half-diagonal 2.6 — Ibn Muqla's proportional unit is the rhombic pen dot.
"""
import math, re, sys

H = 7.6          # half-side of each square
WINDOW_R = 5     # dāra radius
NUQTA = 2.6      # half-diagonal of the rhombic dot


def star_path(h: float = H) -> str:
    """Outline of square ∪ (square rotated 45°): 16 vertices, clockwise from the top tip."""
    d = h * math.sqrt(2)              # tip distance of the rotated square
    k = h * (math.sqrt(2) - 1)        # where a rotated edge crosses an upright edge
    c = 12
    pts = [(c, c - d), (c + k, c - h), (c + h, c - h), (c + h, c - k), (c + d, c), (c + h, c + k), (c + h, c + h), (c + k, c + h),
           (c, c + d), (c - k, c + h), (c - h, c + h), (c - h, c + k), (c - d, c), (c - h, c - k), (c - h, c - h), (c - k, c - h)]
    return "M" + " L".join(f"{x:.3f} {y:.3f}" for x, y in pts) + "Z"


def window_path(r: float = WINDOW_R) -> str:
    return f"M{12 - r} 12a{r} {r} 0 1 0 {2 * r} 0a{r} {r} 0 1 0 {-2 * r} 0Z"


def seal(size: int = 40, ink: str = "#12183F", gold: str = "#B8893A") -> str:
    n = NUQTA
    return (f'<svg viewBox="0 0 24 24" width="{size}" height="{size}" aria-hidden="true" class="seal">'
            f'<path d="{star_path()} {window_path()}" fill="{ink}" fill-rule="evenodd"/>'
            f'<path d="M12 {12 - n} {12 + n} 12 12 {12 + n} {12 - n} 12Z" fill="{gold}"/></svg>')


def tile(stroke: str = "#D9B66E", opacity: float = .16, s: int = 96) -> str:
    """Seamless khatam lattice for dark backgrounds (squares + rhombi only — no 6-fold geometry)."""
    c, h = s / 2, s * .21
    d = h * math.sqrt(2)
    star = lambda x, y: (f'<rect x="{x - h}" y="{y - h}" width="{2 * h}" height="{2 * h}"/>'
                         f'<path d="M{x} {y - d}L{x + d} {y}L{x} {y + d}L{x - d} {y}Z"/>')
    body = star(c, c) + "".join(star(x, y) for x in (0, s) for y in (0, s))
    body += f'<path d="M{c - d} {c}H{d}M{c + d} {c}H{s - d}M{c} {c - d}V{d}M{c} {c + d}V{s - d}"/>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{s}" height="{s}" viewBox="0 0 {s} {s}">'
            f'<g fill="none" stroke="{stroke}" stroke-opacity="{opacity}" stroke-width="1">{body}</g></svg>')


def check() -> None:
    pts = [tuple(map(float, p.split())) for p in re.findall(r"[\d.]+ [\d.]+", star_path())]
    r = [math.hypot(x - 12, y - 12) for x, y in pts]
    tips = [p for p, d in zip(pts, r) if d > max(r) - .01]
    ang = sorted(round(math.degrees(math.atan2(y - 12, x - 12)) % 360) for x, y in tips)
    gaps = {(ang[(i + 1) % len(ang)] - ang[i]) % 360 for i in range(len(ang))}
    print(f"vertices: {len(pts)} | outer tips: {len(tips)} | tip angles: {ang} | gaps: {sorted(gaps)}")
    assert len(tips) == 8 and gaps == {45}, "seal must stay an 8-fold khatam"
    print("OK: 8-fold khatam (a hexagram would be 6 tips at 60°)")


if __name__ == "__main__" and "--check" in sys.argv:
    check()
