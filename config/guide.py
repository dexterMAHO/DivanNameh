from dataclasses import dataclass

from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods


@dataclass(frozen=True)
class Lesson:
    slug: str
    title: str
    objective: str
    steps: tuple[str, ...]
    action: str
    route: str
    icon: str


LESSONS = (
    Lesson('dashboard', 'از پیشخوان شروع کنید', 'شعرهای تازهٔ دفتر و مرورهای آماده را از یک جا پیدا کنید.', (
        'در پیشخوان تعداد کارت‌های آماده و موعد بعدی مرور را ببینید.',
        'از «تازه‌های دفتر» یکی از شعرهای اخیراً ذخیره‌شده را باز کنید.',
        'برای پیدا کردن شعر تازه، کارت «شعرجویی» را باز کنید.',
    ), 'رفتن به پیشخوان', 'dashboard', 'grid'),
    Lesson('library', 'شعر را به دفتر اضافه کنید', 'یک شعر ثبت کنید و با موضوع و مجموعه دوباره آن را پیدا کنید.', (
        '«افزودن شعر» را بزنید و نام شاعر و متن را وارد کنید. نشانی منبع را هم در صورت دسترسی وارد کنید.',
        'هنگام ثبت، موضوع موجود را انتخاب کنید یا موضوعی تازه بسازید.',
        'شعر ذخیره‌شده را در «کتابخانهٔ اشعار» باز کنید. برای مرتب‌کردن چند شعر، به «مجموعه‌های شخصی» بروید.',
    ), 'افزودن شعر', 'poem-new', 'pen'),
    Lesson('discover', 'با شعرجویی بگردید', 'با انتخاب شاعر و موضوع، شعری متناسب با حال‌وهوای خودتان پیدا کنید.', (
        '«شعرجویی» را از منو یا پیشخوان باز کنید.',
        'شاعر یا موضوعی انتخاب کنید و شعرهای منتخب و مجموعه‌های مضمونی را ببینید.',
        'برای انتخاب شعر تصادفی، «کشف شعر» را از منو باز کنید و منبع و طول شعر را مشخص کنید.',
    ), 'رفتن به شعرجویی', 'explore', 'compass'),
    Lesson('treasury', 'بیتی را از روی یک مصرع پیدا کنید', 'از چند واژه که در خاطر دارید به همان بیت در متن کامل برسید.', (
        'ذره‌بین هدر را بزنید. اگر صفحهٔ آرشیو باز شد، «ردّ مصرع» را انتخاب کنید.',
        'چند واژه مثل «یوسف گم گشته» را جست‌وجو کنید و بیت کاملِ برجسته‌شده را در نتایج ببینید.',
        'روی نتیجه بزنید تا همان بخش از شعر باز شود. نام شاعر و منبع در صفحهٔ اثر آمده‌اند.',
    ), 'امتحان ردّ مصرع', 'treasury-trace', 'search'),
    Lesson('favorites', 'شاه‌بیت‌های خودتان را بسازید', 'بیت‌های محبوبتان را یک‌جا گردآوری کنید.', (
        'شعری از دفتر یا گنجینهٔ عمومی باز کنید.',
        'ستارهٔ کنار بیت را بزنید تا آن بیت به «شاه‌بیت‌ها» اضافه شود.',
        'در «شاه‌بیت‌ها» می‌توانید بیت را دوباره بخوانید، به اشتراک بگذارید یا نشان آن را بردارید.',
    ), 'دیدن شاه‌بیت‌ها', 'favorites', 'star'),
    Lesson('review', 'شعر را برای مرور آماده کنید', 'از یک بیت یا بازه کارت بسازید و مرورهای موعددار را انجام دهید.', (
        'در صفحهٔ شعر، بیت‌ها یا بازهٔ موردنظر را برای حفظ انتخاب کنید.',
        'در «مرور امروز» متن را از حافظه بگویید و پاسخ را آشکار کنید.',
        'به یادآوری خود امتیاز بدهید تا موعد بعدی با توجه به سختی همان کارت تنظیم شود.',
    ), 'شروع مرور امروز', 'review', 'repeat'),
    Lesson('share', 'یک بیت یا تمرین بفرستید', 'پیش از فرستادن لینک، نسخه‌ای را که دوستتان می‌بیند بررسی کنید.', (
        'در صفحهٔ شعر یا شاه‌بیت‌ها گزینهٔ اشتراک را بزنید و بیت‌های موردنظر را انتخاب کنید.',
        'برای یک بیتِ دومصرعی می‌توانید «مصرع دوم را به یاد بیاور» را انتخاب کنید. یادداشت همراه اختیاری است.',
        'پیش‌نمایش را تأیید و لینک را کپی کنید. برای غیرفعال‌کردن لینک به «اشتراک‌های من» بروید.',
    ), 'دیدن اشتراک‌های من', 'my-shares', 'bookmark'),
    Lesson('appearance', 'ظاهر و خواندن را تنظیم کنید', 'چیدمان و ظاهر متن را با شیوهٔ خواندن خودتان هماهنگ کنید.', (
        'از نشان خورشید یا ماه هدر، حالت روشن، تاریک یا مطابق دستگاه را انتخاب کنید.',
        'در تنظیمات حساب، پالت رنگی و اندازه و فاصلهٔ سطرها را تغییر دهید.',
        'پیش‌نمایش را ببینید و تنظیمات را ذخیره کنید.',
    ), 'باز کردن تنظیمات', 'settings', 'sun'),
)
LESSONS_BY_SLUG = {lesson.slug: index for index, lesson in enumerate(LESSONS)}
SESSION_KEY = 'guide_completed_lessons'


def completed_lessons(request):
    return {slug for slug in request.session.get(SESSION_KEY, []) if slug in LESSONS_BY_SLUG}


@require_GET
def index(request):
    completed = completed_lessons(request)
    return render(request, 'guide/index.html', {
        'lessons': LESSONS,
        'completed': completed,
        'total': len(LESSONS),
        'next_lesson': next((lesson for lesson in LESSONS if lesson.slug not in completed), None),
    })


@require_http_methods(['GET', 'POST'])
def lesson_detail(request, slug):
    try:
        index = LESSONS_BY_SLUG[slug]
    except KeyError:
        raise Http404 from None
    lesson = LESSONS[index]
    previous = LESSONS[index - 1] if index > 0 else None
    following = LESSONS[index + 1] if index + 1 < len(LESSONS) else None
    completed = completed_lessons(request)
    if request.method == 'POST':
        completed.add(slug)
        request.session[SESSION_KEY] = sorted(completed)
        return redirect('guide-lesson', slug=following.slug) if following else redirect('guide')
    return render(request, 'guide/lesson.html', {
        'lesson': lesson,
        'number': index + 1,
        'total': len(LESSONS),
        'previous': previous,
        'following': following,
        'done': slug in completed,
    })
