import uuid
from collections import defaultdict
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib import messages
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST, require_GET
from accounts.permissions import action_password_error
from poetry.http import private, success, failure, wants_json
from poetry.models import Poem
from .models import MemorizationItem, ReviewLog
from .forms import MemorizationItemForm, ReviewRatingForm
from .services.selections import create_item, get_item_verses, DuplicateItem
from .services.reviews import get_due_items, rate_item, ReviewConflict


PRACTICE_MODES = {
    'cue': 'مصرع راهنما', 'blanks': 'جای خالی', 'progressive': 'نمایش تدریجی',
}


def study_context(owner):
    cards = MemorizationItem.objects.filter(owner=owner)
    return {
        'has_cards': cards.exists(),
        'next_study': cards.filter(status='active', poem__archived_at__isnull=True,
                                   due_at__gt=timezone.now()).values_list('due_at', flat=True).first(),
        'reviewed_today': ReviewLog.objects.filter(item__owner=owner, reviewed_at__date=timezone.localdate()).exists(),
    }


@private
@require_GET
def items(request):
    rows = MemorizationItem.objects.filter(owner=request.user).select_related('poem', 'start_verse', 'end_verse').prefetch_related('poem__verses')
    state = request.GET.get('state', '')
    now = timezone.now()
    filters = {
        'due': Q(status='active', poem__archived_at__isnull=True, due_at__lte=now),
        'upcoming': Q(status='active', poem__archived_at__isnull=True, due_at__gt=now),
        'paused': Q(status='paused', poem__archived_at__isnull=True),
        'archived': Q(poem__archived_at__isnull=False),
    }
    if state in filters:
        rows = rows.filter(filters[state])
    return render(request, 'memorization/list.html', {
        'page': Paginator(rows, 20).get_page(request.GET.get('page')), 'state': state,
    })


@private
@require_GET
def stats(request):
    today = timezone.localdate()
    first_day = today - timedelta(days=6)
    logs = ReviewLog.objects.filter(item__owner=request.user)
    totals = logs.filter(reviewed_at__date__range=(first_day, today)).annotate(day=TruncDate('reviewed_at')).values('day').annotate(
        reviews=Count('pk'), again=Count('pk', filter=Q(rating='again')),
    )
    by_day = {row['day']: row for row in totals}
    next_days = MemorizationItem.objects.filter(owner=request.user, status='active', poem__archived_at__isnull=True,
                                               due_at__gt=timezone.now(), due_at__date__lte=today + timedelta(days=6))
    upcoming = defaultdict(int, next_days.annotate(day=TruncDate('due_at')).values_list('day').annotate(total=Count('pk')))
    difficult = logs.filter(rating='again').values('item_id', 'item__poem_id', 'item__poem__title', 'item__poem__poet_name').annotate(
        times=Count('pk'),
    ).order_by('-times', 'item_id')[:10]
    review_max = max((row['reviews'] for row in by_day.values()), default=1)
    upcoming_max = max(upcoming.values(), default=1)
    return render(request, 'memorization/stats.html', {
        'review_max': review_max, 'upcoming_max': upcoming_max,
        'history': [(first_day + timedelta(days=i), by_day.get(first_day + timedelta(days=i), {})) for i in range(7)],
        'forecast': [(today + timedelta(days=i), upcoming[today + timedelta(days=i)]) for i in range(7)],
        'due_now': get_due_items(request.user).count(), 'difficult': difficult,
    })


