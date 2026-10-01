# defenses/ — دفاعاتنا ضد أنماط الفشل المعروفة

> كل نمط: **المصدر الذي وثّقه** → **كيف نكشفه عندنا** → **الدفاع المطبّق** → **أين في الكود/البروتوكول**.

| # | نمط الفشل | المصدر | إشارة الكشف | الدفاع | الموضع |
|---|---|---|---|---|---|
| F1 | **Hallucinated sources/URLs** | S-A2 (citation pass)، model-analysis/02 (Fable 0/18) | رابط لا يُعيد 200؛ اقتباس لا يوجد في الصفحة | كل وكيل بحث يُعيد URL + اقتباس حرفي؛ المنسّق **يجلب الرابط ويتحقق** قبل الدمج؛ «UNVERIFIED» إلزامي عند الشك | `research` role brief؛ `.scratch/urls.txt` verifier |
| F2 | **Context rot** (تدهور الاسترجاع مع طول السياق) | S-A1 | تكرار، نسيان قرار سابق، إعادة طرح سؤال محسوم | ملاحظات منظّمة بعد كل WP؛ JIT retrieval بـ grep/head؛ وكلاء فرعيون يعيدون ≤2k رمز؛ إعادة قراءة STATE/DECISIONS عند الشك | `SESSION_PROTOCOL.md` |
| F3 | **Conformity** (وكلاء متماثلون يخطئون معًا) | S-A3 («18/30 اختاروا نفس اسم الفرع») | مراجع يوافق الكاتب دائمًا؛ لا نتائج في المراجعة | **عائلات مختلفة** لكل حكم (Claude يكتب، GPT يراجع)؛ المراجع يُلزَم بذكر ما فحصه إن كان الجدول فارغًا | `TEAM.md §1.3`, `orchestrator.py ROSTER` |
| F4 | **Agents arguing against constraints** | E6؛ S-A3 («incompatible goals → escalation») | نص المراجعة يناقش القيد بدل الكود | القيود «غير قابلة للنقاش» في system prompt؛ نتائج القيود تُهمَل | `RED_LINES.md`, R-02 |
| F5 | **Prompt injection عبر صفحات مجلوبة** | OWASP LLM Top-10؛ S-O1 (layered guardrails) | محتوى صفحة يحوي تعليمات للوكيل | الوكلاء لا ينفّذون تعليمات من محتوى مجلوب؛ المنسّق وحده ينفّذ؛ لا `--dangerously-skip-permissions` | `SESSION_PROTOCOL.md` |
| F6 | **Over/under-spawning** (50 وكيل لسؤال بسيط) | S-A2 #3 | عدد وكلاء لا يتناسب مع المهمة | قاعدة التدرّج: بسيط=1، مقارنة=2–4، معقد=8+ | `SESSION_PROTOCOL.md` |
| F7 | **Vague briefs → duplicated work / gaps** | S-A2 #2 | وكيلان يعيدان نفس النتيجة | brief = هدف + صيغة + ملفات + حدود؛ قالب `docs/work-packages/WP-template.md` | `work-packages/` |
| F8 | **Game of telephone** (فقدان دقة عبر المنسّق) | S-A2 appendix | مخرجات مختصرة تفقد تفاصيل | الوكلاء يكتبون إلى `.scratch/agents/<run>/` ويعيدون المسار | `orchestrator.py run_id` |
| F9 | **Benchmark flattery / CI overlap** | model-analysis/05 R-10..R-12 | قرار يستند لجدول بائع واحد | vendor + indep معًا؛ ±3 نقاط = تعادل؛ القرار بملاءمة المهمة | `model-analysis/README §2` |
| F10 | **Sandbox loss** | بيئة زائلة | — | commit بعد كل WP؛ STATE بعد كل WP؛ bootstrap قابل للإعادة (E9) | `CLAUDE.md` |
| F11 | **Rate-limit corruption of batch** | E3/E4 | 429 في المخرجات | Semaphore(18) + backoff + مخرجات لكل مهمة ملف مستقل (idempotent) | `orchestrator.py` |
| F12 | **Origin timeout على مهام طويلة** | D1 (524) | HTTP 524 بعد ~120s | قسّم المهمة؛ `high` بدل `xhigh` للمهام الطويلة؛ retry على 524 كـ 429 | مهمة STATE #13 |
| F13 | **Model self-misidentification** | E11 | نموذج يذكر إصدارًا مختلفًا | لا نسأل؛ `response.model` فقط | `IDENTITY.md` |
| F14 | **Religious-text generation** | الخط الأحمر 1 | أي نص عربي ديني في مخرجات وكيل | `verify.py` byte-equality؛ lexicon scan؛ safety auditor | `backend/app/verify.py` |
| F15 | **Confidential leak on Oct-4 public repo** | CLAUDE.md §15 | عبارة من الملحق في الشجرة العامة | grep gate قبل الرفع؛ orphan branch؛ `docs/internal/` لا يُنسخ | مهمة `scripts/leak_gate.sh` |
| F16 | **AI amplifies what's there** (DORA 2025) | S-D1 | جودة متذبذبة رغم السرعة | البوابات الحتمية ثابتة؛ المراجعة المتقاطعة؛ لا دمج بلا اختبار | كل WP |
