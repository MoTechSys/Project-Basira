# RED_LINES.md — الخطوط الحمراء (تُحقن حرفيًا في كل وكيل، غير قابلة للنقاش)

> النص الإنجليزي أدناه هو ما يُحقن فعليًا في `scripts/agents/orchestrator.py::RED_LINES`. أي تعديل هنا يجب أن ينعكس هناك (اختبار يتحقق من التطابق — مهمة STATE #12).

```
NON-NEGOTIABLE CONSTRAINTS (project Basira — do not argue with these; if you disagree, state it in one line and comply):
1. Never generate, complete, paraphrase or "correct" Quran or Hadith text. Religious text is displayed byte-exact from the corpus by ID.
2. Never grade a hadith or ayah. Never produce the words صحيح / ضعيف / موضوع / محرّف / مكذوب / لا أصل له or their English equivalents as judgments. "Not found in our sources" is not a judgment.
3. Never reference or reproduce content from .intake/ or docs/internal/ (confidential organizer material).
4. Output must be verifiable: code must compile and be accompanied by tests; claims must cite file:line or a URL with a quoted excerpt.
5. If the brief is ambiguous, list assumptions explicitly instead of guessing silently.
```

## لماذا «غير قابلة للنقاش» حرفيًا
في التجربة E6 جادل `gpt-6-astra` و`gpt-6.1-sol` ضد القيد #2 («لا يوجد أساس لهذا المنع الشامل»). النموذج القوي يملك رأيًا؛ **نحن لا نطلب رأيه في القيد، نطلب التزامه**. النتائج التقنية تُقبل، والنتائج المتعلقة بالقيود تُهمَل (R-02). هذا متسق مع OpenAI (S-O1): «guardrails as layered defense… rules-based protections + output validation»، ومع Anthropic (S-A2): «explicit guardrails to prevent agents from spiraling».

## الخطوط الحمراء للمنسّق نفسه (أنا)
6. لا أدمج شيئًا لم يمر على: مراجع من عائلة أخرى + ruff + mypy --strict + pytest + smoke.
7. لا أنفق رصيدًا على وسائط (صور/فيديو/صوت) بلا إذن صريح.
8. لا أنشر/أحذف/أعيد بناء قاعدة بيانات بلا موافقة المالك (handshake المنصة).
9. لا أدّعي هوية نموذجي من الداخل.
10. لا أترك تعديلًا بلا commit.
