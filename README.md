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
# مقدار تولیدشده را در DJANGO_SECRET_KEY فایل .env قرار دهید.
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 127.0.0.1:8000
```

نشانی: http://127.0.0.1:8000 — ورود با حساب ساخته‌شده. ثبت‌نام عمومی وجود ندارد.
در محیطی که همراه این پیاده‌سازی آماده شده، `.venv` و `.env` محلی موجودند؛ فایل env را بدون نیاز بازنویسی نکنید.

## استفاده

1. «افزودن شعر»: شاعر، ابیات، عنوان و تگ اختیاری. ورود بیت‌به‌بیت یا چسباندن متن با `|` یا هر دو خط یک بیت.
2. «پیش‌نمایش» ساختار را نشان می‌دهد. در خطا دادهٔ فرم باقی می‌ماند.
3. در جزئیات شعر، ستاره شاه‌بیت را مشخص می‌کند؛ تمام شعر یا بازهٔ پیوسته را برای حفظ انتخاب کنید.
4. «مرور امروز»: از مصرع راهنما ادامه دهید، پاسخ را آشکار کنید، سپس دوباره/سخت/خوب/آسان را انتخاب کنید.
5. توقف، فعال‌سازی یا حذف کارت از فهرست حفظ؛ آرشیو و بازگردانی شعر از جزئیات آن.
6. ویرایش متن بیت‌های مرتبط، موعد حفظ را بازنشانی می‌کند و تاریخچه را نگه می‌دارد.

## بررسی

```bash
python manage.py check
python manage.py test
python manage.py makemigrations --check --dry-run
python manage.py collectstatic --noinput
DJANGO_DEBUG=False python manage.py check --deploy
```

## ساختار

- `accounts`: کاربر سفارشی و احراز هویت Django
- `poetry`: مدل، فرم، خدمات و صفحات شعر، تگ، شاه‌بیت و کشف
- `memorization`: کارت‌ها، زمان‌بندی قطعی، ثبت اتمیک مرور و UUID یکتا
- `templates` و `static`: رابط SSR، فونت‌های محلی و بهبود تدریجی با JS
- `docs/deployment.md`: استقرار HTTPS، بکاپ و بازیابی
- `docs/decisions.md`: تصمیم‌ها و محدودیت‌های روشن
- `docs/manual-test.md`: چک‌لیست مرورگر و گزارش کنترل کیفیت

همهٔ اطلاعات خصوصی و محدود به صاحب حساب‌اند؛ تغییر داده فقط با POST و CSRF. متن شعر HTML خام نیست. برای استقرار از Gunicorn و HTTPS استفاده کنید. تولید محتوا، گنجور، OCR، اعلان و ثبت‌نام عمومی در محدودهٔ این MVP نیستند.
