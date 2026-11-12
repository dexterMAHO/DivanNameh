import json
from hashlib import sha256

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from memorization.services.transfer import restore_cards, serialize_card, validate_cards
from poetry.models import FavoriteVerse, Poem, Tag, Verse

from .tags import normalize_tag_name, save_tag


FORMAT = 'divannameh-library'
VERSION = 1
MAX_BYTES = 16 * 1024 * 1024
MAX_POEMS = 1000
URL = URLValidator(schemes=['https', 'http'])


def export_poems(owner, *, include_cards=False):
    related = ['tags', 'verses__favorites']
    if include_cards:
        related.append('items__logs')
    return Poem.objects.filter(owner=owner).prefetch_related(*related).order_by('pk')


def export_row(poem):
    verses = list(poem.verses.all())
    positions = {verse.pk: position for position, verse in enumerate(verses, 1)}
    return {
        'title': poem.title, 'poet': poem.poet_name, 'source': poem.source_url,
        'notes': poem.notes, 'line_layout': poem.line_layout, 'archived': poem.archived_at is not None,
        'topics': [topic.name for topic in poem.tags.all()],
        'verses': [[verse.hemistich_1, verse.hemistich_2] for verse in verses],
        'favorites': [index for index, verse in enumerate(verses, 1)
                      if any(favorite.owner_id == poem.owner_id for favorite in verse.favorites.all())],
        'cards': [serialize_card(card, positions) for card in poem.items.all() if card.owner_id == poem.owner_id],
    }


def validate_document(file):
    if file.size > MAX_BYTES:
        raise ValidationError('حجم فایل باید حداکثر ۱۶ مگابایت باشد.')
    try:
        data = json.loads(file.read().decode('utf-8-sig'))
    except (UnicodeDecodeError, ValueError, RecursionError) as error:
        raise ValidationError('فایل JSON معتبر نیست.') from error
    if not isinstance(data, dict) or data.get('format') != FORMAT or type(data.get('version')) is not int or data['version'] != VERSION:
        raise ValidationError('نسخه یا قالب فایل دیوان‌نامه پشتیبانی نمی‌شود.')
    rows = data.get('poems')
    if not isinstance(rows, list) or len(rows) > MAX_POEMS:
        raise ValidationError('در هر بار حداکثر ۱۰۰۰ شعر وارد کنید.')
    result = []
    for index, row in enumerate(rows, 1):
        try:
            result.append(validate_row(row))
        except ValidationError as error:
            raise ValidationError(f'شعر شمارهٔ {index}: {error.messages[0]}') from error
    return {'poems': result, 'topics': validate_topics(data.get('topics', []))}


def validate_row(row):
    if not isinstance(row, dict):
        raise ValidationError('ساختار شعر معتبر نیست.')

    def text(name, maximum, *, required=False):
        value = row.get(name, '')
        if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
            raise ValidationError(f'مقدار «{name}» معتبر نیست.')
        validate_string(value)
        return value

    source = text('source', 500)
    if source:
        URL(source)
    line_layout = row.get('line_layout', False)
    archived = row.get('archived', False)
    if not isinstance(line_layout, bool) or not isinstance(archived, bool):
        raise ValidationError('وضعیت آرشیو یا چیدمان معتبر نیست.')
    verses = row.get('verses')
    if not isinstance(verses, list) or len(verses) > 10000:
        raise ValidationError('فهرست ردیف‌ها معتبر نیست.')
    for verse in verses:
        if not isinstance(verse, list) or len(verse) != 2 or not all(isinstance(part, str) and len(part) <= 20000 for part in verse) or not verse[0].strip():
            raise ValidationError('هر ردیف باید متن اول و یک متن دوم اختیاری داشته باشد.')
        for part in verse:
            validate_string(part)
    favorites = row.get('favorites', [])
    if not isinstance(favorites, list) or not all(type(index) is int and 1 <= index <= len(verses) for index in favorites):
        raise ValidationError('شمارهٔ یکی از شاه‌بیت‌ها معتبر نیست.')
    return {
        'title': text('title', 200), 'poet': text('poet', 160, required=True),
        'notes': text('notes', MAX_BYTES), 'source': source,
        'line_layout': line_layout, 'archived': archived, 'verses': verses,
        'topics': validate_topics(row.get('topics', [])),
        'cards': validate_cards(row.get('cards', []), len(verses)),
        'favorites': sorted(set(favorites)),
    }


