"""What the home page shows, drawn from the reader's own shelf.

The home page offers one verse and a few onward paths. Both come from stored
data: a verse the reader kept, a poem they last read, or an editor-published
work from the treasury. Nothing here is sample content, and the daily verse is
chosen by the local date so it holds still for the whole day instead of
changing on every reload.
"""

from django.utils import timezone

from poetry.models import FavoriteVerse, Poem
from poetry.services.editorial import public_picks, quote_row


def _pick_for_today(count):
    """A stable index for the day, so "today's verse" means today."""
    return timezone.localdate().toordinal() % count if count else None


def verse_of_day(user):
    """One real verse with a way back to the poem it came from.

    Preference order follows how close the verse is to the reader: a verse they
    marked as a شاه‌بیت, then the poem they touched most recently, then the
    public treasury so a brand-new account still has something to read.
    """
    if user.is_authenticated:
        favorites = FavoriteVerse.objects.filter(
            owner=user, verse__poem__archived_at__isnull=True,
        ).select_related('verse__poem')
        index = _pick_for_today(favorites.count())
        if index is not None:
            favorite = favorites.order_by('pk')[index]
            verse = favorite.verse
            return {
                'first': verse.hemistich_1, 'second': verse.hemistich_2,
                'poet': verse.poem.poet_name, 'title': verse.poem.display_title,
                'url': f'{verse.poem.get_absolute_url()}#verse-{verse.position}',
                'origin': 'از شاه‌بیت‌های شما',
            }
        recent = (Poem.objects.filter(owner=user, archived_at__isnull=True)
                  .prefetch_related('verses').first())
        if recent and (verse := recent.excerpt_verse):
            return {
                'first': verse.hemistich_1, 'second': verse.hemistich_2,
                'poet': recent.poet_name, 'title': recent.display_title,
                'url': f'{recent.get_absolute_url()}#verse-{verse.position}',
                'origin': 'از تازه‌ترین شعر دفتر شما',
            }
    picks = public_picks().select_related('entry__book')
    index = _pick_for_today(picks.count())
    if index is None:
        return None
    pick = picks.order_by('pk')[index]
    row = quote_row(pick, pick.sample_position)
    if not row:
        return None
    return {
        'first': row[0], 'second': row[1],
        'poet': pick.entry.book.author, 'title': pick.entry.title,
        'url': f'{pick.entry.get_absolute_url()}#verse-{pick.sample_position}',
        'origin': 'از گنجینهٔ عمومی',
    }


def suggested_reading(limit=3):
    """Editor-published works, so a suggestion always opens a complete text."""
    picks = (public_picks().select_related('entry__book').defer('entry__search_body')
             .order_by('-featured', 'pk'))
    count = picks.count()
    if not count:
        return []
    start = _pick_for_today(count)
    # Wrap around so the window is full even when today's index is near the end.
    window = list(picks[start:start + limit])
    if len(window) < min(limit, count):
        window += list(picks[:min(limit, count) - len(window)])
    return [
        {'title': pick.entry.title, 'poet': pick.entry.book.author,
         'url': pick.entry.get_absolute_url()}
        for pick in window
    ]
