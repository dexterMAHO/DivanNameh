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
        raise ValidationError('نام موضوع باید بین ۱ تا ۶۰ نویسه باشد.')
    others = Tag.objects.filter(owner=owner).exclude(pk=tag.pk if tag else None)
    if others.filter(normalized_name=normalized).exists():
        raise ValidationError('این موضوع قبلاً ساخته شده است.')
    base = slugify(normalized, allow_unicode=True) or 'tag'
    slug, suffix = base, 1
    while others.filter(slug=slug).exists():
        suffix += 1
        slug = f'{base}-{suffix}'
    tag = tag or Tag(owner=owner)
    if tag.owner_id != owner.pk:
        raise ValidationError('موضوع معتبر نیست.')
    tag.name = normalized
    tag.normalized_name = normalized
    tag.slug = slug
    tag.full_clean()
    tag.save()
    return tag


@transaction.atomic
def merge_tags(owner, source_id, target_id):
    from poetry.models import Poem, PoemEditRequest

    if source_id == target_id:
        raise ValidationError('موضوع مبدأ و مقصد باید متفاوت باشند.')
    ids = [source_id, target_id]
    # The edit workflow also locks a poem before changing its topic references.
    list(Poem.objects.filter(owner=owner).select_for_update().order_by('pk').values_list('pk', flat=True))
    poems = Poem.objects.filter(owner=owner, tags=source_id)
    tags = {tag.pk: tag for tag in Tag.objects.select_for_update().filter(owner=owner, pk__in=ids).order_by('pk')}
    if len(tags) != 2:
        raise ValidationError('موضوع انتخاب‌شده در دفتر شما نیست.')
    target = tags[target_id]
    for poem in poems:
        poem.tags.add(target)
    edits = PoemEditRequest.objects.filter(poem__owner=owner, status='pending')
    for edit in edits.iterator(chunk_size=100):
        requested = edit.payload.get('tags', [])
        if source_id in requested:
            edit.payload['tags'] = list(dict.fromkeys(target_id if pk == source_id else pk for pk in requested))
            topics = edit.payload.get('topics', [])
            if tags[source_id].name in topics:
                edit.payload['topics'] = sorted({target.name if name == tags[source_id].name else name for name in topics})
            edit.save(update_fields=['payload'])
    tags[source_id].delete()
