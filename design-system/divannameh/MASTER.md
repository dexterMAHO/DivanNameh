# دیوان نامه — سیستم طراحی «دفتر ادبی معاصر»

این سند مرجع فرانت‌اند است. توکن‌های اجرایی در `static/css/tokens.css` و نمونهٔ زنده در `/design-system/` قرار دارند. صفحه‌های تخصصی در `pages/` قواعد تکمیلی دارند.

## منشأ و تطبیق مهارت

UI UX Pro Max، مخزن `nextlevelbuilder/ui-ux-pro-max-skill`، commit `6ae86f61f520d6ca229d2f40e070410638c908c5`، نسخهٔ 2.15.0، نصب در `.claude/skills/ui-ux-pro-max` (پروژه، برای Claude Code).

جست‌وجوهای اجراشده:
- `personal poetry library editorial warm --design-system`: پیشنهاد عمومی و کم‌تناسب؛ ذخیره نشد.
- `reading app library --design-system`: دستهٔ کتاب/مطالعه، کاغذ گرم، شبکهٔ Swiss و فضای دانشگاهی مرتبط بودند. الگوی landing/testimonials مناسب برنامهٔ خصوصی نیست و کنار گذاشته شد.
- `reading library --domain product --rtl`: Book & Reading Tracker (partial RTL) و Bookmark & Read-Later (full RTL). قواعد کتابخانه و خواندن پذیرفته شدند؛ جهت آیکون و چیدمان بیت جدا بررسی می‌شود.
- `editorial minimal reading --domain style --rtl`: Minimalism & Swiss Style، full RTL؛ سلسله‌مراتب، شبکه، تزئین کم و یک رنگ تأکیدی پذیرفته شدند.
- `error summary validation --domain ux`: خلاصهٔ خطای قابل فوکوس با لینک به فیلد، در کنار خطای درون فرم.
- `orphan heading line balance --domain ux`: text-wrap:balance با fallback طبیعی، بدون شکست خط اجباری در تیتر.

پشتهٔ موجود Django Templates + CSS + Vanilla JS است. مهارت برای Django/CSS خالص stack اختصاصی ندارد؛ راهنمای عمومی HTML، دسترسی‌پذیری و RTL استفاده شد. پیشنهاد فونت‌های لاتین به Noto Naskh Arabic و Vazirmatn محلی تبدیل شد. هیچ فریم‌ورک فرانت‌اند اضافه نمی‌شود.

## شخصیت و اصول

آرام، ادبی، شخصی و دقیق. حس دفتر کاهی با شبکهٔ منظم و فضای سفید. متن شعر مهم‌ترین محتوای صفحه است. آمار تنها از دادهٔ واقعی می‌آید. هر صفحه یک اقدام اصلی دارد؛ CTAهای ثانویه خنثی‌اند. صفحهٔ ورود و مرور خلوت‌تر از کتابخانه‌اند.

## رنگ‌ها و نقش معنایی

| نقش | مقدار | کاربرد |
|---|---|---|
| background | #F4F1E9 | زمینهٔ کاغذی |
| surface | #FFFCF5 | کارت و صفحهٔ شعر |
| surface-muted | #EAE5D9 | دسته‌بندی و وضعیت خنثی |
| foreground | #302D27 | متن اصلی / جوهر |
| muted-foreground | #6E685D | متن توضیحی |
| primary | #824338 | اقدام اصلی و نشان انتخاب |
| primary-hover | #69342C | hover اقدام اصلی |
| on-primary | #FFFCF5 | متن روی زرشکی |
| feature | #343C34 | صفحهٔ مرورِ سبز تیره |
| on-feature | #FFFCF5 | متن روی بخش ویژه |
| feature-muted | #D5DDCF | توضیح روی بخش ویژه |
| border | #D8D0C1 | خطوط تزئینی |
| control-border | #8E8577 | مرز ورودی و کنترل، ≥3:1 |
| focus | #28647B | حلقهٔ فوکوس |
| success / success-surface | #365D42 / #E9F0E7 | تأیید همراه متن |
| danger / danger-surface | #9A342E / #F9EAE5 | خطا همراه متن |

مقادیر hex تنها در فایل tokens؛ هیچ رنگ بی‌نام در کامپوننت‌ها. کنتراست متن عادی ≥4.5:1 و کنترل/آیکون معنایی ≥3:1. خط جداکنندهٔ تزئینی الزام مرز کنترل ندارد.

## تایپوگرافی

