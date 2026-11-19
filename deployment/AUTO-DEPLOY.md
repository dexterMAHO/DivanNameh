# استقرار خودکار شاخهٔ انتخاب‌شده

Ansible یک بار با SSH روی سرور Ubuntu 24.04 یا Debian 12 اجرا می‌شود و Git، Ansible، سرویس و تایمر systemd را نصب می‌کند. از آن پس خود سرور هر دو دقیقه شاخهٔ تعیین‌شده در `divan_branch` را می‌خواند و فقط وقتی کامیت شاخه با نسخهٔ تأییدشده فرق دارد، playbook استقرار را محلی اجرا می‌کند. Playbook Docker و Compose را در صورت نیاز نصب می‌کند، تصویر Django را می‌سازد، مایگریشن و کانتینرها را اجرا می‌کند و HTTPS را مستقیم روی سرور و از طریق دامنه بررسی می‌کند. پروژهٔ Compose و volumeهای دیتابیس و Caddy میان نسخه‌ها مشترک‌اند.

## نصب روی سرور

از شاخهٔ `miniature-frontend` روی دستگاه کنترلر اجرا کنید. در inventory برای دامنهٔ `divannameh.rashn.org` مقدار `divan_branch: miniature-frontend` را قرار دهید. مقدار پیش‌فرض برای سازگاری با نصب‌های قبلی `deploy` است. پیش از نصب، دامنه را به سرور وصل کنید و دسترسی ورودی TCP روی ۸۰ و ۴۴۳ و دسترسی خروجی به مخازن Git، Ubuntu، Docker Hub و PyPI را بررسی کنید. اگر GitHub از سرور در دسترس نیست، یک mirror قابل‌دسترسی با همین شاخه آماده کنید و `divan_repository` را در inventory به نشانی mirror تغییر دهید.

```bash
cp deployment/ansible/auto-inventory.example.yml deployment/ansible/inventory.yml
# IP، پورت و کاربر SSH و دامنه را در inventory.yml تنظیم کنید.
ansible-playbook -i deployment/ansible/inventory.yml deployment/ansible/bootstrap-auto-deploy.yml
```

برای نصب پیش‌نیازها قبل از آماده‌شدن دامنه، گزینهٔ `-e divan_prepare_only=true` را اضافه کنید.

برای کاربر sudo با رمز گزینهٔ `-K` را اضافه کنید. اگر Nginx موجود پورت ۸۰ را گرفته و ۴۴۳ آزاد است، در inventory مقدار `divan_use_existing_nginx: true` را بگذارید. برای مخزن خصوصی، قبل از نصب یک کلید فقط‌خواندنی Git و کلید میزبان تأییدشده را برای کاربر root سرور تنظیم کنید و مقدار `divan_repository` را به نشانی SSH بدهید. دسترسی نوشتن روی شاخهٔ انتخاب‌شده معادل اختیار انتشار کد روی سرور است و باید محدود به افراد مجاز باشد.

## انتشار و بررسی

```bash
git push origin miniature-frontend
```

روی سرور:

```bash
sudo systemctl list-timers divannameh-auto-deploy.timer
sudo journalctl -u divannameh-auto-deploy.service -n 80 --no-pager
sudo readlink /opt/divannameh/current
```

برای اجرای فوری از `sudo systemctl start divannameh-auto-deploy.service` استفاده کنید. قفل، اجرای هم‌زمان را مهار می‌کند. اگر fetch، build، مایگریشن یا بررسی HTTP خطا بدهد، تایمر در نوبت بعد دوباره تلاش می‌کند و پیوند `current` فقط پس از موفقیت جابه‌جا می‌شود. Compose درجا کانتینرها را عوض می‌کند، بنابراین شکست بعد از این مرحله ممکن است به بازیابی سرویس نیاز داشته باشد. برای برگشت کد، کامیت را روی شاخه با `git revert` برگردانید و push کنید. بازگشت کد schema را برنمی‌گرداند. فضای دیسک و بکاپ دیتابیس را متناسب با دفعات انتشار مدیریت کنید.

کامیت محلی تنها پس از push به مخزن قابل انتشار است. اگر چند push بین دو بررسی برسد، آخرین نسخهٔ شاخه منتشر می‌شود. تغییر شاخه با اجرای دوبارهٔ bootstrap و مقدار جدید `divan_branch` اعمال می‌شود.

## سرور فعال دیوان‌نامه

در ۲۰ نوامبر ۲۰۲۶ دیپلوی خودکار برای `divannameh.rashn.org` روی سرور `141.11.107.166` (SSH پورت `9011`) نصب شد:

- شاخهٔ انتشار: `miniature-frontend`
- مسیر نصب: `/opt/divannameh`
- تایمر: `divannameh-auto-deploy.timer`، هر دو دقیقه و پس از راه‌اندازی مجدد سرور
- پراکسی: Nginx موجود با پورت HTTP داخلی `18080` و HTTPS با Caddy
- تنظیم شاخه: `DIVAN_DEPLOY_BRANCH` در سرویس systemd
- تنظیم دامنه و پراکسی: `/opt/divannameh/auto-inventory.json`

برای نصب مجدد با inventory همین سرور:

```bash
ansible-playbook -i deployment/ansible/inventory.yml deployment/ansible/bootstrap-auto-deploy.yml \
  -e divan_branch=miniature-frontend -e divan_use_existing_nginx=true
```

رمزها در مخزن نگهداری نمی‌شوند. پیش از اولین انتشار یک بکاپ PostgreSQL روی سرور در `/opt/divannameh/backups/before-miniature-autodeploy-20261120.dump` ساخته و فهرست آن با `pg_restore --list` بررسی شد.
