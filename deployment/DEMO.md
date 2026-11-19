# demo.divannameh.com — سایت نمایشی

سایت نمایشی همان کد و همان ایمیجِ سایت اصلی را اجرا می‌کند، روی همان سرور و
پشت همان پراکسی، اما با **دیتابیس جداگانه**. گنجینهٔ شعر — شاعران، آثار، متن و
گزیده‌های تحریریه — از دیتابیس اصلی کپی می‌شود؛ حساب‌ها و دفترهای شخصی کپی
نمی‌شوند.

## چرا دیتابیس جدا

ورود در دیوان‌نامه فقط با نام کاربری انجام می‌شود و رمزی در کار نیست
(`accounts/access.py`):

```python
user = readers().filter(username=username).first()
if user is not None:
    login(request, user)
```

اگر سایت نمایشی به دیتابیس اصلی وصل شود، هر بازدیدکننده‌ای که نام کاربری یک
کاربر واقعی را حدس بزند یا بداند، وارد حساب او می‌شود: دفتر شخصی، شاه‌بیت‌ها،
کارت‌های حفظ، و امکان آرشیو کردن شعرهایش. این یک ریسک نظری نیست؛ همان مسیر
ورودِ عادی است.

جداسازی هزینه‌ای برای محتوا ندارد: گنجینه از دادهٔ کاربران مستقل است. هر کلید
خارجی میان مدل‌های گنجینه به مدل گنجینه‌ای دیگر اشاره می‌کند، و شعرِ ذخیره‌شدهٔ
کاربر با فیلدهای متنی (`treasury_book_slug`، `treasury_entry_key`) به منشأ خود
وصل است، نه با ForeignKey. پس سایت نمایشی می‌تواند دقیقاً همان گنجینه را داشته
باشد و جدول‌های کاربرش خالی بماند.

## ۱. رکورد DNS — پیش از هر چیز

در پنل دامنه یک رکورد بسازید که به همان IP سرور اصلی اشاره کند:

```
demo.divannameh.com.   A   <IP همان سرور>
```

Caddy برای هر نام گواهی جداگانه از Let's Encrypt می‌گیرد؛ تا وقتی این رکورد
منتشر نشده باشد، صدور گواهی شکست می‌خورد. با `dig +short demo.divannameh.com`
انتشار را تأیید کنید.

## ۲. استقرار با یک دستور (مسیر پیشنهادی)

اگر از همان لانچر همیشگی استفاده می‌کنید، فقط `--demo` را اضافه کنید:

```bash
deployment/ansible/deploy-root.sh 194.60.230.102 divannameh.com --demo demo.divannameh.com
```

پلی‌بوک در این حالت خودش:

1. `DIVAN_DEMO_SECRET_KEY` و `DIVAN_DEMO_DB_PASSWORD` را — اگر نباشند — روی
   سرور می‌سازد و به `secrets.env` اضافه می‌کند (مقادیر موجود بازنویسی نمی‌شوند)؛
2. پیکربندی پراکسی دوسایتی را **پیش از** ری‌استارت اعتبارسنجی می‌کند؛
3. `compose.yaml` و `compose.demo.yaml` را با هم بالا می‌آورد؛
4. گنجینه را با `clone_treasury --replace` در دیتابیس نمایشی می‌ریزد؛
5. هر دو سایت را روی HTTPS بررسی می‌کند.

بدون `--demo` هیچ‌کدام از این مرحله‌ها اجرا نمی‌شوند و استقرار دقیقاً مثل قبل است.

اجرای دوباره بی‌خطر است: گنجینه با `--replace` بازسازی می‌شود و دادهٔ کاربرانِ
سایت نمایشی دست‌نخورده می‌ماند. اگر می‌خواهید در یک استقرار، کپی گنجینه انجام
**نشود**، `--extra-vars divan_demo_clone=false` را اضافه کنید.

برای کپی گنجینه بدون اجرای کل پلی‌بوک، از دستور بخش ۶ روی خود سرور استفاده کنید.

مراحل دستی زیر برای وقتی است که می‌خواهید بدون Ansible کار کنید.

## ۳. متغیرهای محیطی (مسیر دستی)

در `secrets.env` سرور (کنار مقادیر فعلی) اضافه کنید:

```bash
openssl rand -base64 48   # برای DIVAN_DEMO_SECRET_KEY
openssl rand -base64 36   # برای DIVAN_DEMO_DB_PASSWORD
```

```
DIVAN_DEMO_SECRET_KEY=<مقدار نخست>
DIVAN_DEMO_DB_PASSWORD=<مقدار دوم>
DIVAN_DEMO_DOMAIN=demo.divannameh.com
DIVAN_DEMO_ORIGIN=https://demo.divannameh.com
DIVAN_DEMO_WORKERS=1
```

