# Telegram bot — evidence (2026-10-06)

Rendered from the **rich_message blocks Telegram stored** for real replies of @BasiraCheckBot (fetched back with a
user session after `scripts/live_e2e.py` ran against https://basirapp.site). The drawing is a Telegram-like dark
theme (`integrations/telegram/scripts/preview_blocks.py`); the structure — headings, pull-quotes, tables, collapsible sections, buttons and
their styles — is exactly what the server returned.

| File | Input |
|---|---|
| `01_start.png` | `/start` |
| `02_found_quran.png` | «قال تعالى: ﴿إن الله مع الصابرين﴾» |
| `03_needs_review_quran.png` | «قال تعالى: ﴿إن الله علي كل شيء قدير﴾» — «علي» / «عَلَىٰ» marked |
| `04_not_found.png` | «قال ﷺ: «الدين المعاملة»» — search buttons only |
| `05_partial_hadith.png` | «طلب العلم فريضة على كل مسلم ومسلمة» — «ومسلمة» marked |
| `07_image_hadith.png` | an image of a hadith → OCR text first, `needs_review/image_unconfirmed` |
| `08_channel_forward.png` | a channel post forwarded to the bot (ayah + hadith, «رواه البخاري») |
| `09_sources.png` | `/sources` |
