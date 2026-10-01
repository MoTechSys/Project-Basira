# AGENT_PLAYBOOK.md — كيف تكتشف قدراتك في 10 دقائق وتشغّل فريقًا متعدد النماذج

> **لمن:** أي وكيل ذكاء اصطناعي جديد (أي حساب، أي جلسة) يستلم هذا المشروع في بيئة Genspark AI Developer.
> **الهدف:** لا تُعِد الاكتشاف من الصفر. هذا الملف يعطيك **الطريقة** (الأوامر الجاهزة) و**النتائج التي حصلنا عليها** (حتى تقارن)، و**الأخطاء التي وقعنا فيها** (حتى لا تكرّرها).
> **القاعدة الذهبية:** كل ما تدّعيه عن نفسك يجب أن يكون ناتج أمر شغّلته. **لا تخمّن قدراتك.**
> English summary at the end (§9).

---

## 0. ترتيب القراءة الإلزامي (≈15 دقيقة)
1. `AGENTS.md` → 2. هذا الملف → 3. `docs/STATE.md` → 4. `docs/DECISIONS.md` → 5. `docs/TEAM.md` + `docs/model-analysis/06-roster-decision.md` → 6. `docs/adr/`.
ثم نفّذ **§1** قبل أي شيء آخر.

---

## 1. اكتشاف الذات والبيئة (5 دقائق) — انسخ ونفّذ

### 1.1 الآلة
```bash
cd /home/user/webapp && pwd && ls -la
cat /etc/os-release | head -2; uname -r; nproc; free -h | head -2; df -h / | tail -1
whoami; sudo -n true && echo "sudo: passwordless OK"
ulimit -n   # 1024 → ارفعه لـ Vite: ulimit -n 65536
```
**ما وجدناه (2026-10-01):** Debian 13 · 4 vCPU · 7.8 GB RAM (**swap 127 MB فقط — احذر العمليات الثقيلة**) · 20 GB حر · sudo بدون كلمة مرور.

### 1.2 الأدوات
```bash
for t in python3 node npm java gcc make git gh wrangler pm2 gsk ffmpeg convert pdftotext markitdown jq; do
  command -v $t >/dev/null && printf "%-11s ✓ %s\n" $t "$($t --version 2>&1 | head -1 | cut -c1-40)" || printf "%-11s ✗\n" $t; done
npm ls -g --depth=0 2>/dev/null | tail -n +2
pip3 list 2>/dev/null | wc -l
gh auth status 2>&1 | head -3
```
**ما وجدناه:** Python 3.13 · Node 22 · Java 21 (JRE فقط) · GCC 14 · git 2.47 · `gh` مسجّل كـ **MoTechSys** · wrangler 4 · pm2 7 · gsk 1.13 · ffmpeg/ImageMagick/pdftotext · 239 حزمة pip. **غير موجود:** Docker (مستحيل)، Go/Rust/Bun (قابل للتثبيت).

### 1.3 الشبكة وGit
```bash
for u in https://registry.npmjs.org https://pypi.org https://api.github.com; do curl -s -m 5 -o /dev/null -w "$u %{http_code}\n" $u; done
git remote -v; git branch -a; git log --oneline -3
```

### 1.4 مفاتيح النماذج (الأهم)
```bash
env | grep -E "^(ANTHROPIC|OPENAI|GSK)_" | sed 's/=.*/=***/'
echo "$ANTHROPIC_BASE_URL"; echo "$OPENAI_BASE_URL"
```
**ما وجدناه:** `ANTHROPIC_BASE_URL=https://www.genspark.ai/api/anthropic` و `OPENAI_BASE_URL=https://www.genspark.ai/api/llm_proxy/v1` + مفاتيح. **هذا يعني أن لديك واجهتي API كاملتين لتشغيل وكلاء فرعيين.** إن لم تكن موجودة: المالك يفعّلها من **Project → API Keys → Inject**.

