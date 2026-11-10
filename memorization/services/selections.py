from django.core.exceptions import ValidationError
from django.db import transaction
from memorization.models import MemorizationItem
from poetry.models import Poem


class DuplicateItem(ValidationError):
    pass


@transaction.atomic
def create_item(owner, poem, scope, start=None, end=None):
    poem = Poem.objects.select_for_update().get(pk=poem.pk, owner=owner)
    if poem.archived_at or not poem.verses.exists():
        raise ValidationError('فقط شعر فعال دارای بیت را می‌توان به حفظ افزود.')
    item = MemorizationItem(owner=owner, poem=poem, scope=scope, start_verse=start, end_verse=end)
    item.full_clean(validate_constraints=False)
    existing = MemorizationItem.objects.filter(owner=owner, poem=poem, scope=scope)
    if scope == 'range':
        existing = existing.filter(start_verse=start, end_verse=end)
    if existing.exists():
        raise DuplicateItem('این کارت قبلاً اضافه شده است.')
    item.save()
    return item


def get_item_verses(item):
    verses = item.poem.verses.all()
    if item.scope == 'range':
        verses = verses.filter(position__gte=item.start_verse.position, position__lte=item.end_verse.position)
    return verses
