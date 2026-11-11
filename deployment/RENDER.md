# ایجاد Web Service در Render

## پیش‌نیاز GitHub

مخزن فعلی: `https://github.com/dexterMAHO/DivanNameh`، شاخهٔ `main`، WSGI واقعی: `config.wsgi:application`.

فایل‌های جدید استقرار هنوز توسط این کار commit/push نشده‌اند. ابتدا diff را مرور کنید و خودتان تأیید و منتشر کنید. `git status` و `git diff --check` را کنترل کنید. `.env`، `.env.neon`، db.sqlite3، backups، exports و staticfiles نباید stage شوند. اگر در آینده Secret وارد تاریخچه شد، ابتدا آن را rotate کنید؛ حذف از آخرین commit کافی نیست.

## روش اول: Blueprint

1. وارد [Render Dashboard](https://dashboard.render.com/) شوید.
2. New → Blueprint و مخزن GitHub بالا را با دسترسی محدود به همین repo متصل کنید.
3. شاخهٔ main و فایل render.yaml را انتخاب کنید.
4. مقادیر SECRET_KEY تصادفی و DATABASE_URL مستقیم Neon را در فیلدهای محرمانه وارد کنید.
5. Free، Region=Frankfurt و دستورات build/start را بازبینی کنید. اگر Neon در منطقهٔ دیگری ساخته‌اید، region فایل را **قبل از ساخت** تغییر دهید؛ region سرویس بعداً قابل تغییر نیست.
6. ایجاد سرویس و اولین deploy را خودتان تأیید کنید.

Blueprint فقط یک Web Service تعریف می‌کند؛ Render Postgres یا دیسک/سرویس پولی نمی‌سازد. نام سرویس پیشنهادی divannameh است؛ hostname نهایی توسط Render تعیین و با RENDER_EXTERNAL_HOSTNAME به Django داده می‌شود.

## روش دوم: تنظیم دستی

New → Web Service → اتصال مخزن:

| فیلد | مقدار |
|---|---|
| Runtime | Python 3 |
| Branch | main |
| Root Directory | خالی؛ manage.py در ریشه است |
| Region | Frankfurt یا نزدیک‌ترین گزینه به Neon |
| Instance Type | Free در صورت دسترس‌بودن |
| Build Command | `./build.sh` |
| Start Command | `python -m gunicorn config.wsgi:application --config gunicorn.conf.py` |
| Health Check Path | `/healthz/` |
| Auto Deploy | On Commit |

نسخه Python با `.python-version` روی 3.13.5 (نسخهٔ تست‌شدهٔ محلی) ثابت شده است. اگر در Render متغیر PYTHON_VERSION دارید، نباید با فایل تعارض داشته باشد؛ env اولویت دارد. [انتخاب نسخه Python](https://render.com/docs/python-version)

متغیرهای لازم:

```text
DJANGO_ENV=production
DJANGO_SETTINGS_MODULE=config.settings_production
DEBUG=False
SECRET_KEY=<generated secret, at least 50 characters>
DATABASE_URL=<direct Neon connection with SSL>
TRUST_PROXY=True
DB_CONN_MAX_AGE=0
WEB_CONCURRENCY=2
APP_TIME_ZONE=Asia/Tehran
```

ALLOWED_HOSTS و CSRF_TRUSTED_ORIGINS برای دامنهٔ اصلی Render خودکارند. برای دامنهٔ سفارشی، هر دو را طبق ENVIRONMENT.md اضافه کنید. `*` مجاز نیست. اگر URL pooled انتخاب شده DATABASE_MIGRATION_URL مستقیم هم الزامی است.

## پس از build

لاگ باید نصب requirements، check، collectstatic و migrate موفق را نشان دهد؛ سپس Gunicorn به `0.0.0.0:$PORT` گوش می‌دهد. فایل config پورت را از محیط می‌خواند. سلامت `/healthz/` فقط فرایند برنامه را می‌سنجد و به دیتابیس کوئری نمی‌زند؛ برای سلامت دیتابیس، ورود و کتابخانه را جدا بررسی کنید.

در مرورگر HTTPS:
- `/healthz/` باید `{"status":"ok"}` بدهد.
- `/login/` باید فارسی، با CSS و فونت صحیح باشد.
- ورود، خروج، ذخیرهٔ شعر و مرور باید کار کنند.
- HTTP به HTTPS هدایت شود و HTTPS وارد حلقهٔ redirect نشود.

برای ساخت حساب اولیه (فقط اگر منتقل نشده):

```bash
python scripts/neon_manage.py --env-file .env.neon createsuperuser
```

رمز به‌صورت تعاملی خوانده می‌شود. ساخت superuser در build یا از رمز ثابت محیط انجام نمی‌شود. Render Free دسترسی Shell ندارد؛ helper از سیستم محلی به Neon وصل می‌شود. [محدودیت‌های Free](https://render.com/docs/free)

پس از اطمینان از HTTPS، `SECURE_HSTS_SECONDS=3600` را تنظیم و redeploy کنید؛ includeSubDomains و preload فعلاً False بمانند. هیچ proxy ناشناس نباید بتواند هدر Forwarded را جعل کند؛ اعتماد به proxy برای Render یا reverse proxy کنترل‌شده است.

## به‌روزرسانی

هر commit بعدی به main با autoDeployTrigger=commit build می‌شود. ابتدا تست‌ها را اجرا و migration را بررسی کنید. push فقط بعد از تأیید مالک انجام شود. اگر به checks-pass نیاز دارید، CI بسازید و trigger را تغییر دهید؛ این نسخه آن را فرض نمی‌کند.

Rollback کد معادل rollback دیتابیس نیست. قبل از تغییر schema بکاپ بگیرید؛ اگر migration ناسازگار است برنامهٔ برگشت داده نیز لازم است. [راهنمای Django در Render](https://render.com/docs/deploy-django)، [مرجع Blueprint](https://render.com/docs/blueprint-spec)
