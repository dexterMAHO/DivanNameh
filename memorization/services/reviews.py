import time
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError, OperationalError
from django.http import Http404
from django.utils import timezone
from memorization.models import MemorizationItem, ReviewLog
from poetry.models import Poem
from .scheduler import calculate_next_review

class ReviewConflict(Exception):
    pass


def get_due_items(owner, now=None):
    return MemorizationItem.objects.filter(owner=owner, status='active', poem__archived_at__isnull=True,
                                          due_at__lte=now or timezone.now()).select_related('poem', 'start_verse', 'end_verse')


def rate_item(owner, pk, rating, request_id, now=None):
    for attempt in range(3):
        try:
            return _rate(owner, pk, rating, request_id, now or timezone.now())
        except (IntegrityError, OperationalError):
            if attempt == 2:
                raise ReviewConflict('ثبت هم‌زمان انجام نشد؛ دوباره تلاش کنید.')
            time.sleep(0.05 * (attempt + 1))


@transaction.atomic
def _rate(owner, pk, rating, request_id, now):
    # Keep lock order consistent with editing: poem, then item.
    poem_id = MemorizationItem.objects.filter(pk=pk, owner=owner).values_list('poem_id', flat=True).first()
    if poem_id is None:
        raise Http404
    poem = Poem.objects.select_for_update().get(pk=poem_id, owner=owner)
    item = MemorizationItem.objects.select_for_update().get(pk=pk, owner=owner)
    previous = ReviewLog.objects.filter(request_id=request_id).first()
    if previous:
        if previous.item_id != item.pk:
            raise ReviewConflict('شناسهٔ درخواست قبلاً استفاده شده است.')
        return previous
    if rating not in dict(ReviewLog.RATINGS):
        raise ValidationError('امتیاز معتبر نیست.')
    if item.status != 'active' or poem.archived_at or item.due_at > now:
        raise ReviewConflict('این کارت اکنون موعد مرور ندارد.')
    values = calculate_next_review(item, rating, now)
    log = ReviewLog.objects.create(item=item, request_id=request_id, rating=rating, reviewed_at=now,
                                  previous_due_at=item.due_at, next_due_at=values['due_at'],
                                  previous_interval_days=item.interval_days, next_interval_days=values['interval_days'])
    for key, value in values.items():
        setattr(item, key, value)
    item.review_count += 1
    item.last_reviewed_at = now
    item.save()
    return log
