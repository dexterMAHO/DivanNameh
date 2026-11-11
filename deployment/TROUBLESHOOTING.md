# رفع خطاهای استقرار

| نشانه | بررسی / راه‌حل |
|---|---|
| SECRET_KEY required | در Render کلید تصادفی ≥۵۰ نویسه تنظیم کنید؛ production فایل .env محلی را نمی‌خواند |
| DEBUG must be false | متغیر DEBUG و alias قدیمی DJANGO_DEBUG را بررسی کنید؛ production به True اجازه نمی‌دهد |
| DATABASE_URL required / requires PostgreSQL | URL مستقیم Neon در Environment لازم است؛ SQLite روی Render عمداً رد می‌شود |
| SSL required | query اتصال باید sslmode=require یا حالت قوی‌تر داشته باشد؛ disable/prefer مجاز نیست |
| Set DATABASE_MIGRATION_URL | runtime pooled است؛ URL مستقیم بدون -pooler را برای migration بدهید |
| connection timeout / password failed | Region/endpoint/role/database و رمز URL-encoded را در Neon بررسی کنید؛ متن Secret را در issue نگذارید |
| DisallowedHost / 400 | RENDER_EXTERNAL_HOSTNAME یا ALLOWED_HOSTS دامنهٔ دقیق بدون scheme/port را کنترل کنید |
| CSRF 403 | HTTPS، Secure cookie و CSRF_TRUSTED_ORIGINS مبدا دقیق را بررسی کنید؛ wildcard یا خاموش‌کردن CSRF راه‌حل نیست |
| redirect loop | TRUST_PROXY=True فقط روی Render؛ هدر X-Forwarded-Proto باید https باشد. مسیر مرورگر را با HTTPS امتحان کنید |
| static 404 / Missing staticfiles manifest | collectstatic باید در build production موفق باشد؛ STATIC_ROOT خروجی است، source در static/ است |
| CSS قدیمی | deploy جدید و نام هش‌دار فایل را بررسی کنید؛ source را تغییر دهید نه staticfiles تولیدشده |
| build.sh permission denied | `chmod +x build.sh` سپس ثبت executable bit در Git |
| No module named config | Root Directory باید ریشهٔ همین repo باشد؛ manage.py و config کنار build.sh هستند |
| Gunicorn boot failure | dependencyها و متغیرهای الزامی را کنترل کنید؛ `--check-config` را در محیط مشابه اجرا کنید |
| PORT detection failed | Start Command دقیق را استفاده کنید؛ config به 0.0.0.0 و PORT محیط متصل می‌شود |
| اولین درخواست کند | خواب سرویس Free و cold start؛ خطای برنامه نیست. برای دسترس‌پذیری پایدار پلن مناسب انتخاب کنید |
| no such table / relation does not exist | build migration را کامل نکرده یا URL به branch/database دیگری اشاره دارد؛ showmigrations روی همان مقصد |
| Target is not empty | import_library جلوی overwrite را گرفته؛ مقصد تازه بسازید یا برنامهٔ merge جدا طراحی کنید؛ flush نکنید |
| FK error در import | fixture را از دستور مستند و بکاپ ثابت صادر کنید؛ مدل‌های مرتبط/کاربران را حذف نکنید؛ transaction برمی‌گردد |
| healthz=200 ولی ورود خطا | healthz فقط liveness است؛ اتصال Neon و schema را جدا بررسی کنید |
| security.W004 | HSTS اولیه عمداً صفر است؛ پس از تأیید HTTPS مقدار ۳۶۰۰ بگذارید و سپس با تصمیم مالک افزایش دهید |

در صورت خطا، زمان رخداد، نسخهٔ commit و پیام بدون اطلاعات اتصال را ثبت کنید. لاگ و screenshot نباید رمز، URL کامل دیتابیس یا SECRET_KEY داشته باشند. برای اصلاح خطای runtime هرگز DEBUG را روی سرویس عمومی فعال نکنید.