- متن و کنترل: Vazirmatn، fallback Tahoma/sans-serif، اندازهٔ پایه 16px و line-height 1.8.
- تیتر/شعر/لوگو: Noto Naskh Arabic، fallback Tahoma/serif. فونت محلی، font-display:swap.
- متادیتا 12px، برچسب 14px، بدنه 16px، متن شعر clamp(20px, 2vw, 26px)، تیتر صفحه clamp(30px, 3.4vw, 46px).
- متن شعر line-height 2.2؛ از justify و letter-spacing برای حروف فارسی استفاده نشود.
- عنوان‌ها balanced، متن کاربر wrap، حداقل عرض فرزندان grid/flex صفر. نیم‌فاصله و محتوا بدون دستکاری.

## هندسه و فاصله

- مقیاس: 4 / 8 / 12 / 16 / 24 / 32 / 40 / 48 / 64 پیکسل.
- شعاع: 4px کنترل، 8px کارت، 999px نشان گرد. سایه فقط سطح بلندشده، بسیار ملایم.
- شبکه دسکتاپ: ناوبری راست 232px؛ محتوای اصلی حداکثر 1160px با gutter سیال 20–48px.
- زیر 1024px: ناوبری به سربرگ و منوی بازشونده تبدیل می‌شود؛ زیر 768px تک‌ستونه، شعر دو مصرع زیر هم.
- کارت‌های کتابخانه: ۳ ستون بزرگ، ۲ ستون متوسط، ۱ ستون موبایل.
- ابیات: مصرع نخست راست، مصرع دوم چپ؛ سطر تنها تمام عرض. شماره و نشان بیرون متن.

## کامپوننت‌ها

- Button: حداقل 44px ارتفاع، icon 20px، gap 8px؛ primary / secondary / quiet / destructive. hover، active، focus-visible و disabled مستقل. بارگذاری با متن و aria-busy.
- Navigation: آیکون خطی 1.7px، نام قابل خواندن، aria-current در سرور، انتخاب با رنگ+مرز+وزن. منوی موبایل aria-expanded و Escape.
- Card: سطح روشن، مرز ظریف، header/body/footer با spacing یکسان؛ کلیک با لینک واقعی.
- Chip: تگ لینک‌دار، wrap بدون حذف نام؛ badge وضعیت همراه متن.
- Form: label ثابت، راهنمای نزدیک، خطای inline و خلاصهٔ قابل فوکوس. فیلدها min-height 48px، no placeholder-only.
- Verse: متن دست‌نخورده، ستارهٔ SVG با aria-pressed؛ نام کنترل بیانگر عمل اضافه/برداشتن است.
- Review: راهنما → آشکارسازی → چهار انتخاب با توضیح؛ بدون نمودار تسلط ساختگی.
- Empty state: آیکون کتاب، عنوان، علت یا مسیر بعدی و یک CTA مرتبط.
- Notification: اعلان عمومی polite؛ خطا alert، متن مستقل از رنگ. هیچ اطلاعات مهم فقط با hover نمایش داده نشود.
- Icons: sprite SVG داخلی با 24×24 viewBox و stroke ثابت؛ آیکون تزئینی aria-hidden. از emoji و glyph ستاره/منو استفاده نشود.

## حرکت و دسترسی‌پذیری

رنگ/سایهٔ دکمه 140ms، سطح و اعلان 200ms؛ بدون انیمیشن مستمر و بدون جابه‌جایی layout. prefers-reduced-motion همهٔ گذارها را خاموش می‌کند. حلقهٔ 3px با offset 3px؛ محتوای sticky نباید فوکوس را بپوشاند. لینک رفتن به محتوا، labelها و ترتیب DOM با ترتیب دیداری همسو. ویژگی‌های اصلی با HTML و بدون JS کار می‌کنند.

## معیار بررسی

تمام مسیرها؛ حالت خالی و پر؛ خطای فرم؛ hover/focus/disabled؛ 375، 768، 1024، 1440؛ طولانی‌شدن عنوان و تگ؛ فارسی و نیم‌فاصله؛ مرور و انتخاب شاه‌بیت؛ CSS تولید production؛ کنتراست محاسبه‌شده. حالت روشن، تاریک و مطابق دستگاه با هر چهار پالت در مرجع زندهٔ رابط از تنظیمات حساب قابل بررسی‌اند. برای آزمون تعاملی با دادهٔ جدا از دستور مرورگر در README استفاده کنید.
