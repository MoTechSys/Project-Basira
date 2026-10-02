# المساهمة في «بصيرة»

شكراً لاهتمامك! اقرأ هذا قبل فتح PR.

## المبادئ الصارمة

1. **لا كود يولّد نصاً شرعياً من ذاكرة النموذج.**
2. **كل نص مرجعي يُعرض = من المدوّنة بمعرّفه.**
3. **المطابقة حتمية (deterministic) حرف بحرف.**
4. **لا تخزين لبيانات المستخدم.**

مخالفة أي واحدة = PR مرفوض.

## سير العمل

1. افتح issue للمناقشة قبل البدء بميزة كبيرة.
2. أنشئ فرعاً من `main` باسم `feat/...` أو `fix/...`.
3. اكتب اختبارات قبل أو مع الكود (TDD مفضّل).
4. تأكد أن `make test` يمر بـ 100%.
5. تأكد أن `make lint` نظيف.
6. افتح PR بوصف واضح وربطه بالـ issue.

## معايير الكود

### Python (Backend)
- Python 3.11+
- `ruff` + `mypy --strict`
- `pytest` للاختبارات
- Type hints إلزامية

### TypeScript (Frontend)
- `tsc --strict`
- `eslint` + `prettier`
- `vitest` للـ unit
- `playwright` للـ e2e

## الالتزام بالثوابت الشرعية

عند لمس أي كود في `backend/app/match/` أو `backend/app/verify/`:
- أضف اختباراً adversarial جديداً.
- وثّق أي تغيير في `SAFETY.md`.
- أشر إلى الـ invariant المتأثر (I1, I2, ...).

## أسلوب رسائل الـ Commits

نتبع Conventional Commits:
- `feat:` ميزة جديدة
- `fix:` إصلاح خطأ
- `docs:` توثيق
- `refactor:` إعادة هيكلة بلا تغيير سلوك
- `test:` إضافة/تعديل اختبارات
- `chore:` صيانة (dependencies, config)
