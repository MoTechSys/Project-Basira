# Basira seal — «ختم المعارضة»

| File | Use |
|---|---|
| `logo-mark.svg` | seal on light surfaces (ink `#12183F`, gold dot `#B8893A`) |
| `logo-mark-ondark.svg` | seal on night surfaces (paper `#F6F2E9`, light-gold dot `#D9B66E`) |
| `logo-mark-mono.svg` | single colour (print, stamps, Safari pinned tab) |

The wordmark «بصيرة» is live text set in Reem Kufi 600 (`frontend/public/fonts/ReemKufi.woff2`), not an
outline file, so the lockup is the `LogoHorizontal` component in `src/brand/Logo.tsx`.

Geometry is generated, never hand-drawn: `docs/design/brand/seal.py` (`--check` asserts 8 tips at 45°).
Previous eye-mark files were removed with identity v4 (DECISIONS E-056).
