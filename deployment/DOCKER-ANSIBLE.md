# استقرار دیوان‌نامه با Docker و Ansible

شاخهٔ `deploy-demo` از Django/Gunicorn، PostgreSQL 17 و Caddy استفاده می‌کند. مایگریشن پیش از شروع وب اجرا می‌شود و WhiteNoise فایل‌های استاتیک تولیدشده در build را ارائه می‌کند. فقط Caddy پورت میزبان دارد. PostgreSQL روی شبکهٔ خصوصی Docker با TLS و حساب اختصاصی برنامه اجرا می‌شود. اتصال داخلی با `sslmode=require` رمزگذاری می‌شود و گواهی داخلی PostgreSQL در هر شروع کانتینر ساخته می‌شود. دادهٔ PostgreSQL و گواهی‌های Caddy در volumeهای نام‌دار نگهداری می‌شوند.

## اجرای محلی

از ریشهٔ مخزن با Docker Engine، افزونهٔ Compose v2 و OpenSSL:

```bash
umask 077
cp deployment/docker/.env.example .env.docker
```

دو مقدار خالی `DIVAN_SECRET_KEY` و `DIVAN_DB_PASSWORD` را به‌ترتیب با خروجی `openssl rand -hex 48` و `openssl rand -hex 32` پر کنید. سپس:

```bash
docker compose --env-file .env.docker up -d --build --wait
curl -kfsS https://localhost:8443/healthz/
docker compose --env-file .env.docker exec web python manage.py createsuperuser
```

مستقیماً به `https://localhost:8443/login/` بروید. Caddy برای localhost از CA محلی خودش استفاده می‌کند و مرورگر تا زمان اعتماد به آن هشدار می‌دهد. برای توقف، `docker compose --env-file .env.docker down` اجرا کنید. گزینهٔ `-v` داده‌های volume را حذف می‌کند.

## نصب روی سرور با Ansible

کنترلر به Git و Ansible Core نیاز دارد. مقصد یک Ubuntu Server 24.04 با SSH و کاربر دارای sudo است. رکورد A دامنه را به IP سرور و در صورت استفاده از IPv6 رکورد AAAA را به IP درست وصل کنید. TCP پورت‌های ۸۰ و ۴۴۳ باید آزاد و از اینترنت قابل دسترس باشند. Playbook از Docker و Compose موجود روی سرور استفاده می‌کند. اگر Compose موجود نباشد، بسته‌ها را متناسب با خانوادهٔ Docker نصب‌شده انتخاب می‌کند. برای سرور دارای Docker CE، مخزن APT رسمی Docker باید در دسترس باشد. سرور برای نصب بسته‌ها و build به مخازن Ubuntu، Docker Hub و PyPI نیاز دارد.

```bash
git clone --branch deploy-demo https://github.com/dexterMAHO/DivanNameh.git
cd DivanNameh
cp deployment/ansible/inventory.example.yml deployment/ansible/inventory.yml
# IP، کاربر SSH و دامنه را در inventory.yml وارد کنید.
ansible-playbook -i deployment/ansible/inventory.yml deployment/ansible/deploy.yml
```

اگر sudo رمز می‌خواهد `-K` و اگر کلید SSH پیش‌فرض کافی نیست `--private-key /path/to/key` را به فرمان اضافه کنید. Playbook فقط فایل‌های commit فعلی را از کنترلر به سرور می‌فرستد. کلید Django و رمز PostgreSQL در اولین نصب روی سرور تولید و در `/opt/divannameh/secrets.env` نگهداری می‌شوند. اجرای دوباره همان رمزها و volumeها را استفاده می‌کند. playbook پس از بررسی HTTPS، پیوند `/opt/divannameh/current` را به نسخهٔ تأییدشده تغییر می‌دهد.

## اجرای سریع با SSH کاربر root

از روی دستگاه کنترلر اجرا کنید. سرور باید اتصال SSH کاربر root را روی پورت `9011` بپذیرد.

```bash
./deployment/ansible/deploy-root.sh 203.0.113.10 divan.example.com
# با کلید SSH مشخص
./deployment/ansible/deploy-root.sh 203.0.113.10 divan.example.com --private-key /path/to/key
```

برای ورود با رمز، فایل محلی `.env.ssh-root` را در ریشهٔ پروژه با مجوز `0600` بسازید و مقدار `ansible_password` را در آن به قالب YAML قرار دهید. اگر ترجیح می‌دهید رمز را هنگام اجرا وارد کنید، گزینهٔ `--ask-pass` را به فرمان اضافه کنید و فایل رمز را کنار بگذارید.

اسکریپت یک inventory موقت می‌سازد و پس از پایان آن را پاک می‌کند. اگر `.env.deploy-root` در ریشهٔ پروژه موجود نباشد، رمز PostgreSQL را بدون نمایش می‌پرسد و کلید Django را تولید می‌کند. هر دو در همان فایل با مجوز `0600` ذخیره می‌شوند. فایل در Git و Docker build وارد نمی‌شود. Ansible این فایل را فقط در نصب اول روی سرور کپی می‌کند. پس از نصب می‌توانید کپی محلی را بردارید و فایل را حذف کنید. نصب موجود از اطلاعات ذخیره‌شده در `/opt/divannameh/secrets.env` استفاده می‌کند. تغییر رمز یک دیتابیس موجود نیاز به تغییر رمز نقش PostgreSQL و هماهنگ‌کردن فایل سرور دارد.

## داده و نگهداری

نصب با دیتابیس خالی شروع می‌شود. برای ساخت ادمین، مشاهدهٔ لاگ یا واردکردن دیتاست، روی سرور از دستورهای زیر استفاده کنید:

```bash
sudo -i
cd /opt/divannameh/current
dc() {
    docker compose --project-name divannameh \
        --env-file /opt/divannameh/secrets.env \
        --env-file /opt/divannameh/current/compose.env "$@"
}
dc ps
dc logs --tail=100 web
dc exec web python manage.py createsuperuser

# اختیاری: پس از انتقال فایل منتخب گنجینه به سرور
dc cp /path/to/treasury.jsonl.gz web:/tmp/treasury.jsonl.gz
dc exec web python manage.py import_treasury /tmp/treasury.jsonl.gz

# نمونهٔ بکاپ؛ فایل را در محل دیگری نگهداری و بازیابی را آزمایش کنید.
umask 077
dc exec -T db pg_dump -U postgres -Fc divannameh > divannameh.dump
```

برای به‌روزرسانی، نسخهٔ مورد نظر را روی کنترلر checkout و playbook را دوباره اجرا کنید. پیش از انتشار دارای مایگریشن از DB بکاپ بگیرید. برگشت به commit قبلی تغییرات schema را برنمی‌گرداند. برای نسخهٔ عمومی، زمان‌بندی بکاپ، پایش و محدودسازی ثبت‌نام را جداگانه تنظیم کنید.
