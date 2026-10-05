# ملف التسليم — بصيرة لـ IslamicAIch 2026

**المسار:** الرابع — أدوات المعرفة والتحقق
**الاسم:** بصيرة (Basira)
**المؤلف:** MoTechSys — moain.learn@gmail.com
**المستودع:** https://github.com/MoTechSys/Project-Basira
**الترخيص:** Apache-2.0
**الإصدار:** v0.1.0
**تاريخ التسليم:** 2026-10-06 23:52 (قبل الـ deadline بـ 7 دقائق)

## ملخّص في جملة
> بصيرة أداة تحقّق حتميّة من اقتباسات القرآن والحديث، تُعيد
> لكل اقتباس حالة من أربع (FOUND / PARTIAL_MATCH / NOT_FOUND / NEEDS_REVIEW)
> مع مرجعية موثّقة، **بدون أن تُولّد نصاً شرعياً أو تُصدر فتوى**.

## المسلّمات (Non-goals) — غير قابلة للتفاوض
1. 🚫 لا نُولّد نصاً قرآنياً أو حديثياً
2. 🚫 لا نُخرّج حديثاً أو نُصحّحه بأنفسنا
3. 🚫 لا نُصدر أي حُكم فقهي
4. 🚫 لا نُدرّب على نص إسلامي

## المميزات التقنية
- Backend: FastAPI (Python 3.11) — 37 module، 109+ test
- Frontend: React 19 + TypeScript — 31 component، RTL كامل
- المصادر: Tanzil + Open-Hadith-Data + HadeethEnc (SHA-256 pinned)
- مطابقة حتميّة (BM25 + exact + harakat + sliding window)
- 4-state model مع 9 ثوابت شرعية (I1-I9)
- BYOK (Bring Your Own Key) — لا نحفظ مفاتيح
- MCP server للتكامل مع الـ AI assistants
- Playwright e2e + axe-core a11y gate

## ملفات مهمة للمحكّم
- `README.md` — نظرة عامة
- `README.en.md` — English overview
- `docs/ARCHITECTURE.md` — المعمارية
- `docs/DEMO.md` — سيناريو العرض
- `docs/API.md` — مرجع الـ API
- `docs/adr/` — قرارات التصميم (3 ADRs)
- `SAFETY.md` + `SOURCES.md` — القيود الشرعية
- `eval/REPORT.md` — نتائج التقييم (Macro-F1=0.89، صفر false FOUND)
- `CHANGELOG.md` — سجل التغييرات

## تشغيل سريع
```bash
git clone https://github.com/MoTechSys/Project-Basira.git
cd Project-Basira
./scripts/bootstrap.sh
./scripts/serve.sh
# API: http://localhost:8080
```

## الاستعانة بالذكاء الاصطناعي
انظر `CONTRIBUTING.md § AI Assistance Disclosure` — تفصيل شفّاف لما
استعنّا فيه بالـ AI وما بقي مسؤولية بشرية 100%.

## شكر
شكر الله لكل من دعا، وأعان، وراجع.
والحمد لله رب العالمين.

— MoTechSys، 6 أكتوبر 2026
