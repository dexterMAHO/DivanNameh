from datetime import UTC
from uuid import NAMESPACE_URL, UUID, uuid5

from django.core.exceptions import ValidationError
from django.utils.dateparse import parse_datetime

from memorization.models import MemorizationItem, ReviewLog


CARD_COUNTS = ('interval_days', 'review_count', 'streak', 'lapses')
LOG_COUNTS = ('previous_interval_days', 'next_interval_days')
LOG_DATES = ('reviewed_at', 'previous_due_at', 'next_due_at')


def serialize_card(card, positions):
    return {
        'scope': card.scope,
        'start': positions.get(card.start_verse_id),
        'end': positions.get(card.end_verse_id),
        'status': card.status,
        'due_at': card.due_at.isoformat(),
        'last_reviewed_at': card.last_reviewed_at.isoformat() if card.last_reviewed_at else None,
        **{key: getattr(card, key) for key in CARD_COUNTS},
        'reviews': [
            {'id': str(log.transfer_id or log.request_id), 'rating': log.rating,
             **{key: getattr(log, key).isoformat() for key in LOG_DATES},
             **{key: getattr(log, key) for key in LOG_COUNTS}}
            for log in card.logs.all()
        ],
    }


def validated_date(value, *, optional=False):
    if optional and value is None:
        return None
    try:
        date = parse_datetime(value) if isinstance(value, str) and len(value) <= 50 else None
        if date and date.utcoffset() is not None and 1900 <= date.year <= 9900:
            return date.astimezone(UTC).isoformat()
    except (OverflowError, ValueError):
        pass
    raise ValidationError('تاریخ یکی از کارت‌ها یا مرورها معتبر نیست.')


def validated_counts(values, names):
    result = {}
    for name in names:
        value = values.get(name, 0)
        if type(value) is not int or not 0 <= value <= 365000:
            raise ValidationError('شمار یا فاصلهٔ مرور معتبر نیست.')
        result[name] = value
    return result


def validate_cards(cards, verse_count):
    if not isinstance(cards, list) or len(cards) > 1000:
        raise ValidationError('فهرست کارت‌ها معتبر نیست.')
    result = []
    scopes = set()
    for card in cards:
        if not isinstance(card, dict):
            raise ValidationError('ساختار کارت معتبر نیست.')
        scope = card.get('scope')
        start, end = card.get('start'), card.get('end')
        if not verse_count or not (
            (scope == 'full' and start is None and end is None) or
            (scope == 'range' and type(start) is int and type(end) is int and 1 <= start <= end <= verse_count)
        ):
            raise ValidationError('بازهٔ کارت معتبر نیست.')
        key = scope, start, end
        if key in scopes:
            raise ValidationError('بازهٔ کارت در این شعر تکراری است.')
        scopes.add(key)
        status = card.get('status')
        if status not in ('active', 'paused'):
            raise ValidationError('وضعیت کارت معتبر نیست.')
        logs = card.get('reviews', [])
        if not isinstance(logs, list) or len(logs) > 20000:
            raise ValidationError('فهرست مرورهای کارت معتبر نیست.')
        reviews = []
        seen = set()
        for log in logs:
            if not isinstance(log, dict) or log.get('rating') not in [value for value, _ in ReviewLog.RATINGS]:
                raise ValidationError('امتیاز مرور معتبر نیست.')
            try:
                identifier = str(UUID(log.get('id', ''))) if isinstance(log.get('id'), str) else None
            except ValueError:
                identifier = None
            if not identifier or identifier in seen:
                raise ValidationError('شناسهٔ مرور نامعتبر یا تکراری است.')
            seen.add(identifier)
            reviews.append({
                'id': identifier, 'rating': log['rating'],
                **{name: validated_date(log.get(name)) for name in LOG_DATES},
                **validated_counts(log, LOG_COUNTS),
            })
        result.append({
            'scope': scope, 'start': start, 'end': end, 'status': status, 'reviews': reviews,
            'due_at': validated_date(card.get('due_at')),
            'last_reviewed_at': validated_date(card.get('last_reviewed_at'), optional=True),
            **validated_counts(card, CARD_COUNTS),
        })
    return result


def restore_cards(poem, verses, cards):
    for row in cards:
        start = verses[row['start'] - 1] if row['start'] else None
        end = verses[row['end'] - 1] if row['end'] else None
        state = {name: row[name] for name in ('status', 'due_at', 'last_reviewed_at', *CARD_COUNTS)}
        state['due_at'] = parse_datetime(state['due_at'])
        state['last_reviewed_at'] = parse_datetime(state['last_reviewed_at']) if state['last_reviewed_at'] else None
        card, created = MemorizationItem.objects.get_or_create(
            owner_id=poem.owner_id, poem=poem, scope=row['scope'], start_verse=start, end_verse=end, defaults=state,
        )
        if not row['reviews']:
            continue
        existing = {str(origin or identifier) for identifier, origin in card.logs.values_list('request_id', 'transfer_id')}
        logs = [
            ReviewLog(
                item=card, transfer_id=log['id'],
                request_id=uuid5(NAMESPACE_URL, f'divannameh-review:{card.pk}:{log["id"]}'),
                rating=log['rating'],
                **{name: parse_datetime(log[name]) for name in LOG_DATES},
                **{name: log[name] for name in LOG_COUNTS},
            )
            for log in row['reviews'] if log['id'] not in existing
        ]
        if not logs:
            continue
        ReviewLog.objects.bulk_create(logs, batch_size=500)
        if not created:
            incoming = state['last_reviewed_at']
            if incoming and (card.last_reviewed_at is None or incoming > card.last_reviewed_at):
                for name in ('due_at', 'last_reviewed_at', 'interval_days', 'streak', 'lapses'):
                    setattr(card, name, state[name])
            card.review_count = max(card.review_count, card.logs.count())
            card.save(update_fields=['due_at', 'last_reviewed_at', 'interval_days', 'streak', 'lapses', 'review_count'])
