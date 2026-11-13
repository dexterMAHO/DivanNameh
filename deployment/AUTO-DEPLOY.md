# استقرار خودکار شاخهٔ deploy

Ansible یک بار با SSH روی سرور Ubuntu 24.04 اجرا می‌شود و Git، Ansible، سرویس و تایمر systemd را نصب می‌کند. از آن پس خود سرور هر دو دقیقه شاخهٔ `deploy` را می‌خواند و فقط وقتی کامیت شاخه با نسخهٔ تأییدشده فرق دارد، playbook استقرار را محلی اجرا می‌کند. Playbook Docker و Compose را در صورت نیاز نصب می‌کند، تصویر Django را می‌سازد، مایگریشن و کانتینرها را اجرا می‌کند و HTTPS را مستقیم روی سرور و از طریق دامنه بررسی می‌کند. پروژهٔ Compose و volumeهای دیتابیس و Caddy میان نسخه‌ها مشترک‌اند.

## نصب روی سرور

از شاخهٔ `deploy` روی دستگاه کنترلر اجرا کنید. پیش از نصب، دامنه را به سرور وصل کنید و دسترسی ورودی TCP روی ۸۰ و ۴۴۳ و دسترسی خروجی به مخازن Git، Ubuntu، Docker Hub و PyPI را بررسی کنید. اگر GitHub از سرور در دسترس نیست، یک mirror قابل‌دسترسی با همین شاخه آماده کنید و `divan_repository` را در inventory به نشانی mirror تغییر دهید.

```bash
cp deployment/ansible/auto-inventory.example.yml deployment/ansible/inventory.yml
# IP، پورت و کاربر SSH و دامنه را در inventory.yml تنظیم کنید.
ansible-playbook -i deployment/ansible/inventory.yml deployment/ansible/bootstrap-auto-deploy.yml
```

برای کاربر sudo با رمز گزینهٔ `-K` را اضافه کنید. اگر Nginx موجود پورت ۸۰ را گرفته و ۴۴۳ آزاد است، در inventory مقدار `divan_use_existing_nginx: true` را بگذارید. برای مخزن خصوصی، قبل از نصب یک کلید فقط‌خواندنی Git و کلید میزبان تأییدشده را برای کاربر root سرور تنظیم کنید و مقدار `divan_repository` را به نشانی SSH بدهید. دسترسی نوشتن روی شاخهٔ `deploy` معادل اختیار انتشار کد روی سرور است و باید محدود به افراد مجاز باشد.

## انتشار و بررسی

```bash
git push origin HEAD:deploy
```

روی سرور:

```bash
sudo systemctl list-timers divannameh-auto-deploy.timer
sudo journalctl -u divannameh-auto-deploy.service -n 80 --no-pager
sudo readlink /opt/divannameh/current
```

برای اجرای فوری از `sudo systemctl start divannameh-auto-deploy.service` استفاده کنید. قفل، اجرای هم‌زمان را مهار می‌کند. اگر fetch، build، مایگریشن یا بررسی HTTP خطا بدهد، تایمر در نوبت بعد دوباره تلاش می‌کند و پیوند `current` فقط پس از موفقیت جابه‌جا می‌شود. Compose درجا کانتینرها را عوض می‌کند، بنابراین شکست بعد از این مرحله ممکن است به بازیابی سرویس نیاز داشته باشد. برای برگشت کد، کامیت را روی شاخه با `git revert` برگردانید و push کنید. بازگشت کد schema را برنمی‌گرداند. فضای دیسک و بکاپ دیتابیس را متناسب با دفعات انتشار مدیریت کنید.