def validate_topics(topics):
    if not isinstance(topics, list) or len(topics) > 500 or not all(
        isinstance(topic, str) and 0 < len(normalize_tag_name(topic)) <= 60 for topic in topics
    ):
        raise ValidationError('فهرست موضوع‌ها معتبر نیست.')
    for topic in topics:
        validate_string(topic)
    return sorted({normalize_tag_name(topic) for topic in topics})


def validate_string(value):
    if '\x00' in value or any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise ValidationError('متن شامل نویسهٔ نامعتبر است.')


def identity(title, poet, line_layout, verses):
    value = json.dumps([title, poet, line_layout, verses], ensure_ascii=False, separators=(',', ':'))
    return sha256(value.encode()).hexdigest()


def build_plan(owner, rows):
    existing = {}
    names = set()
    poets = {row['poet'] for row in rows}
    poems = Poem.objects.filter(owner=owner, poet_name__in=poets).prefetch_related('verses').order_by('pk')
    for poem in poems.iterator(chunk_size=200):
        key = identity(poem.title, poem.poet_name, poem.line_layout,
                       [(verse.hemistich_1, verse.hemistich_2) for verse in poem.verses.all()])
        existing.setdefault(key, poem)
        names.add((poem.title, poem.poet_name))

    plan = []
    seen = set(existing)
    for row in rows:
        key = identity(row['title'], row['poet'], row['line_layout'], row['verses'])
        name = (row['title'], row['poet'])
        kind = 'duplicate' if key in seen else 'variant' if name in names and row['title'] else 'new'
        plan.append((key, row, kind))
        seen.add(key)
        names.add(name)
    return existing, plan


@transaction.atomic
def apply_plan(owner, rows, *, include_variants=False, topics=()):
    owner = User.objects.select_for_update().get(pk=owner.pk)
    existing, plan = build_plan(owner, rows)
    tags = {tag.normalized_name: tag for tag in Tag.objects.filter(owner=owner)}
    for name in topics:
        if name not in tags:
            tags[name] = save_tag(owner, name)
    created = 0
    for key, row, kind in plan:
        poem = existing.get(key)
        if poem is None:
            if (kind == 'variant' and not include_variants) or kind == 'duplicate':
                continue
            poem = Poem.objects.create(
                owner=owner, title=row['title'], poet_name=row['poet'], source_url=row['source'],
                notes=row['notes'], line_layout=row['line_layout'], archived_at=timezone.now() if row['archived'] else None,
            )
            Verse.objects.bulk_create([
                Verse(poem=poem, position=position, hemistich_1=first, hemistich_2=second)
                for position, (first, second) in enumerate(row['verses'], 1)
            ], batch_size=500)
            existing[key] = poem
            created += 1
        selected = []
        for name in row['topics']:
            if name not in tags:
                tags[name] = save_tag(owner, name)
            selected.append(tags[name])
        if selected:
            poem.tags.add(*selected)
        if row['favorites'] or row.get('cards'):
            verses = list(poem.verses.all())
            FavoriteVerse.objects.bulk_create([
                FavoriteVerse(owner=owner, verse=verses[index - 1]) for index in row['favorites']
            ], ignore_conflicts=True)
            if row.get('cards'):
                Poem.objects.select_for_update().only('pk').get(pk=poem.pk)
                restore_cards(poem, verses, row['cards'])
    return created
