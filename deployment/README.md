# استقرار دیوان نامه روی Render + Neon

پروژه برای **Django + Gunicorn روی Render** و **PostgreSQL روی Neon** آماده شده است. VPS لازم نیست. هیچ حساب یا سرویس آنلاین توسط این تغییرات ساخته نشده و Commit/Push انجام نشده است.

## مسیر پیشنهادی

1. تغییرات محلی را مرور کنید؛ تست‌ها و `git diff --check` را اجرا کنید.
2. پس از تأیید خودتان، فایل‌های استقرار را در شاخهٔ `main` مخزن `https://github.com/dexterMAHO/DivanNameh` commit/push کنید. فایل‌های `.env*`، SQLite، backups و exports را اضافه نکنید.
3. [Neon و انتقال داده](DATABASE.md) را انجام دهید. دیتابیس SQLite فعلی خالی نیست؛ انتقال به مقصد تازه اختیاری است اما حذف آن مجاز نیست.
4. مطابق [Render](RENDER.md) یک Web Service بسازید. روش Blueprint از `render.yaml` یا تنظیم دستی هر دو مستند شده‌اند.
5. Secrets را فقط در Environment سرویس وارد کنید. جدول کامل در [ENVIRONMENT.md](ENVIRONMENT.md).
6. پس از اولین build موفق، `/healthz/`، `/login/`، ورود، صفحهٔ کتابخانه و CSS/فونت را روی HTTPS بررسی کنید.
7. اگر داده وارد نکرده‌اید، حساب اولیه را با دستور محلی `scripts/neon_manage.py ... createsuperuser` بسازید. روی طرح Free به Render Shell متکی نباشید.
8. HSTS را بعد از تأیید HTTPS فعال کنید. برای هر تغییر بعدی ابتدا تست و بکاپ؛ سپس push به main باعث auto deploy می‌شود.

## دستورهای محلی

```bash
source .venv/bin/activate
python manage.py check
python manage.py test
python manage.py makemigrations --check --dry-run
```

اجرای توسعه بدون DATABASE_URL همچنان SQLite است. فایل `.env` موجود خودتان را بازنویسی نکنید؛ نام‌های قدیمی `DJANGO_SECRET_KEY`، `DJANGO_DEBUG` و `DJANGO_ALLOWED_HOSTS` هنوز پشتیبانی می‌شوند. متغیرهای جدید `SECRET_KEY`، `DEBUG` و `ALLOWED_HOSTS` اولویت دارند.

دستورهای Render، در محیط سرویس دارای Secrets:

```bash
./build.sh
python -m gunicorn config.wsgi:application --config gunicorn.conf.py
```

`build.sh` وابستگی‌ها را نصب، check و collectstatic را اجرا و سپس با اتصال مستقیم migrationها را اعمال می‌کند. migrate داده را پاک نمی‌کند؛ با این حال هر migration آینده باید قبل از انتشار از نظر تغییر/حذف داده بررسی شود. migration در build روی طرح رایگان اجرا می‌شود؛ از migrationهای ناسازگار با نسخهٔ فعلی در حال اجرا پرهیز کنید و ساختار expand/contract را رعایت کنید.

## وضعیت و محدودیت‌ها

گزارش دقیق بررسی، مرحله‌ها، تست‌ها و موارد اجرا‌نشده در [VALIDATION.md](VALIDATION.md) آمده است. انتشار واقعی نیازمند ساخت حساب‌ها، معرفی Secrets و تأیید انتشار توسط شماست.

در بررسی ۲۰۲۶-۱۱-۱۱ طرح Free سرویس وب Render موجود است، اما خود Render آن را برای production با نیاز دسترس‌پذیری پایدار توصیه نمی‌کند. این مسیر برای شروع شخصی کم‌هزینه مناسب است؛ تضمین uptime ندارد. سرویس رایگان بعد از بی‌کاری می‌خوابد و اولین درخواست کندتر است؛ دیسک آن پایدار نیست و Shell ندارد. [محدودیت‌های رسمی Render](https://render.com/docs/free)

Neon در زمان بررسی طرح Free دارد؛ سهمیهٔ فضای ذخیره‌سازی و compute را پیش از ساخت در داشبورد کنترل کنید. اعداد و شرایط ممکن است تغییر کنند. [قیمت‌گذاری رسمی Neon](https://neon.com/pricing)

## فایل‌های کاربران

این پروژه فعلاً FileField/ImageField یا قابلیت آپلود ندارد. `STATIC_ROOT=staticfiles/` فقط خروجی قابل بازتولید build است. `MEDIA_ROOT=media/` جداست ولی روی Render Free ذخیره‌سازی دائمی نیست. اگر در آینده آپلود اضافه شد، پیش از فعال‌کردن از object storage سازگار با S3 مثل Cloudflare R2 یا Amazon S3 و backend مناسب Django استفاده کنید؛ WhiteNoise برای فایل خصوصی کاربر نیست.
