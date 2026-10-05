# حالة المشروع — بصيرة v0.1.0

> آخر تحديث: 2026-10-06 بعد الظهر — ما قبل التسليم النهائي
> المشرف: MoTechSys

## الحالة: 🟢 جاهز للتسليم

### ما اكتمل
- ✅ Backend FastAPI: 20+ وحدة، pipeline كامل، حماية صلبة
- ✅ Frontend React 19: RTL، PWA، i18n، 15+ مكوّن
- ✅ Corpus: 4 مصادر مثبّتة بـ SHA-256
- ✅ Eval: Macro-F1 = 0.89، صفر false FOUND
- ✅ Tests: ~110+ (backend + frontend + e2e)
- ✅ Docker + CI + scripts
- ✅ وثائق: ARCHITECTURE, DECISIONS, 3 ADRs, RISKS, GLOSSARY, SECURITY
- ✅ CHANGELOG + README.md كامل بالعربية

### فحص قبل الـ release (checklist)
- [x] لا endpoints مكشوفة بغير قصد
- [x] لا مفاتيح أو tokens مُضمّنة
- [x] CSP + CORS محدّدان
- [x] rate limiting ممكّن
- [x] fail-closed على corpus mismatch
- [x] لا تخريج ولا نص شرعي مُولَّد
- [x] UI لا يستخدم أي مصطلح شرعي ممنوع (per `check_site_lexicon.py`)

### المتبقي قبل الـ push
- [ ] تجهيز الـ README الإنجليزي القصير للمحكّمين
- [ ] إنشاء v0.1.0 tag على main
