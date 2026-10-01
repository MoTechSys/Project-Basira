"""CSP nonce stamping for the SPA shell (E-036).

`index.html` may contain inline scripts (dark-mode bootstrap before first paint, JSON-LD). A strict
CSP (`script-src 'self'`) blocks them; `'unsafe-inline'` would defeat CSP. The compromise used by
every major framework: a per-request nonce in the header AND on every inline <script>.

Only `<script ...>` tags that do NOT already carry a nonce are stamped. External scripts
(`src=...`) are covered by `'self'` and are left untouched; stamping them is harmless but noisy.
"""

from __future__ import annotations

import re

# `<script` followed by attributes that contain neither `nonce=` nor `src=`, up to the closing `>`.
# Negative look-ahead per attribute chunk keeps the regex linear (no catastrophic backtracking).
_INLINE_SCRIPT = re.compile(r"<script(?P<attrs>(?:\s+(?!nonce=|src=)[^\s>]+)*)\s*>", re.IGNORECASE)


def stamp_nonce(html: str, nonce: str) -> str:
    """Return *html* with ``nonce="<nonce>"`` added to every inline ``<script>`` tag.

    Idempotent for tags that already have a nonce; no-op when *nonce* is empty.
    """
    if not nonce:
        return html

    def _sub(m: re.Match[str]) -> str:
        attrs = m.group("attrs")
        return f'<script nonce="{nonce}"{attrs}>'

    return _INLINE_SCRIPT.sub(_sub, html)
