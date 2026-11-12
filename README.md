# دیوان نامه · DivanNameh

دفتر خصوصی شعر فارسی برای نگهداری شعر، تگ‌گذاری، انتخاب شاه‌بیت و حفظ با مرور فاصله‌دار. رابط فارسی/RTL با ظاهر دفتر کاهی، Django Templates و Vanilla JavaScript.

## راه‌اندازی

Python 3.12 یا 3.13:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -c 'import secrets; print(secrets.token_urlsafe(64))'
# مقدار تولیدشده را در SECRET_KEY فایل .env قرار دهید.
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 127.0.0.1:8000
```

ثبت‌نام با نام کاربری انجام می‌شود. برای ورود دوباره، از مرورگر ثبت‌شده استفاده کنید. ورود مدیر در `/admin/login/` انجام می‌شود.
در محیطی که همراه این پیاده‌سازی آماده شده، `.venv` و `.env` محلی موجودند؛ فایل env را بدون نیاز بازنویسی نکنید.

## استفاده

1. در کتابخانه، عنوان، شاعر یا یک مصرع را جست‌وجو کنید. موضوع‌ها، مجموعه‌ها، آرشیو و ترتیب نمایش از همان صفحه در دسترس‌اند.
2. در «افزودن شعر»، متن را سطری، بیت‌به‌بیت یا یکجا وارد کنید. پیش‌نویس خودکار با انتخاب کاربر در همان مرورگر نگه داشته می‌شود.
3. گنجینه، جست‌وجوی شاعر و جست‌وجوی آثار را دارد. گزیده را به دفتر منتقل کنید یا به انتهای نسخهٔ شخصی همان اثر بیفزایید.
4. از هر شعر می‌توان یک کارت کامل و چند کارت بازه‌ای ساخت. «مرور امروز» سه روش تمرین دارد و «آمار مرور» تاریخچه و موعد کارت‌ها را نمایش می‌دهد.
5. از «درخواست‌های ویرایش»، وضعیت، تفاوت نسخه و علت رد را دنبال کنید. ویرایش ابیات تأییدشده همچنان زمان مرور کارت‌های مرتبط را بازنشانی می‌کند.
6. «ورود و خروج فایل» نسخهٔ JSON دفتر و تاریخچهٔ مرور یا Markdown خواندنی می‌دهد. ورود JSON پیش‌نمایش و تأیید جدا دارد.
7. در تنظیمات، دستگاه‌ها، پیوند انتقال، کد بازیابی یک‌بارمصرف و خوانایی شعر را مدیریت کنید.

## بررسی

```bash
python manage.py check
python manage.py test
python manage.py makemigrations --check --dry-run
python manage.py collectstatic --noinput
# Chrome و Node.js 24، با SQLite و حساب آزمایشی جدا
PYTHON=.venv/bin/python node scripts/check_browser.mjs
# بررسی production طبق deployment/ENVIRONMENT.md انجام می‌شود.
```

## ساختار

- `accounts`: کاربر سفارشی و احراز هویت Django
- `poetry`: مدل، فرم، خدمات و صفحات شعر، تگ، شاه‌بیت و کشف
- `memorization`: کارت‌ها، زمان‌بندی قطعی، ثبت اتمیک مرور و UUID یکتا
- `templates` و `static`: رابط SSR، فونت‌های محلی و بهبود تدریجی با JS
- `deployment/README.md`: استقرار Render + Neon، محیط‌ها، بکاپ و انتقال کنترل‌شدهٔ داده
- `docs/decisions.md`: تصمیم‌ها و محدودیت‌های روشن
- `docs/manual-test.md`: چک‌لیست مرورگر و گزارش کنترل کیفیت

همهٔ اطلاعات خصوصی و محدود به صاحب حساب‌اند؛ تغییر داده فقط با POST و CSRF. متن شعر HTML خام نیست. برای استقرار بدون VPS از راهنمای [Render + Neon](deployment/README.md) استفاده کنید. گنجینه از نمایه و متن مجازِ نسخه‌های واردشدهٔ گنجور استفاده می‌کند. OCR و یادآور خارج از این مرحله‌اند.

## استقرار آنلاین

تنظیمات development و production جدا هستند. روی Render از `./build.sh` و `python -m gunicorn config.wsgi:application --config gunicorn.conf.py` استفاده کنید. Secrets و PostgreSQL اجباری‌اند؛ production فایل `.env` را نمی‌خواند. شروع: [deployment/README.md](deployment/README.md).
