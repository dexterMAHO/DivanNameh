from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.text import slugify
from poetry.models import Tag

def normalize_tag_name(name):
    return ' '.join(name.replace('ك', 'ک').replace('ي', 'ی').split()).casefold()

@transaction.atomic
def save_tag(owner, name, tag=None):
    normalized = normalize_tag_name(name)
    if not normalized or len(normalized) > 60:
        raise ValidationError('نام تگ باید بین ۱ تا ۶۰ نویسه باشد.')
    others = Tag.objects.filter(owner=owner).exclude(pk=tag.pk if tag else None)
    if others.filter(normalized_name=normalized).exists():
        raise ValidationError('این تگ قبلاً ساخته شده است.')
    base = slugify(normalized, allow_unicode=True) or 'tag'
    slug, suffix = base, 1
    while others.filter(slug=slug).exists():
        suffix += 1
        slug = f'{base}-{suffix}'
    tag = tag or Tag(owner=owner)
    if tag.owner_id != owner.pk:
        raise ValidationError('تگ معتبر نیست.')
    tag.name = normalized
    tag.normalized_name = normalized
    tag.slug = slug
    tag.full_clean()
    tag.save()
    return tag
