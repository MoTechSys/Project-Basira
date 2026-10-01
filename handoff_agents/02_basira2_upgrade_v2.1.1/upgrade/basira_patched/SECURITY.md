# SECURITY.md

## الإبلاغ
راسل فريق المشروع عبر Issues الخاصة في GitHub أو البريد المذكور في README. نرد خلال 48 ساعة.

## نموذج التهديد والضوابط
| التهديد | الضابط |
|---|---|
| حقن تعليمات داخل الاقتباس | النموذج لا يتخذ قرارًا؛ المواضع تُعاد مطابقتها حرفيًا (`relocate`)، والحالة من آلة حتمية. اختبار فئة J |
| إغراق الطلبات | `BASIRA_RATE_LIMIT_PER_MIN` (افتراضي 30/دقيقة/IP) · حد النص 5,000 حرف · حد الصورة |
| تسريب بيانات المستخدم | **لا تخزين**: لا قاعدة بيانات، لا سجلات نصوص، الصورة تُحذف من الذاكرة بعد الرد. كشف PII وتحذير قبل الإرسال |
| تسريب أسرار | لا أسرار في المستودع (`.env.example` فقط) · `gitleaks` في CI |
| تبعيات مكشوفة | `pip-audit` + `npm audit` في CI |
| XSS | React يهرّب كل شيء؛ لا `dangerouslySetInnerHTML`؛ النصوص من المدوّنة تُعرض كنص |
| Clickjacking / MIME / Referrer | رؤوس: `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy`, `Content-Security-Policy`, `Strict-Transport-Security` (عند HTTPS) |
| CORS | قائمة أصول صريحة `BASIRA_CORS_ORIGINS` |
| سلامة المدوّنة | `corpus/fetch.py` يتحقق من sha256 لكل ملف ويفشل عند الاختلاف؛ `/health` يعرض `index_sha256` |
| تكرارية النتائج | `determinism_hash` في كل رد = sha256(بصمة الفهرس + المدخل المطبّع + الأحكام) |

## ما لا نجمعه
لا حسابات، لا كوكيز تتبع، لا تحليلات طرف ثالث. عدّادات الاستخدام (إن فُعّلت) في الذاكرة فقط وبلا أي معرّف.
