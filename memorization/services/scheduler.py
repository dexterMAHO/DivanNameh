from datetime import timedelta


def calculate_next_review(item, rating, now):
    previous = item.interval_days
    if rating == 'again':
        return dict(interval_days=0, due_at=now + timedelta(minutes=10), streak=0, lapses=item.lapses + 1)
    if rating == 'hard':
        days = 1 if previous == 0 else max(1, round(previous * 1.2))
    elif rating == 'good':
        days = 1 if previous == 0 else max(2, round(previous * 2.2))
    elif rating == 'easy':
        days = 3 if previous == 0 else max(3, round(previous * 3.0))
    else:
        raise ValueError('Invalid rating')
    return dict(interval_days=days, due_at=now + timedelta(days=days), streak=item.streak + 1, lapses=item.lapses)
