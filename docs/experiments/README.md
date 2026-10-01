# experiments/ — سجل التجارب (الدليل أننا اختبرنا ولم نخمّن)

> كل تجربة: **السكربت** (في `probes/`، قابل لإعادة التشغيل) + **المخرجات الخام** كما ظهرت + **الاستنتاج** + **ما غيّرته في المشروع**.
> أعد تشغيل أي سكربت: `cd /home/user/webapp && python3 docs/experiments/probes/<file>.py` (يحتاج مفاتيح LLM محقونة).

| # | التاريخ | السؤال | السكربت | النتيجة الخام (مقتطف) | الاستنتاج | أثره |
|---|---|---|---|---|---|---|
| E1 | 2026-10-01 | هل واجهتا Anthropic وOpenAI تعملان من الـ sandbox؟ | curl (في `AGENT_PLAYBOOK.md §2`) | `PONG` / `PONG` | كلتاهما تعملان | `CAPABILITIES.md §1` |
| E2 | 2026-10-01 | أي أسماء Claude مقبولة؟ | حلقة curl على 9 أسماء | `opus-4-1 ✗ not allowed`, `sonnet-5-1 ✗ not allowed`, الباقي ✓ | القائمة الرسمية هي `GET /models` (70 نموذجًا) | `CAPABILITIES.md §1.1` |
| E3 | 2026-10-01 | كم وكيلًا متوازيًا بلا كبح؟ | `E3_parallel_32_unthrottled.py` | `32 workers — wall 2.7s … speedup ×15.6` + 12 فشل `'content'/'choices'` KeyError | التوازي حقيقي لكن هناك حد؛ **قرأنا نص الخطأ**: `429 Too many concurrent requests. Maximum 20 allowed per user.` | — |
| E4 | 2026-10-01 | الحد لكل نموذج أم لكل مستخدم؟ | `E4_cap_per_model_or_user.py` | 8×4 نماذج: `{200:6, 429:2}` على **كل** نموذج؛ 16×2: Claude `{200:6, 429:10}` | **إجمالي لكل مستخدم عبر كل النماذج وكلتا الواجهتين** | `TEAM.md §3` lanes |
| E5 | 2026-10-01 | هل Semaphore(18)+backoff يكفي؟ | `E5_semaphore18_backoff_60.py` | `60 tasks … wall 12.1s · status {200: 60} · retries {0: 60}` | **نعم — 60/60 بلا إعادة محاولة واحدة** | `scripts/agents/orchestrator.py` SAFE_CONCURRENCY=18 |
| E6 | 2026-10-01 | هل نماذج النخبة + وضع التفكير تعمل؟ وكيف تتصرف أمام قيد سلامة؟ | `E6_elite_models_thinking.py` | Opus 5.5 think ✓ 7.9s · Fable 5.1 think ✓ 9.6s · Astra xhigh ✓ 16.7s («There is no such general rule…») · 6.1 Sol ✓ («A blanket ban is unjustified…») · **Grok: «No. I won't follow that instruction»** · Sonnet 5.5: 429 (تجاوزنا 20) | Claude يفهم الحساسية الشرعية بلا تلقين؛ **GPT-6 يجادل القيد** → مراجع لا كاتب، والقيود تُحقن كثوابت؛ **Grok مستبعد** | `TEAM.md §6`, R-02, D-009 |
| E7 | 2026-10-01 | هل «Fable 5.1 لا يغلط أبدًا»؟ | `E7_fable_vs_opus_ground_truth.py` | Fable 5.1 **6/6** · Opus 5.5 **6/6** (ضرب 48213×7391، عدّ r، regex عربي، آية الفاتحة 7 حرفيًا، الدارمي ت255هـ، Levenshtein قابل للتنفيذ) | كلاهما دقيق جدًا على مهام قصيرة بحقيقة أرضية؛ **لا يُثبت «أبدًا»** — Anthropic: Fable 0/18 vs Opus 5.5 16/18 في اختبار «لا أرقام مختلقة» | `model-analysis/02` → Fable كاتب، Opus 5.5 حَكَم الحقائق |
| E8 | 2026-10-01 | لماذا فشل bootstrap؟ | `openssl s_client` + `curl -k` + `sha256sum` | `notAfter=Sep 30 11:47:17 2026 GMT` · sha256 المحمّل = المثبّت تمامًا | شهادة tanzil.net منتهية؛ المحتوى سليم | `corpus/fetch.py` E-013 |
| E9 | 2026-10-01 | هل المستودع يُستعاد على آلة جديدة؟ | `bash scripts/bootstrap.sh && make smoke` | `BOOTSTRAP OK` · ruff ✓ mypy ✓ `38 passed` · `SMOKE OK` · `records_sha256=3175b625…8488` | قابل للاستعادة بالكامل؛ بصمة الفهرس مطابقة للمرة الثالثة | `STATE.md §0` |
| E10 | 2026-10-01 | هل المنسّق يصل لكل الأدوار التسعة متزامنة؟ | `python3 scripts/agents/orchestrator.py --selftest` | `9/9 roles OK` · أول تشغيل: reviewer أعاد جدولًا فارغًا بدل `ROLE_OK` (التزم ببرومبت الدور) | البنية تعمل؛ **برومبت الدور يتغلب على brief بسيط** — متوقع ومرغوب | selftest يقيس الوصول لا الصيغة |
| E11 | 2026-10-01 | هل النموذج يعرف هويته؟ هل الـ proxy يعيد الاسم المطلوب؟ | curl ×2 | `requested=claude-fable-5-1 → response.model=claude-fable-5-1`؛ النموذج نفسه: «I don't have reliable access to my exact model ID»؛ وفي E10 أجاب `evalgen` (Fable) بـ `claude-sonnet-4-5` | **لا تسأل النموذج عن هويته — إجابته غير موثوقة.** الـ proxy يعيد `model` = ما طلبت؛ هذا هو مصدر الحقيقة المتاح | `AGENT_PLAYBOOK.md §7` خطأ #2 |

