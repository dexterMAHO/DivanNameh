# گزارش آماده‌سازی استقرار — ۲۰۲۶-۱۱-۱۱

## ۱. خلاصهٔ تغییرات

آماده‌سازی Render + Neon، تفکیک development/production، validation محیط، PostgreSQL/SSL اجباری در production، WhiteNoise، Gunicorn، build و مستندات انجام شد. رابط کاربری تکمیل‌شده توسط مالک تغییر نکرد. استقرار واقعی آنلاین انجام نشده؛ مالک هنوز حساب‌ها/سرویس‌های مقصد را نساخته و درخواست راهنمای ساخت داده است.

## ۲. فایل‌های ایجادشده

- `.python-version`, `build.sh`, `render.yaml`, `gunicorn.conf.py`
- `config/settings_base.py`, `config/settings_development.py`, `config/settings_production.py`, `config/environment.py`, `config/health.py`
- `config/tests/test_deployment.py` و فایل‌های init لازم
- `accounts/management/commands/import_library.py` و فایل‌های init لازم
- `accounts/tests/test_import_library.py`
- `scripts/migrate_production.py`, `scripts/neon_manage.py`
- `deployment/README.md`, `ENVIRONMENT.md`, `DATABASE.md`, `RENDER.md`, `TROUBLESHOOTING.md`, `VALIDATION.md`

## ۳. فایل‌های اصلاح‌شده

`config/settings.py` به انتخاب‌گر profile تبدیل شد؛ `/healthz/` به `config/urls.py` اضافه شد؛ `.env.example`, `.gitignore`, `README.md` و ارجاع راهنمای قدیمی `docs/deployment.md` به‌روز شدند. فایل `.env` واقعی، دیتابیس، migrationها و فایل‌های UI اصلاح نشدند. requirements موجود کافی بود و تغییر نکرد.

## ۴. تصمیم‌های فنی

- ساختار config و WSGI موجود حفظ شد؛ مسیر واقعی `config.wsgi:application` است.
- Python واقعی 3.13.5 و Django واقعی 5.2.19؛ Gunicorn 23.0.0، WhiteNoise 6.9.0، dj-database-url 3.0.1 و Psycopg 3.2.9 در محیط بررسی شدند.
- توسعه `.env` و نام‌های قدیمی محیط را پشتیبانی می‌کند. production فقط محیط صریح را می‌خواند؛ کلید ضعیف/مفقود، DEBUG=True، SQLite، نبود URL یا SSL ضعیف خطای روشن می‌دهد.
- دامنهٔ Render از RENDER_EXTERNAL_HOSTNAME خوانده می‌شود؛ domain فرضی و wildcard در تنظیمات گذاشته نشده است.
- اتصال مستقیم Neon برای MVP؛ migration URL جدا در صورت pooling؛ conn_max_age=0 و health checks برای اتصال‌های idle.
- Gunicorn دو worker sync، پورت از PORT، stderr/stdout برای لاگ؛ query string و body در access log ثبت نمی‌شوند.
- healthz فقط liveness است تا probe مکرر دیتابیس را بی‌دلیل فعال نگه ندارد؛ دسترسی DB در پذیرش آنلاین جدا بررسی می‌شود.
- HSTS ابتدا صفر تا HTTPS و دامنه تأیید شوند؛ سپس ۳۶۰۰ پیشنهاد می‌شود. includeSubDomains/preload پیش‌فرض خاموش‌اند.
- Blueprint تنها Web Service Free دارد. Secretها sync:false هستند و وارد repo نشده‌اند.
- import_library فقط مدل‌های مشخص و مقصد خالی را قبول می‌کند؛ نیاز به --confirm-empty-target، تراکنش و حفظ روابط دارد. این فرمان روی دیتابیس واقعی اجرا نشد.

## ۵. تست‌های موفق

- تست‌های موجود برنامه و تست‌های جدید تنظیمات/واردسازی: ۳۳ تست.
- `python manage.py check`: بدون issue.
- `python manage.py makemigrations --check --dry-run`: بدون تغییر؛ migration موجودی بازنویسی نشد.
- `python -m pip check`: بدون dependency ناسازگار.
- collectstatic با **تنظیمات production**: موفق؛ manifest و نسخه‌های فشرده تولید شدند.
- `gunicorn ... --check-config`: موفق.
- اجرای واقعی Gunicorn روی loopback با متغیرهای آزمایشی و URL ساختگی DB: healthz و login پاسخ ۲۰۰؛ CSRF cookie امن؛ فایل‌های هش‌دار CSS/JS/font از WhiteNoise پاسخ ۲۰۰؛ HTTP به HTTPS ۳۰۱؛ X-Forwarded-Proto=https بدون حلقهٔ redirect.
- تست تنظیمات production در subprocess جدا، URLهای ساختگی، بدون تماس با Neon یا تغییر دیتابیس واقعی.
- تست import با دادهٔ ساختگی: برگشت user/password hash، گروه/permission، شعر/بیت، تگ M2M، شاه‌بیت، مرز کارت و ReviewLog؛ رد replay و مقصد غیرخالی؛ rollback روی FK نامعتبر.
- `bash -n build.sh`: موفق؛ executable bit تنظیم شد.
- `render.yaml` با JSON Schema رسمی Render اعتبارسنجی شد.
- `git diff --check`: موفق؛ در تاریخچهٔ بررسی‌شده فایل .env یا SQLite ثبت‌شده یافت نشد؛ مقادیر محرمانهٔ فعلی محیط هم تطابقی نداشتند. این بررسی محدود به نام‌ها و مقادیر شناخته‌شده است.

