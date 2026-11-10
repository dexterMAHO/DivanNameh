from poetry.models import Poem


def choose_random_poem(owner, exclude_id=None):
    poems = Poem.objects.filter(owner=owner, archived_at__isnull=True, verses__isnull=False).distinct().prefetch_related('verses', 'tags')
    if exclude_id and str(exclude_id).isdigit() and poems.exclude(pk=exclude_id).exists():
        poems = poems.exclude(pk=exclude_id)
    return poems.order_by('?').first()