### 1.5 الـ Skills وأداة gsk
```bash
gsk list-tools --output json | python3 -c "import json,sys;d=json.load(sys.stdin);t=d.get('tools',d);print(len(t),'gsk tools')"
gsk me --output text | head -6          # الحساب والرصيد
gsk capabilities --output text | head -20
ls /mnt/skills 2>/dev/null               # تُملأ عند التفعيل فقط
```
**ما وجدناه:** **300 أداة** في gsk (بحث، crawl، وسائط، Cloudflare hosted، Google/Slack/Notion/GitHub connectors، `create_task` لوكلاء Genspark المتخصصين، `consult_advisor`، `batch_web_search`…). الـ Skills الأربع: `gsk-hosted-deploy`، `gsk-hosted-identity`، `cf-byok-deploy`، `designer-handoff` — تُفعَّل بـ `activate_ai_developer_skill`.

---

## 2. اكتشاف النماذج المتاحة (دقيقة واحدة)

```bash
# القائمة الرسمية الحية (لا تخمّن — اقرأها)
curl -s "$OPENAI_BASE_URL/models" -H "Authorization: Bearer $OPENAI_API_KEY" | jq -r '.data[].id' | sort
# اختبار نبض لكلا الواجهتين
curl -s "$ANTHROPIC_BASE_URL/v1/messages" -H "x-api-key: $ANTHROPIC_API_KEY" -H "anthropic-version: 2023-06-01" -H "content-type: application/json" \
  -d '{"model":"claude-opus-5-5","max_tokens":10,"messages":[{"role":"user","content":"Say OK"}]}' | jq -r '.content[0].text'
curl -s "$OPENAI_BASE_URL/chat/completions" -H "Authorization: Bearer $OPENAI_API_KEY" -H "content-type: application/json" \
  -d '{"model":"gpt-6-astra","messages":[{"role":"user","content":"Say OK"}]}' | jq -r '.choices[0].message.content'
```
**ما وجدناه:** 70 نموذجًا. الأقوى المتاح (مع البحث المُسنَد في `docs/model-analysis/`): `claude-opus-5-5`، `claude-fable-5-1`، `gpt-6-astra`، `gpt-6.1-sol`. **غير متاح:** Gemini، `claude-sonnet-5-1`، `claude-opus-4-1`.

**تنسيق الطلب:**
- Anthropic: `{"model","max_tokens","messages",["thinking":{"type":"enabled","budget_tokens":N}]}` → الرد في `content[].text` (و`content[].type=="thinking"` إن فُعّل).
- OpenAI: `{"model","messages",["reasoning_effort":"low|medium|high|xhigh"]}` → `choices[0].message.content`.

---

## 3. اكتشاف حد التوازي (دقيقتان) — **لا تفترض، قِس**

```python
# .scratch/parallel_probe.py  (انسخه كما هو)
import asyncio, os, httpx, collections, time
A=os.environ["ANTHROPIC_BASE_URL"]+"/v1/messages"; H={"x-api-key":os.environ["ANTHROPIC_API_KEY"],"anthropic-version":"2023-06-01"}
async def call(c,i):
    r=await c.post(A,headers=H,json={"model":"claude-opus-5-5","max_tokens":10,"messages":[{"role":"user","content":f"Say OK {i}"}]})
    return r.status_code, r.text[:120]
async def main(n):
    async with httpx.AsyncClient(timeout=120) as c:
        t=time.perf_counter(); res=await asyncio.gather(*[call(c,i) for i in range(n)]); wall=time.perf_counter()-t
    print(n,"concurrent →",dict(collections.Counter(r[0] for r in res)),f"{wall:.1f}s")
    for r in res:
        if r[0]!=200: print("  ",r[1]); break
asyncio.run(main(32))
```
**ما وجدناه:** `429 — "Too many concurrent requests. Maximum 20 allowed per user."` — الحد **20 طلبًا متزامنًا لكل مستخدم، مشترك بين كل النماذج وكلتا الواجهتين**. ليس لكل نموذج.

**القاعدة المشتقة (مُختبَرة 60/60 نجاح):**
```python
SEM = asyncio.Semaphore(18)          # هامش أمان تحت 20
# عند 429: sleep 0.5 * 2**attempt, حتى 4 محاولات
```
التسريع المقاس: **×15.6** مقابل التنفيذ المتسلسل. الإنتاجية المستدامة ≈ 5 مهام قصيرة/ثانية.