@private
@require_POST
def add_item(request):
    def invalid(message, status=400, code='invalid', errors=None):
        poem_id = request.POST.get('poem_id', '')
        if not wants_json(request) and request.POST.get('return_to_poem') == '1' and poem_id.isascii() and poem_id.isdigit() and len(poem_id) <= 18:
            poem = get_object_or_404(Poem, pk=poem_id, owner=request.user)
            messages.error(request, message, extra_tags='study-inline')
            return redirect(poem.get_absolute_url() + '#study')
        return failure(request, message, status=status, code=code, errors=errors)

    if error := action_password_error(request):
        return invalid(error, status=403)
    form = MemorizationItemForm(request.POST, owner=request.user)
    if not form.is_valid():
        return invalid('شعر یا بازهٔ انتخاب‌شده معتبر نیست.', errors=form.errors)
    data = form.cleaned_data
    try:
        item = create_item(request.user, data['poem_id'], data['scope'], data.get('start_verse_id'), data.get('end_verse_id'))
    except (DuplicateItem, IntegrityError):
        return invalid('این کارت قبلاً اضافه شده است.', status=409, code='duplicate_item')
    except ValidationError:
        return invalid('بازهٔ انتخاب‌شده معتبر نیست.', code='invalid_range')
    target = item.poem.get_absolute_url() if request.POST.get('return_to_poem') == '1' else 'memorize'
    return success(request, 'به فهرست حفظ افزوده شد.', target, item={'id': item.pk, 'scope': item.scope, 'label': item.scope_label, 'poem_id': item.poem_id, 'due_at': item.due_at.isoformat()}, remaining_due_count=get_due_items(request.user).count())


@private
@require_POST
def item_action(request, pk, action):
    item = get_object_or_404(MemorizationItem, pk=pk, owner=request.user)
    return_query = request.POST.get('return_query', '')
    target = reverse('memorize')
    if return_query.startswith('?') and len(return_query) < 200 and url_has_allowed_host_and_scheme(target + return_query, allowed_hosts=set()):
        target += return_query
    if action == 'delete':
        if request.POST.get('confirm') != 'yes':
            return render(request, 'confirm.html', {'label': 'حذف کارت حفظ', 'explanation': 'تاریخچهٔ مرور این کارت حذف می‌شود. شعر و شاه‌بیت‌ها باقی می‌مانند.', 'cancel_url': target, 'return_query': return_query})
        item.delete()
    else:
        # Update only status so a concurrent review cannot be overwritten.
        MemorizationItem.objects.filter(pk=item.pk, owner=request.user).update(status='paused' if action == 'pause' else 'active')
    return success(request, 'فهرست حفظ به‌روز شد.', target)


@private
@require_GET
def review(request):
    queue = get_due_items(request.user)
    item = queue.first()
    verses = list(get_item_verses(item)) if item else []
    mode = request.GET.get('mode', 'cue')
    if mode not in PRACTICE_MODES:
        mode = 'cue'
    cue = verses[0].hemistich_1 if verses else ''
    words = cue.split()
    blanks = [(word, index % 3 == 1 or len(words) == 1) for index, word in enumerate(words)] if mode == 'blanks' else []
    return render(request, 'memorization/review.html', {
        **study_context(request.user), 'item': item, 'verses': verses, 'cue': cue, 'blanks': blanks,
        'remaining': queue.count(), 'request_id': uuid.uuid4(), 'ratings': ReviewLog.RATINGS,
        'mode': mode, 'modes': PRACTICE_MODES.items(),
    })


@private
@require_POST
def rate(request, pk):
    get_object_or_404(MemorizationItem, pk=pk, owner=request.user)
    form = ReviewRatingForm(request.POST)
    if not form.is_valid():
        return failure(request, 'امتیاز یا شناسهٔ درخواست معتبر نیست.', errors=form.errors)
    try:
        log = rate_item(request.user, pk, **form.cleaned_data)
    except ReviewConflict as exc:
        if wants_json(request):
            return failure(request, str(exc), status=409, code='not_due')
        messages.info(request, str(exc))
        return redirect('review')
    mode = request.POST.get('mode', '')
    target = reverse('review') + (f'?mode={mode}' if mode in PRACTICE_MODES else '')
    return success(request, 'مرور ثبت شد.', target, item_id=pk, rating=log.rating, next_due_at=log.next_due_at.isoformat(),
                   interval_days=log.next_interval_days, remaining_due_count=get_due_items(request.user).count())