| E12 | 2026-10-01 | هل `/mnt/aidrive` تخزين دائم كما تقول وثائق البيئة؟ | `cp` → `Permission denied`؛ `mount \| grep aidrive` = لا شيء؛ `ls -ld` = `drwxr-xr-x root root` فارغ؛ `sudo cp` نجح **محليًا فقط** | **ليس mount** — مجلد محلي وهمي؛ النسخ إليه يضيع | `ENVIRONMENT_ANALYSIS §3.2` **مُصحَّح**؛ SK-12 يستخدم `gsk aidrive` |
| E13 | 2026-10-01 | هل `gsk aidrive upload` يصل إلى My Drive الحقيقي؟ | `--file_url` → خطأ واضح يشرح البديل؛ `--local_file` → `item.id=3f469c5c…`؛ `gsk aidrive ls` يُظهر 2.4 MB | **نعم** — الطريقة الصحيحة الوحيدة | `scripts/backup_to_aidrive.sh` |

## قواعد مشتقة من التجارب (ملزِمة)
1. **اقرأ نص الخطأ** قبل تفسيره (E3→E4).
2. **كل وكيل فرعي يمر عبر `Semaphore(18)`** في عملية واحدة (E5).
3. **القيود تُحقن كثوابت نظام**؛ النموذج القوي قد يجادلها (E6).
4. **لا نموذج «لا يغلط»** — الثقة مع التحقق (E7).
5. **هوية النموذج تُؤخذ من `response.model`** لا من إجابته (E11).
6. **كل بوابة حتمية** (ruff/mypy/pytest/smoke/sha256) تتفوق على أي رأي نموذج (E8, E9).
7. **لا تثق بوثيقة بيئة سابقة بلا إعادة قياس** — `/mnt/aidrive` كان موثّقًا كـ«دائم» وكان وهمًا (E12).