کلید و رمزِ نمایشی باید با مقادیر سایت اصلی **متفاوت** باشند؛ وگرنه سایت
نمایشی می‌تواند کوکی معتبرِ سایت اصلی امضا کند.

## ۴. بررسی پیکربندی پراکسی پیش از راه‌اندازی

پراکسی مشترک است. خطای نحوی در `Caddyfile.with-demo` هر دو سایت را می‌خواباند،
پس اول اعتبارسنجی کنید:

```bash
docker compose --project-name divannameh \
  --env-file /opt/divannameh/secrets.env \
  --env-file /opt/divannameh/releases/<revision>/compose.env \
  -f compose.yaml -f compose.demo.yaml \
  run --rm --no-deps --entrypoint "" proxy \
  caddy validate --config /etc/caddy/Caddyfile.with-demo --adapter caddyfile
```

## ۵. بالا آوردن سایت نمایشی

```bash
docker compose --project-name divannameh \
  --env-file /opt/divannameh/secrets.env \
  --env-file /opt/divannameh/releases/<revision>/compose.env \
  -f compose.yaml -f compose.demo.yaml up -d
```

`demo-migrate` جدول‌ها را می‌سازد و `demo-web` بالا می‌آید. سایت اصلی در طول
این کار دست‌نخورده می‌ماند؛ تنها سرویسی که دوباره ساخته می‌شود `proxy` است.

## ۶. اتصال به گنجینهٔ اصلی

گنجینه را از دیتابیس اصلی به دیتابیس نمایشی کپی کنید:

```bash
docker compose --project-name divannameh \
  --env-file /opt/divannameh/secrets.env \
  --env-file /opt/divannameh/releases/<revision>/compose.env \
  -f compose.yaml -f compose.demo.yaml \
  run --rm demo-clone --replace
```

سرویس `demo-clone` تنها کانتینری است که به هر دو شبکهٔ دیتابیس وصل است و با
`profiles` هرگز با `up` بالا نمی‌آید. دستور فقط می‌خواند و
هرگز روی مبدأ نمی‌نویسد. کلیدهای اصلی حفظ می‌شوند، پس پیوندهای ادبی و
گزیده‌ها به همان آثار اشاره می‌کنند و اجرای دوباره نتیجهٔ یکسان می‌دهد.

چه کپی می‌شود: `TreasuryBook`، `TreasuryEntry`، `TreasuryTopic`،
`TreasuryPick` (با موضوع‌هایش)، `TreasurySet`، `TreasurySetVerse`،
`TreasuryVerseLink`.

چه کپی **نمی‌شود**: `User`، `Poem`، `Verse`، `FavoriteVerse`،
`MemorizationItem`، `ReviewLog`، `Collection`، `PoemShare`.

برای به‌روز نگه داشتن، همین دستور را بعد از هر به‌روزرسانی گنجینه اجرا کنید.

## ۷. بررسی

```bash
curl -sI https://demo.divannameh.com/ | head -1
curl -s https://demo.divannameh.com/treasury/ | grep -c 'poet-profile-card'
curl -sI https://divannameh.com/ | head -1     # سایت اصلی باید دست‌نخورده باشد
```

## خاموش کردن سایت نمایشی

```bash
docker compose --project-name divannameh \
  --env-file /opt/divannameh/secrets.env \
  --env-file /opt/divannameh/releases/<revision>/compose.env \
  -f compose.yaml -f compose.demo.yaml \
  stop demo-web demo-migrate demo-db

# و بازگرداندن پراکسی به پیکربندی تک‌سایتی
docker compose --project-name divannameh \
  --env-file /opt/divannameh/secrets.env \
  --env-file /opt/divannameh/releases/<revision>/compose.env \
  -f compose.yaml up -d --force-recreate proxy
```

حذف کامل دادهٔ نمایشی: `docker volume rm divannameh_demo_postgres_data`.

## اگر سایت نمایشی باید واقعاً روی دیتابیس اصلی باشد

این کار با توضیح بالا توصیه نمی‌شود. اگر با آگاهی از ریسک لازم است، پیش از آن
ورود بدون رمز را ببندید — برای نمونه با فعال‌کردن
`READER_HUMAN_CHECK_ENABLED` و افزودن یک گام احراز هویت واقعی، یا با
محدودکردن سایت نمایشی به حالت فقط‌خواندنی. تا وقتی ورود فقط با نام کاربری
انجام می‌شود، اشتراک دیتابیس یعنی اشتراک دسترسی به همهٔ حساب‌ها.
