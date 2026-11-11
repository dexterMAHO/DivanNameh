# متغیرهای محیطی

production فایل `.env` را خودکار نمی‌خواند. در Render از Environment استفاده کنید؛ برای مدیریت Neon از فایل محلی خصوصی `.env.neon` و helper مستند استفاده می‌شود.

| نام | نوع / مقدار پیش‌فرض | کاربرد |
|---|---|---|
| DJANGO_ENV | development / production | انتخاب profile در config.settings؛ Render همیشه production را انتخاب می‌کند |
| DJANGO_SETTINGS_MODULE | config.settings | در Render صریحاً config.settings_production |
| SECRET_KEY | رشتهٔ تصادفی، الزامی در production | حداقل ۵۰ نویسه؛ بدون مقدار پیش‌فرض production |
| DEBUG | bool؛ توسعه True، production False | مقدار True در production موجب توقف واضح می‌شود |
| ALLOWED_HOSTS | CSV نام میزبان | بدون scheme، port یا wildcard؛ دامنهٔ Render خودکار اضافه می‌شود |
| CSRF_TRUSTED_ORIGINS | CSV مبدا HTTPS | مثال https://poems.example.com؛ بدون slash انتهایی؛ مبدا Render خودکار |
| DATABASE_URL | URL اتصال PostgreSQL | الزامی در production؛ توسعه در نبود آن SQLite است |
| DATABASE_MIGRATION_URL | URL مستقیم، اختیاری | فقط وقتی DATABASE_URL pooled است؛ helperها برای migration/مدیریت از این استفاده می‌کنند |
| DB_CONN_MAX_AGE | عدد صحیح ≥۰، پیش‌فرض ۰ | اتصال در پایان هر درخواست بسته می‌شود؛ health check اتصال هم فعال است |
| RENDER | true؛ خودکار Render | انتخاب production و تشخیص proxy مورد اعتماد |
| RENDER_EXTERNAL_HOSTNAME | خودکار Render | hostname واقعی سرویس؛ در repo حدس زده نمی‌شود |
| TRUST_PROXY | bool؛ روی Render True | اعتماد به X-Forwarded-Proto فقط پشت reverse proxy قابل اعتماد |
| APP_TIME_ZONE | Asia/Tehran | زمان محلی مرور و تاریخ‌ها |
| PORT | عدد؛ Render تعیین می‌کند | Gunicorn روی 0.0.0.0:PORT؛ پیش‌فرض محلی ۸۰۰۰ |
| WEB_CONCURRENCY | عدد مثبت؛ ۲ | تعداد workerهای sync؛ با پایش حافظه قابل کاهش به ۱ |
| SECURE_HSTS_SECONDS | عدد ≥۰؛ ۰ | پس از تأیید HTTPS ابتدا ۳۶۰۰؛ سپس با تصمیم مالک افزایش دهید |
| SECURE_HSTS_INCLUDE_SUBDOMAINS | bool؛ False | فقط وقتی HTTPS تمام زیردامنه‌ها تأیید شده |
| SECURE_HSTS_PRELOAD | bool؛ False | مستلزم حداقل یک سال و includeSubDomains؛ فعال‌سازی عمدی |
| DJANGO_READ_DOTENV | bool؛ True در توسعه | False برای تست‌های جدا؛ production هرگز .env نمی‌خواند |

نام‌های قدیمی `DJANGO_SECRET_KEY`، `DJANGO_DEBUG` و `DJANGO_ALLOWED_HOSTS` alias هستند. اگر هر دو نام تنظیم شده باشند، نام کوتاه جدول اولویت دارد؛ در Render فقط نام‌های جدول را استفاده کنید.

## ساخت SECRET_KEY

روی دستگاه خودتان:

```bash
python -c 'import secrets; print(secrets.token_urlsafe(64))'
```

خروجی را در Render Environment ذخیره کنید، نه در چت، GitHub، فایل YAML یا اسکرین‌شات. Blueprint برای SECRET_KEY از شما مقدار می‌خواهد؛ عمداً از generateValue استفاده نشده چون کلید خودکار Render ممکن است کمتر از حد طول بررسی Django باشد. کلید بین deployها ثابت بماند تا نشست‌ها ناخواسته باطل نشوند.

## نمونهٔ فایل محلی برای مدیریت Neon

فایل `.env.neon` (در Git نادیده گرفته می‌شود) را با ویرایشگر بسازید:

```dotenv
SECRET_KEY=<your-generated-secret>
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL="postgresql://ROLE:ENCODED_PASSWORD@DIRECT_NEON_HOST/DATABASE?sslmode=require"
```

```bash
chmod 600 .env.neon
python scripts/neon_manage.py --env-file .env.neon check --deploy
```

این URL فقط نمونهٔ ساختاری است؛ Connection String واقعی را از Neon کپی کنید و پارامترهای SSL/channel binding ارائه‌شده را حفظ کنید. helper نه فایل env را چاپ می‌کند و نه از آن به عنوان کد shell استفاده می‌کند. با هر فرمان مدیریت، انتخاب محیط صریح است.

کلید HTTPS و کوکی‌های Secure در production اجباری‌اند. SSL دیتابیس require/verify-ca/verify-full مجاز است؛ disable/allow/prefer رد می‌شود. SSL اتصال دیتابیس از HTTPS اتصال مرورگر مستقل است.

## ورود خواننده و تأیید انسان بودن

خواننده با نام کاربری در مرورگر ثبت‌شده وارد می‌شود. حساب تازه در مرورگری ثبت می‌شود که ثبت‌نام از آن انجام شده است. خواننده‌ای که هنوز نشست فعال دارد می‌تواند مرورگرش را در تنظیمات ثبت کند. مدیر برای حساب فعال خواننده از فهرست کاربران پیوند یک‌بارمصرف صادر می‌کند. بازکردن پیوند در مرورگر تازه پس از تأیید، دسترسی مرورگر قبلی را برای ورودهای بعدی لغو می‌کند. ورود مدیر در `/admin/login/` انجام می‌شود.

برای استفاده از Cloudflare Turnstile در ورود و ثبت‌نام، `TURNSTILE_SITE_KEY` و `TURNSTILE_SECRET_KEY` را در Environment سرویس تنظیم کنید. هنگام نبود کلیدها، فرم یک سؤال جمع نمایش می‌دهد.
