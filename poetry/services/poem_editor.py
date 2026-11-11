from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from poetry.models import Poem, Verse
from .tags import save_tag


def parse_verses(text, mode):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if mode == 'pairs':
        if len(lines) % 2:
            raise ValidationError('تعداد سطرها فرد است؛ مصرع آخر را کامل کنید یا حالت هر خط یک بیت را انتخاب کنید.')
        rows = list(zip(lines[::2], lines[1::2]))
    elif mode == 'lines':
        rows = [tuple(line.split('|', 1)) if '|' in line else (line, '') for line in lines]
    else:
        raise ValidationError('روش ورود ابیات معتبر نیست.')
    return validate_verses(rows)


def validate_verses(rows):
    if not 1 <= len(rows) <= 500:
        raise ValidationError('بین ۱ تا ۵۰۰ بیت وارد کنید.')
    result = []
    for first, second in rows:
        first, second = first.strip(), second.strip()
        if not first or max(len(first), len(second)) > 1000:
            raise ValidationError('مصرع اول الزامی است و هر مصرع حداکثر ۱۰۰۰ نویسه دارد.')
        result.append((first, second))
    return result


@transaction.atomic
def save_poem(owner, data, rows, poem=None):
    rows = validate_verses(rows)
    is_edit = poem is not None
    if is_edit:
        poem = Poem.objects.select_for_update().get(pk=poem.pk, owner=owner)
    else:
        poem = Poem(owner=owner)
    tags = list(data['tags'])
    if any(tag.owner_id != owner.pk for tag in tags):
        raise ValidationError('موضوع معتبر نیست.')
    old = list(poem.verses.all()) if poem.pk else []
    if len(rows) < len(old):
        raise ValidationError('حذف بیت در این نسخه مجاز نیست؛ متن بیت‌ها را اصلاح کنید.')
    for field in ['title', 'poet_name', 'source_url', 'notes']:
        setattr(poem, field, data[field])
    poem.full_clean()
    poem.save()
    if data.get('new_tag'):
        tags.append(save_tag(owner, data['new_tag']))
    poem.tags.set(tags)
    changed = set()
    for index, (first, second) in enumerate(rows):
        if index < len(old):
            verse = old[index]
            if (verse.hemistich_1, verse.hemistich_2) == (first, second):
                continue
            verse.hemistich_1, verse.hemistich_2 = first, second
            verse.save(update_fields=['hemistich_1', 'hemistich_2'])
        else:
            Verse.objects.create(poem=poem, position=index + 1, hemistich_1=first, hemistich_2=second)
        changed.add(index + 1)
    if is_edit and changed:
        # Range endpoints are nullable. PostgreSQL can lock the cards, but not
        # the nullable side of the outer joins used to fetch those endpoints.
        items = poem.items.select_for_update(of=('self',)).select_related('start_verse', 'end_verse')
        for item in items:
            if item.scope == 'full' or any(item.start_verse.position <= p <= item.end_verse.position for p in changed):
                item.due_at, item.interval_days, item.streak = timezone.now(), 0, 0
                item.save(update_fields=['due_at', 'interval_days', 'streak', 'updated_at'])
    return poem
