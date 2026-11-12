from django.db.models import Count

from poetry.models import Poem

from .search import search_field, search_text


def numeric_id(value):
    value = str(value or '')
    return int(value) if value.isascii() and value.isdigit() and len(value) <= 18 else None


def choose_random_poem(owner, exclude_id=None, *, poet='', topic='', length='', recent=(), keep_id=None):
    poems = Poem.objects.filter(owner=owner, archived_at__isnull=True, verses__isnull=False)
    poems = poems.distinct().prefetch_related('verses', 'tags')
    if poet:
        poems = poems.alias(poet_search=search_field('poet_name')).filter(poet_search__icontains=search_text(poet))
    if topic:
        poems = poems.filter(tags__owner=owner, tags__slug=topic)
    if length in ('short', 'long'):
        poems = poems.annotate(line_count=Count('verses', distinct=True))
        poems = poems.filter(line_count__lte=8) if length == 'short' else poems.filter(line_count__gt=8)
    if keep := numeric_id(keep_id):
        existing = poems.filter(pk=keep).first()
        if existing:
            return existing
    exclude = numeric_id(exclude_id)
    preferred = poems.exclude(pk__in={*recent, exclude}).order_by('?').first() if recent or exclude else None
    if preferred:
        return preferred
    if exclude:
        different = poems.exclude(pk=exclude).order_by('?').first()
        if different:
            return different
    return poems.order_by('?').first()
