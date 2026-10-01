# docs/agent/ — ذاكرة الوكيل («الخلايا العصبية»)

> هذا المجلد **خاص بالوكيل المهندس** (أنا ومن يخلفني). كل ما أحتاجه كي أعمل بأعلى المعايير بلا نسيان وبلا هلوسة، منظّمًا كذاكرة طويلة المدى تُحمَّل بالقدر اللازم فقط (مبدأ *progressive disclosure*، Anthropic 2025).
> **قاعدة التحميل:** اقرأ `README` + `context/IDENTITY.md` + `context/OWNER.md` دائمًا (≈3 دقائق). الباقي يُفتح عند الحاجة حسب الجدول أدناه. لا تحمّل كل شيء — *context is a finite resource with diminishing returns* (المصدر S-A1).

## الخريطة (ماذا تفتح ومتى)

| مجلد | محتواه | افتحه عندما |
|---|---|---|
| `context/` | **IDENTITY** (من أنا، ما نموذجي فعلًا، حدودي) · **OWNER** (نوايا المالك الثابتة ولغته) · **RED_LINES** (الخطوط الحمراء المحقونة في كل وكيل) · **SESSION_PROTOCOL** (طقس بداية/نهاية الجلسة) | بداية **كل** جلسة |
| `discoveries/` | ما اكتشفناه بالتجربة عن هذه البيئة: الحدود المقاسة، سلوكيات النماذج، أخطاء وقعنا فيها | قبل أي عمل يتعلق بالوكلاء الفرعيين أو حدود المنصة |
| `research/` | بحوث مُسنَدة بالمصادر الأولية: هندسة السياق، بناء الوكلاء، معايير الهندسة العالمية (كود/اختبار/أمن/مراقبة/واجهة/تسليم)، NLP عربي، بيئة Genspark | عند اتخاذ قرار تقني أو تصميم بروتوكول |
| `skills/` | مهارات قابلة لإعادة الاستخدام كإجراءات مُجرَّبة (SKILL-xx): كيف أشغّل فريقًا، كيف أتحقق من مصدر، كيف أستعيد المستودع… | عند تنفيذ مهمة متكررة |
| `defenses/` | دفاعاتنا ضد أنماط الفشل المعروفة (hallucination, context rot, conformity, injection…) وكيف نكشفها | عند مراجعة مخرجات وكيل، وعند كل دمج |

## مبادئ هذا المجلد (مشتقة من المصادر الأولية في `research/`)
1. **أصغر مجموعة رموز عالية الإشارة** — لا نضع هنا ما يمكن استرجاعه بـ `grep`/`glob` من المستودع (S-A1).
2. **ملاحظات منظّمة خارج السياق** = الذاكرة الحقيقية. تُحدَّث **بعد كل حزمة عمل**، لا نهاية الجلسة فقط (S-A1 «structured note-taking»; S-A2 «save plan to Memory»).
3. **كل ادعاء له مصدر أو تجربة.** صيغة الاقتباس: `[S-xx]` → `research/SOURCES.md`. التجارب: `[E-xx]` → `docs/experiments/`.
4. **الوكلاء الفرعيون يكتبون إلى ملفات ويعيدون مراجع خفيفة**، لا نصوصًا طويلة عبر المنسّق (S-A2 «subagent output to filesystem to minimize the game of telephone»).
5. **التنوع مقصود**: نماذج من عائلات مختلفة لكل حكم، لأن الوكلاء المتماثلين يرتكبون **الخطأ نفسه معًا** (S-A3 «failures from conformity»).

## فهرس المصادر الأولية المقروءة كاملةً (2026-10-01)
| ID | المصدر | ما أخذناه |
|---|---|---|
| S-A1 | Anthropic — *Effective context engineering for AI agents* (Sept 2025) | attention budget، context rot، right altitude، JIT retrieval، compaction، note-taking، sub-agents |
| S-A2 | Anthropic — *How we built our multi-agent research system* (Jun 2025) | orchestrator-worker، 8 مبادئ prompting، token usage = 80% of variance، LLM-as-judge، filesystem artefacts |
| S-A3 | Anthropic — *Patterns and problems in emerging multiagent systems* (Aug 2026) | conformity failures، epistemic failures، turf wars، Sonnet 5 الوحيد الذي يتشارك الكود مع merge عالٍ |
| S-A4 | Anthropic — *Claude Code: Best practices for agentic coding* (Apr 2025) | CLAUDE.md، explore→plan→code→commit، TDD، كاتب/مراجع منفصلان، worktrees، headless fan-out |
| S-A5 | Anthropic — *Writing tools for AI agents with AI agents* (2025) | أدوات قليلة عميقة، namespacing، concise/detailed، أخطاء قابلة للتنفيذ، 25k token cap |
| S-O1 | OpenAI — *A practical guide to building agents* (2025, PDF 34p) | model/tools/instructions، single-agent first، manager vs decentralized، layered guardrails، human-in-the-loop triggers |
| S-G1 | Genspark Help Center — *Genspark Code* | L4 autonomous coding agent، Projects tab، 5 فئات مشاريع |
| S-K1 | Karpathy — *Software 3.0* (Jun 2025, via latent.space / YC) | autonomy slider، keep human in verify loop، «Iron-Man suit» |
| S-R1 | Shinn et al. — *Reflexion* (NeurIPS 2023) · Yang et al. — *SWE-agent* (NeurIPS 2024) | verbal self-reflection in episodic memory؛ agent-computer interface design |
| S-D1 | Google Cloud — *2025 DORA Report* | «AI amplifies what's already there»؛ 30% لا يثقون بكود AI؛ code review time +91% |

التفاصيل والاقتباسات الحرفية في `research/`.
