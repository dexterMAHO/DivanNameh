from django.db import transaction
from django.utils import timezone

from accounts.models import User
from memorization.services.selections import DuplicateItem, create_item
from poetry.models import FavoriteVerse, Poem, Verse


def add_review(owner, poem, verses):
    ordered = sorted(verses, key=lambda verse: verse.position)
    groups = []
    for verse in ordered:
        if not groups or verse.position != groups[-1][-1].position + 1:
            groups.append([])
        groups[-1].append(verse)
    for group in groups:
        try:
            create_item(owner, poem, 'range', group[0], group[-1])
        except DuplicateItem:
            continue


@transaction.atomic
def save_public_work(owner, entry, rows, positions, action, *, line_layout=False):
    User.objects.select_for_update().get(pk=owner.pk)
    candidates = Poem.objects.select_for_update().filter(
        owner=owner, treasury_book_slug=entry.book.slug, treasury_entry_key=entry.key,
    ).order_by('archived_at', 'pk')
    if action == 'unfavorite':
        FavoriteVerse.objects.filter(
            owner=owner, verse__poem__in=candidates, verse__treasury_position=positions[0],
        ).delete()
        return None

    candidates = list(candidates)
    poem = next((candidate for candidate in candidates
                 if candidate.treasury_edition == entry.book.dataset_digest
                 and candidate.treasury_positions == list(range(1, len(rows) + 1))), None)
    if poem is None:
        poem = next((candidate for candidate in candidates
                     if candidate.treasury_edition == entry.book.dataset_digest and candidate.treasury_positions), None)
    if poem is None:
        poem = Poem.objects.create(
            owner=owner, title=entry.title[:200], poet_name=entry.book.author[:160], source_url=entry.source_url,
            line_layout=line_layout,
            treasury_book_slug=entry.book.slug, treasury_entry_key=entry.key,
            treasury_edition=entry.book.dataset_digest,
        )
    known = {verse.treasury_position: verse for verse in poem.verses.all() if verse.treasury_position}
    required = list(range(1, len(rows) + 1))
    missing = [position for position in required if position not in known]
    last = poem.verses.order_by('-position').values_list('position', flat=True).first() or 0
    additions = Verse.objects.bulk_create([
        Verse(poem=poem, treasury_position=position, position=last + index,
              hemistich_1=rows[position - 1][0], hemistich_2=rows[position - 1][1])
        for index, position in enumerate(missing, 1)
    ])
    if missing or poem.archived_at:
        poem.archived_at = None
        poem.treasury_positions = [*known, *missing]
        poem.save(update_fields=['archived_at', 'treasury_positions', 'updated_at'])
        if missing and known:
            poem.items.filter(scope='full').update(due_at=timezone.now(), interval_days=0, streak=0)
    known.update({verse.treasury_position: verse for verse in additions})
    if action == 'favorite':
        favorite_exists = FavoriteVerse.objects.filter(
            owner=owner, verse__poem__in=[*candidates, poem], verse__treasury_position=positions[0],
        ).exists()
        if not favorite_exists:
            FavoriteVerse.objects.get_or_create(owner=owner, verse=known[positions[0]])
    elif action == 'memorize':
        add_review(owner, poem, [known[position] for position in positions])
    return poem
