# استقرار دیوان نامه روی VPS

## آماده‌سازی

یک کاربر سرویس بدون دسترسی مدیریتی ایجاد کنید؛ مثلاً `divannameh`. Python 3.12/3.13، venv، PostgreSQL، Nginx و ابزار صدور گواهی HTTPS را از مخزن سیستم نصب کنید. کد را در `/srv/divannameh` با مالکیت کاربر سرویس قرار دهید. محیط مجازی بسازید و requirements را نصب کنید.

در PostgreSQL یک نقش محدود و یک دیتابیس متعلق به آن ایجاد کنید. فایل `.env` با مجوز `600`:

```dotenv
DJANGO_SECRET_KEY=<random-secret-at-least-50-characters>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=poems.example.com
DATABASE_URL=postgresql://divannameh:<url-encoded-password>@127.0.0.1:5432/divannameh
APP_TIME_ZONE=Asia/Tehran
CSRF_TRUSTED_ORIGINS=https://poems.example.com
TRUST_PROXY=True
SECURE_HSTS_SECONDS=3600
```

`TRUST_PROXY` فقط وقتی درست است که پورت Gunicorn عمومی نباشد و Nginx هدر X-Forwarded-Proto را بازنویسی کند. HSTS شامل زیردامنه‌ها و preload فعال است؛ قبل از ثبت دامنه در فهرست preload باید HTTPS تمام زیردامنه‌ها را بررسی و مقدار را به حد لازم افزایش دهید. مقدار اولیهٔ کوتاه برای آزمون است.

```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py check --deploy
```

## systemd

`/etc/systemd/system/divannameh.service`:

```ini
[Unit]
Description=DivanNameh
After=network.target postgresql.service
[Service]
User=divannameh
Group=divannameh
WorkingDirectory=/srv/divannameh
ExecStart=/srv/divannameh/.venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 2 --access-logfile - --error-logfile -
Restart=on-failure
PrivateTmp=true
NoNewPrivileges=true
UMask=0077
[Install]
WantedBy=multi-user.target
```

سپس `systemctl daemon-reload` و `systemctl enable --now divannameh`.

## Nginx و HTTPS

در بخش http تنظیم Nginx:

```nginx
limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;
```

نمونه server پس از صدور گواهی معتبر:

```nginx
server {
    listen 80;
    server_name poems.example.com;
    return 301 https://$host$request_uri;
}
server {
    listen 443 ssl;
    server_name poems.example.com;
    ssl_certificate /etc/letsencrypt/live/poems.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/poems.example.com/privkey.pem;
    client_max_body_size 4m;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    location = /login/ {
        limit_req zone=login burst=5 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

WhiteNoise فایل‌های collectstatic را ارائه می‌کند. با Certbot و افزونهٔ Nginx گواهی دامنهٔ واقعی را صادر کنید و تمدید خودکار را با `certbot renew --dry-run` بررسی کنید. پیش از reload، `nginx -t` اجرا شود. لاگ‌ها: `journalctl -u divannameh` و لاگ access/error Nginx. صفحهٔ ورود، POST با CSRF، خروج و مسیر static را روی HTTPS بررسی کنید.

## بکاپ و آزمون بازیابی

بکاپ روزانه، رمزگذاری و یک نسخه خارج از سرور. فایل env را جداگانه و محرمانه نگه دارید.

PostgreSQL (اعتبار اتصال در `.pgpass` با مجوز 600، نه آرگومان shell):

```bash
pg_dump -Fc -h 127.0.0.1 -U divannameh divannameh > divannameh.dump
createdb divannameh_restore
pg_restore --no-owner --dbname=divannameh_restore divannameh.dump
```

برای SQLite از snapshot سازگار استفاده کنید:

```bash
python scripts/backup_sqlite.py db.sqlite3 /secure/backups/divannameh.sqlite3
```

روی دیتابیس بازیابی‌شده و یک نمونهٔ محلی جدا، `migrate --check` را اجرا کنید، تعداد شعر/بیت/مرور را مقایسه کنید، ورود و یک چرخهٔ مرور را امتحان کنید. فایل دیتابیس زنده را هنگام نوشتن با cp کپی نکنید. بکاپ را در پوشهٔ static یا Git قرار ندهید.

## به‌روزرسانی

پیش از تغییر، بکاپ و آزمون restore بگیرید. وابستگی‌ها و کد نسخهٔ جدید را نصب، تست و migrations را بررسی کنید؛ سپس migrate، collectstatic و restart سرویس. دیتابیس را پاک نکنید. اگر migration برگشت‌ناپذیر است، برگشت نسخه باید همراه بازیابی بکاپ هماهنگ باشد.

استقرار روی VPS واقعی و تست PostgreSQL نیاز به محیط سرور دارد؛ اجرای محلی SQLite جای آن را نمی‌گیرد.