---

## 4. طريقتان لتشغيل وكلاء فرعيين

### 4.1 الطريقة الأساسية: API مباشر (تحكّم كامل، تفكير أقصى)
القالب الكامل في `scripts/agents/orchestrator.py` (انظر §6). الجوهر:
```python
async def run_agent(role, brief, files):          # role من docs/TEAM.md
    model, mode = ROSTER[role]                     # مثال: ("claude-opus-5-5", {"thinking":{"type":"enabled","budget_tokens":16000}})
    system = RED_LINES + ROLE_PROMPTS[role]        # الخطوط الحمراء تُحقن دائمًا كثوابت
    async with SEM:
        return await call(model, system, brief + attach(files), **mode)
```
**متى:** كل عمل بصيرة (كود، مراجعة، اختبارات، بحث، وثائق).

### 4.2 الطريقة الثانوية: وكلاء Genspark المتخصصون عبر `gsk create_task`
```bash
gsk list-tools --output json | python3 -c "import json,sys;[print(t['description'][:300]) for t in json.load(sys.stdin)['tools'] if t['name']=='create_task']"
```
أنواع: `super_agent`، `deep_research`، `docs`، `slides`، `website`، `cross_check`، `video/audio_generation`، `custom_super_agent`. **لا يرثون سياقك** — ضع كل شيء في `query`. يُنشئون مهمة مستقلة لها `task_url`. **متى:** بحث عميق طويل، عرض تقديمي للتسليم، فحص متقاطع (`cross_check`) لمستند نهائي.

### 4.3 مستشار أقوى عند التعثر
`gsk consult_advisor --focus "..." --transcript "..."` — يستدعي نموذجًا أقوى لإرشاد قصير. استخدمه عند تغيير النهج أو بعد ملاحظات جوهرية من المالك.

---

## 5. ما اختبرناه فعلًا (سجل التجارب — الدليل أننا لم نخمّن)

| # | التجربة | الطريقة | النتيجة | الملف |
|---|---|---|---|---|
| E1 | نبض Anthropic + OpenAI | curl | `PONG` من كليهما | `CAPABILITIES.md §1` |
| E2 | 9 أسماء Claude | حلقة curl | 7 تعمل، `opus-4-1` و`sonnet-5-1` مرفوضان | `CAPABILITIES.md §1.1` |
| E3 | 32 وكيل / 6 نماذج بلا كبح | asyncio | 2.7 ث، ×15.6، 12 فشل → **قرأنا رسالة الخطأ**: حد 20/مستخدم | `CAPABILITIES.md §2` |
| E4 | هل الحد لكل نموذج؟ | 8×4 ثم 16×2 | 429 على كل النماذج → **إجمالي** | `CAPABILITIES.md §2` |
| E5 | Semaphore(18)+backoff، 60 مهمة | asyncio | **60/60 نجاح، 0 إعادة، 12.1 ث** | `CAPABILITIES.md §2` |
| E6 | نماذج النخبة + وضع التفكير | 15 استدعاء متوازٍ | Opus 5.5/Fable 5.1 thinking يعمل؛ GPT-6 `xhigh` يعمل؛ **Astra/Sol جادلا ضد قيد سلامة**؛ **Grok رفض تعليمة بريئة** | `TEAM.md §6` |
| E7 | Fable 5.1 vs Opus 5.5 — 6 مهام بحقيقة أرضية محلية (حساب، عدّ، regex، آية، مؤلف الدارمي، Levenshtein قابل للتنفيذ) | asyncio + تحقق بالكود | **6/6 لكليهما** | هذا الملف §5 |
| E8 | شهادة tanzil.net منتهية | openssl + curl + sha256 | الملف مطابق للبصمة المثبّتة → حل E-013 | `DECISIONS.md E-013` |
| E9 | bootstrap + smoke على sandbox جديد | `bash scripts/bootstrap.sh && make smoke` | BOOTSTRAP OK · 38/38 · SMOKE OK · بصمة الفهرس مطابقة للمرة الثالثة | `STATE.md §0` |

