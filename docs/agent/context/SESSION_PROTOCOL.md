# SESSION_PROTOCOL.md — طقس الجلسة (مشتق من S-A1, S-A2, S-A4)

## بداية الجلسة (≤10 دقائق)
1. `cd /home/user/webapp && git status -sb && git log --oneline -3` — أين نحن.
2. اقرأ: `AGENTS.md` → `docs/agent/README.md` → `context/IDENTITY.md` → `context/OWNER.md` → `docs/STATE.md §2`.
3. إن كان الـ sandbox جديدًا: `bash scripts/bootstrap.sh && make smoke` (يجب `BOOTSTRAP OK` + `SMOKE OK`).
4. `python3 scripts/agents/orchestrator.py --selftest` — الفريق يصل (9/9).
5. اكتب خطة الجلسة في `docs/STATE.md §2` **قبل** أي كود (S-A4 «explore → plan → code → commit»؛ S-A2 «save plan to Memory»).

## أثناء العمل — لكل حزمة عمل (WP)
```
WP brief (docs/work-packages/WP-NN.md: goal · files · acceptance · constraints · refs)
→ author (Opus 5.5 | Fable 5.1, thinking 16k) writes to .scratch/agents/<run>/
→ reviewer (GPT-6 Astra xhigh) — other family, checklist in brief
→ tester (GPT-6.1 Sol xhigh) — adversarial pytest
→ safety auditor (Opus 5.5 fresh ctx) — if any user-facing string changed
→ orchestrator: apply diff → ruff · mypy --strict · pytest · smoke → commit → merge main → verify
→ update docs/STATE.md §1/§2 + docs/agent/discoveries/ if anything new was learned
```
- **Scale effort to complexity** (S-A2 #3): مهمة بسيطة = وكيل واحد؛ مقارنة = 2–4؛ بحث معقد = 8+ بمسؤوليات مقسّمة بوضوح.
- **Brief واضح** (S-A2 #2): هدف، صيغة مخرجات، أدوات/ملفات، حدود المهمة — وإلا تتكرر الأعمال وتُترك فجوات.
- **Start wide, then narrow** (S-A2 #6) في البحث.
- **Parallel tool calls** (S-A2 #8): استدعاءات مستقلة في كتلة واحدة.
- **جولتا نقاش كحد أقصى** ثم يحسم المنسّق؛ القرار في رسالة الـ commit.
- **اقرأ نص الخطأ** قبل تفسيره (E3→E4).

## إدارة السياق (S-A1)
- لا تحمّل ملفات كاملة إن كفى `grep -n`/`head`؛ **just-in-time retrieval**.
- بعد كل WP: اكتب ملاحظة منظّمة (ماذا تم، ما تبقّى، ما اكتُشف) — هذه هي ذاكرتك عند الـ compaction.
- الوكلاء الفرعيون يعيدون **ملخصًا ≤2k رمز** + مسار الملف؛ التفاصيل في `.scratch/agents/`.
- إن شعرت بـ context rot (تكرار، نسيان قرار سابق): أعد قراءة `STATE.md` و`DECISIONS.md` بدل الاعتماد على الذاكرة.

## نهاية الجلسة (إلزامي)
1. `git status --short` فارغ. كل شيء في `main` ومدفوع.
2. `docs/STATE.md`: التاريخ، ما تم، الترتيب التالي، الحقائق المكتشفة.
3. `docs/agent/discoveries/` إن وُجد اكتشاف جديد؛ `docs/experiments/` إن أُجريت تجربة.
4. سطر واحد للمالك: ما أُنجز، ما التالي، ما يحتاج قراره.
