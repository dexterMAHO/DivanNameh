# Neon PostgreSQL و انتقال اطلاعات

## ایجاد سرویس — توسط مالک حساب

1. وارد [کنسول Neon](https://console.neon.tech/) شوید و حساب را بسازید.
2. Project مستقل برای DivanNameh ایجاد کنید. پلن Free را در صورت مناسب‌بودن سهمیه‌ها انتخاب کنید.
3. Region نزدیک به سرویس Render انتخاب کنید؛ Blueprint این پروژه Frankfurt است، بنابراین نزدیک‌ترین Region اروپایی موجود Neon را بررسی کنید. انتخاب واقعی بر اساس گزینه‌های حساب انجام شود.
4. در پروژه، database و role مخصوص همین برنامه بسازید. نام‌ها آزادند و باید از Connection String واقعی استفاده شوند. دیتابیس این برنامه را با پروژه‌های نامرتبط مشترک نکنید.
5. نقش برنامه باید مالک schema/tables همین دیتابیس باشد تا migrationها را اجرا کند؛ از نقش مدیر سازمان برای برنامه استفاده نکنید. برای حداقل دسترسی، نقش LOGIN بدون SUPERUSER/CREATEDB/CREATEROLE را از SQL Editor با حساب مدیر بسازید و مالکیت دیتابیس/مجوز ساخت schema public را به آن بدهید؛ رمز فقط در ابزار Neon وارد شود. نقش‌های ساخته‌شده از Console ممکن است امتیاز بیشتری داشته باشند؛ grants را بررسی کنید.
6. در Connect، branch و database و role مربوط را انتخاب کنید. Connection pooling را خاموش کنید و URL **مستقیم** را بگیرید. نام میزبان مستقیم `-pooler` ندارد.
7. URL را با SSL در Render به عنوان DATABASE_URL وارد کنید. برای اندازهٔ این MVP اتصال مستقیم ساده‌ترین انتخاب است. در صورت انتخاب pooling برای runtime، DATABASE_MIGRATION_URL را نیز با URL مستقیم تنظیم کنید.
8. تنظیمات پروژه conn_max_age=0، health checks و غیرفعال‌بودن server-side cursors را اعمال می‌کنند. URL و SSL هیچ‌گاه در repo ذخیره نمی‌شوند. [راهنمای رسمی Django و Neon](https://neon.com/docs/guides/django)، [اتصال برنامه](https://neon.com/docs/connect/connect-from-any-app)

## دادهٔ موجود

در بررسی فعلی SQLite خالی نبود و حساب/شعر/شاه‌بیت/مرور داشت. هیچ داده‌ای حذف یا به Neon منتقل نشده است. PK مدل‌ها BigAutoField استاندارد است؛ FKها و M2M تگ‌ها در fixture نگه داشته می‌شوند. Custom User پروژه `accounts.User` است. فایل آپلودی وجود ندارد.

دو مسیر:
- **شروع خالی:** build migrationها را اجرا می‌کند؛ سپس createsuperuser. SQLite محلی دست‌نخورده می‌ماند.
- **انتقال کتابخانه:** پس از ساخت Neon و قبل از ایجاد حساب/استفاده از مقصد، مراحل زیر را فقط با تأیید مالک روی **دیتابیس مقصد تازه و خالی** انجام دهید. import روی مقصد دارای کاربر، گروه یا دادهٔ شعر عمداً رد می‌شود.

## ۱. بکاپ سازگار SQLite

ابتدا نوشتن محلی را متوقف کنید. دستور زیر فایل قبلی را بازنویسی نمی‌کند؛ برای بکاپ‌های بعدی نام جدید انتخاب کنید.

```bash
source .venv/bin/activate
mkdir -p backups exports
chmod 700 backups exports
python scripts/backup_sqlite.py db.sqlite3 backups/pre-neon.sqlite3
```

فایل بکاپ شامل اطلاعات حساب‌هاست؛ به Git اضافه نکنید و یک نسخهٔ رمزگذاری‌شده جداگانه نگه دارید. قبل از انتقال، با یک کپی جدا صحت بازشدن کتابخانه را بررسی کنید.

## ۲. استخراج از بکاپ ثابت

```bash
umask 077
divan_backup="$(realpath backups/pre-neon.sqlite3)"
DATABASE_URL="sqlite:///$divan_backup" DJANGO_SETTINGS_MODULE=config.settings_development \
  python manage.py dumpdata accounts auth.group poetry memorization \
  --natural-foreign --indent 2 --output exports/library.json
```

این دستور sessionها، admin log، ContentType و Permissionهای تولیدشده را صادر نمی‌کند. ارتباط permission گروه/کاربر با natural key ذخیره می‌شود و پس از migrate مقصد قابل حل است. شناسه‌های اصلی داده حفظ می‌شوند. فایل شامل hash رمزها و شعر خصوصی است؛ فقط روی دستگاه خودتان نگه دارید.

## ۳. آماده‌سازی و بررسی مقصد

فایل خصوصی `.env.neon` را مطابق ENVIRONMENT.md بسازید؛ URL مستقیم و production settings استفاده می‌شود.

```bash
python scripts/neon_manage.py --env-file .env.neon check
python scripts/neon_manage.py --env-file .env.neon showmigrations
python scripts/neon_manage.py --env-file .env.neon migrate --noinput
```

در Console مطمئن شوید branch/database درست و مقصد تازه است. هنگام import هیچ نسخهٔ برنامه‌ای نباید در مقصد بنویسد. واردسازی را پیش از راه‌اندازی سرویس وب انجام دهید.

## ۴. واردسازی پس از تأیید صریح مالک

```bash
python scripts/neon_manage.py --env-file .env.neon import_library \
  exports/library.json --confirm-empty-target
```

این فرمان به جای loaddata بدون محافظ، ابتدا مدل‌های مجاز و خالی‌بودن مقصد را بررسی می‌کند و سپس import را اتمیک انجام می‌دهد. روی مقصد غیرخالی توقف می‌کند؛ هیچ merge یا overwrite ندارد. خود loaddata constraintهای FK و sequence شناسه‌ها را تنظیم می‌کند. اگر import شکست بخورد تراکنش برمی‌گردد؛ `flush`، حذف جدول یا تکرار loaddata مستقیم راه‌حل نیست.

## ۵. بررسی بعد از انتقال

شمار حساب/شعر/بیت/تگ/کارت/مرور را با بکاپ مقایسه کنید. با حساب منتقل‌شده وارد شوید؛ شعر، شاه‌بیت، تگ‌ها، موعد کارت و یک مرور تازه را کنترل کنید. SQLite و exports را تا پایان تأیید نگه دارید. اگر قبلاً حساب مدیر منتقل شده نیازی به createsuperuser مجدد نیست.

## بکاپ آنلاین بعد از راه‌اندازی

برای خروجی استاندارد PostgreSQL از pg_dump با اتصال **مستقیم** استفاده کنید؛ اعتبار اتصال در فایل `.pgpass` با مجوز 600 یا محیط امن قرار گیرد، نه آرگومان آشکار یا repo. دستور نمونه با نام‌های جایگزین خودتان:

```bash
pg_dump -h DIRECT_NEON_HOST -U APP_ROLE -d APP_DATABASE -Fc -f backups/neon.dump
```

بازیابی را همیشه اول در database/branch جدا امتحان کنید و هرگز روی دیتابیس live تست نکنید. قابلیت و مدت نگهداری restore در Neon به پلن وابسته است؛ بکاپ مستقل لازم است.