> **درس E6:** النموذج القوي ليس مرادفًا للطاعة. GPT-6 جادل ضد الخط الأحمر «لا تقل محرّف». لذلك القيود تُحقن كـ**ثوابت نظام غير قابلة للنقاش**، والنتائج المتعلقة بالقيود تُهمَل مع إبقاء النتائج التقنية (مخاطرة R-02).
> **درس E7:** «لا يغلط أبدًا» غير قابل للإثبات؛ 6/6 على مهام قصيرة لا يعني 0 خطأ في 5000 سطر. Anthropic نفسها: Fable 5.1 رسب 0/18 في اختبار «لا أرقام مختلقة» بينما Opus 5.5 نجح 16/18. **الخلاصة: الثقة + التحقق، لا أحدهما.**

---

## 6. البروتوكول التشغيلي للفريق (مختصر — التفصيل في `TEAM.md`)

```
brief (docs/work-packages/WP-NN.md)
  → author (Opus 5.5 | Fable 5.1, thinking 16k)
  → reviewer من عائلة أخرى (GPT-6 Astra, xhigh)
  → test engineer (GPT-6.1 Sol, xhigh)
  → safety auditor إن كان نصًا للمستخدم (Opus 5.5 سياق جديد)
  → المنسّق: ruff · mypy --strict · pytest · smoke → commit → merge main → verify
```
- جولتا نقاش كحد أقصى ثم يحسم المنسّق؛ القرار يُذكر في رسالة الـ commit.
- مخرجات الوكلاء **لا تدخل git**؛ فقط الملفات المُتحقَّق منها.
- **الخط الأحمر لكل وكيل:** لا يولّد نصًا دينيًا، لا يحكم، لا يسرّب `.intake/` أو `docs/internal/`.

---

## 7. أخطاء وقعنا فيها — لا تكرّرها
1. **بدأنا العمل قبل تحليل الذات.** المالك طلب «حلّل بيئتك أولًا» وقفزنا للمشروع. → افعل §1 **قبل** أي تعديل.
2. **ادّعينا اسم النموذج الذي يشغّلنا** («سونيت 5.1») بناءً على كلام المالك. → لا تعرف نموذجك من الداخل؛ قل ذلك صراحة.
3. **قدّمنا تشكيلة بنماذج ضعيفة** لأنها متاحة. → المالك: «الأقوى فقط». الاختيار **بالبحث المُسنَد** لا بالتوفر (D-009).
4. **افترضنا أن 429 خطأ عابر** قبل قراءة نص الرسالة. → اقرأ `r.text` دائمًا.
5. **نسينا ملفات خارج `backend/` في lint** (`corpus/`, `scripts/`). → STATE §2 مهمة #11.

---

## 8. المالك: نواياه الثابتة (حتى لا تُعيد السؤال)
- شغل **مؤسسات** لا أفراد؛ **الرصيد لا يهم**؛ **الدقة قبل كل شيء**؛ **لا هلوسة**.
- أنت **أداة تحت إدارته** (D-006)؛ العمل عمله.
- **لا PR** — ادمج في `main` مباشرة بعد التحقق (D-001).
- يوم **4 أكتوبر** مستودع جديد «كأنه بدأ اليوم» (D-002) — لا شيء بتاريخ سابق يدخل المستودع العام.
- وثّق **كل** تجربة وقرار؛ حدّث `STATE.md` نهاية كل جلسة.

---

## 9. English summary
This playbook lets any new agent become fully operational in ~10 minutes **without re-discovering**: (1) run the self-discovery commands in §1 (machine, tools, model keys, 300 `gsk` tools, 4 skills); (2) list live models from `$OPENAI_BASE_URL/models` — never assume; (3) **measure** concurrency: the platform cap is **20 in-flight requests per user across all models**; use `Semaphore(18)` + exponential backoff (verified 60/60); (4) spawn sub-agents via direct Anthropic/OpenAI proxies (full control, max reasoning) or via `gsk create_task` for Genspark specialist agents; (5) the experiment log proves every claim; (6) team protocol: author → other-family reviewer → tests → safety audit → orchestrator gates → merge; (7) mistakes we made so you don't; (8) owner's standing intents. Roster and evidence: `docs/TEAM.md`, `docs/model-analysis/`.