## ۶. تست‌های ناموفق / هشدار

تست خودکار شکست‌خوردهٔ حل‌نشده وجود ندارد. `check --deploy` با HSTS=0 یک هشدار `security.W004` می‌دهد؛ این یک تصمیم مرحلهٔ راه‌اندازی است، نه خطای اتصال یا تنظیمات ضروری. پس از تأیید HTTPS مقدار HSTS تنظیم شود. خطای نبود Secret/DB یا DEBUG ناامن در تست‌های منفی، رفتار مورد انتظار و موفق است.

## ۷. اجرا‌نشده به دلیل نبود دسترسی/محیط

ساخت Neon/Render، اتصال واقعی PostgreSQL، migration روی Neon، build کامل Render، ایجاد حساب آنلاین، واردسازی واقعی، TLS روی دامنهٔ واقعی و انتشار production انجام نشده‌اند. تست SQL واقعی PostgreSQL محلی نیز انجام نشده است؛ نتایج ORM/fixture از SQLite تست است. URL ساختگی در smoke test به دیتابیس متصل نمی‌شود.

## ۸. اقدام‌های دستی مالک

مرور و تأیید تغییرات، commit/push، ساخت حساب Neon و Render، انتخاب Region هماهنگ، تهیهٔ URL/Secret، انتخاب شروع خالی یا انتقال، تأیید واردسازی در صورت نیاز و کنترل HTTPS. حساب یا سرویس خارجی در این کار ایجاد/تغییر داده نشده است.

## ۹. دستورهای دقیق

در محیط Render که Secrets تنظیم شده‌اند:

```bash
./build.sh
python -m gunicorn config.wsgi:application --config gunicorn.conf.py
```

مدیریت محلی Neon پس از ساخت فایل خصوصی:

```bash
python scripts/neon_manage.py --env-file .env.neon check --deploy
python scripts/neon_manage.py --env-file .env.neon migrate --noinput
python scripts/neon_manage.py --env-file .env.neon createsuperuser
```

اگر کتابخانه با حساب مدیر منتقل می‌شود، createsuperuser را اجرا نکنید. دستور import و بکاپ در DATABASE.md آمده است.

## ۱۰. ریسک‌های باقی‌مانده

Free خواب/cold start و محدودیت منابع دارد؛ فایل local دائمی نیست؛ باید از اطلاعات Neon بکاپ مستقل گرفت. تغییر schema در build ممکن است پیش از فعال‌شدن کد جدید اعمال شود؛ migrationهای آینده باید با نسخهٔ قبلی سازگار باشند. healthz سلامت اتصال DB را تضمین نمی‌کند. برای سرویس عمومی گسترده‌تر، محدودسازی تلاش ورود و پایش خطا جداگانه لازم است.

## ثبت فازها

| فاز | نتیجه |
|---|---|
| 1 — بررسی | ساختار، versions، apps/middleware، SQLite دارای داده، نبود upload و Git main/origin واقعی بررسی شد |
| 2 — dependencies | همهٔ وابستگی‌های موردنیاز موجود و pip check سالم |
| 3 — settings | profileها، fail-closed production، SSL، proxy، hosts و CSRF پیاده و تست شدند |
| 4 — deployment files | build، executable bit، Gunicorn، Python pin، Blueprint و health آماده |
| 5 — GitHub | remote/branch/status/history بررسی؛ commit/push انجام نشد |
| 6 — Neon | راهنمای ساخت، role، region، URL مستقیم و SSL آماده؛ ساخت دستی باقی است |
| 7 — Render | Blueprint و راهنمای دستی build/start/env/auto-deploy آماده |
| 8 — انتقال | بکاپ/fixture و واردسازی محافظت‌شده با تست دادهٔ ساختگی؛ دادهٔ واقعی دست‌نخورده |
| 9 — validation | check/test/static/Gunicorn/proxy/schema موفق؛ warning HSTS ثبت شد |
| 10 — docs | فایل‌های کامل deployment و ارجاع README آماده |
