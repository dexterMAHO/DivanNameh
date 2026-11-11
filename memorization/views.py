import uuid
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST, require_GET
from accounts.permissions import action_password_error
from poetry.http import private, success, failure
from .models import MemorizationItem, ReviewLog
from .forms import MemorizationItemForm, ReviewRatingForm
from .services.selections import create_item, get_item_verses, DuplicateItem
from .services.reviews import get_due_items, rate_item, ReviewConflict


@private
@require_GET
def items(request):
    rows = MemorizationItem.objects.filter(owner=request.user).select_related('poem', 'start_verse', 'end_verse').prefetch_related('poem__verses')
    return render(request, 'memorization/list.html', {'page': Paginator(rows, 20).get_page(request.GET.get('page'))})


@private
@require_POST
def add_item(request):
    if error := action_password_error(request):
        return failure(request, error, status=403)
    form = MemorizationItemForm(request.POST, owner=request.user)
    if not form.is_valid():
        return failure(request, 'شعر یا بازهٔ انتخاب‌شده معتبر نیست.', errors=form.errors)
    data = form.cleaned_data
    try:
        item = create_item(request.user, data['poem_id'], data['scope'], data.get('start_verse_id'), data.get('end_verse_id'))
    except (DuplicateItem, IntegrityError):
        return failure(request, 'این کارت قبلاً اضافه شده است.', status=409, code='duplicate_item')
    except ValidationError:
        return failure(request, 'بازهٔ انتخاب‌شده معتبر نیست.', status=400, code='invalid_range')
    target = item.poem.get_absolute_url() if request.POST.get('return_to_poem') == '1' else 'memorize'
    return success(request, 'به فهرست حفظ افزوده شد.', target, item={'id': item.pk, 'scope': item.scope, 'poem_id': item.poem_id, 'due_at': item.due_at.isoformat()}, remaining_due_count=get_due_items(request.user).count())


@private
@require_POST
def item_action(request, pk, action):
    item = get_object_or_404(MemorizationItem, pk=pk, owner=request.user)
    if action == 'delete':
        if request.POST.get('confirm') != 'yes':
            return render(request, 'confirm.html', {'label': 'حذف کارت حفظ', 'explanation': 'تاریخچهٔ مرور این کارت حذف می‌شود. شعر و شاه‌بیت‌ها باقی می‌مانند.'})
        item.delete()
    else:
        # Update only status so a concurrent review cannot be overwritten.
        MemorizationItem.objects.filter(pk=item.pk, owner=request.user).update(status='paused' if action == 'pause' else 'active')
    return success(request, 'فهرست حفظ به‌روز شد.', 'memorize')


@private
@require_GET
def review(request):
    queue = get_due_items(request.user)
    item = queue.first()
    verses = list(get_item_verses(item)) if item else []
    return render(request, 'memorization/review.html', {'item': item, 'verses': verses, 'cue': verses[0] if verses else None,
                  'remaining': queue.count(), 'request_id': uuid.uuid4(), 'ratings': ReviewLog.RATINGS})


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
        return failure(request, str(exc), status=409, code='not_due')
    return success(request, 'مرور ثبت شد.', 'review', item_id=pk, rating=log.rating, next_due_at=log.next_due_at.isoformat(),
                   interval_days=log.next_interval_days, remaining_due_count=get_due_items(request.user).count())
