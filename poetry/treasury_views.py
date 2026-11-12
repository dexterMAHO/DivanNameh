import hashlib
import json
from collections import defaultdict

from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from accounts.permissions import action_password_error
from memorization.models import MemorizationItem
from memorization.services.reviews import get_due_items

from .treasury_forms import is_line_poem
from .http import failure, private, success
from .models import FavoriteVerse, Poem, TreasuryBook, TreasuryEntry, Verse
from .services.discovery import numeric_id
from .services.search import search_field, search_text
from .services.treasury_metadata import ALPHABET
SORTS = {
    'name': ('author', 'slug'),
    'works': ('-work_count', 'author', 'slug'),
    'era': (F('century').asc(nulls_last=True), 'author', 'slug'),
}
PER_PAGE = 24


def filtered_books(params):
    """Narrow the poet list by search text, first letter and lunar-hijri century."""
    books = TreasuryBook.objects.all()
    query = params.get('q', '').strip()[:120]
    term = search_text(query)
    if term:
        books = books.alias(author_search=search_field('author'), bio_search=search_field('biography'),
                            place_search=search_field('birth_place')).filter(
            Q(author_search__icontains=term) | Q(bio_search__icontains=term) | Q(place_search__icontains=term))
    letter = params.get('letter', '')[:1]
    if letter in ALPHABET:
        books = books.alias(author_search=search_field('author')).filter(author_search__startswith=letter)
    else:
        letter = ''
    raw_century = params.get('century', '')[:2]
    century = str(int(raw_century)) if raw_century.isdecimal() else ''
    if century:
        books = books.filter(century=century)
    sort = params.get('sort') if params.get('sort') in SORTS else 'name'
    return books.order_by(*SORTS[sort]), {'query': query, 'letter': letter,
                                          'century': century, 'sort': sort}


@private
@require_GET
def index(request):
    books, filters = filtered_books(request.GET)
    totals = TreasuryBook.objects.aggregate(poets=Count('pk'), works=Sum('work_count'))
    centuries = (TreasuryBook.objects.filter(century__isnull=False)
                 .values_list('century', flat=True).order_by('century').distinct())
    page = Paginator(books, PER_PAGE).get_page(request.GET.get('page'))
    return render(request, 'poetry/treasury.html', {
        'page': page,
        'matches': page.paginator.count,
        'totals': totals,
        'centuries': list(centuries),
        'alphabet': ALPHABET,
        'filtered': bool(filters['query'] or filters['letter'] or filters['century']),
        **filters,
    })


@private
@require_GET
def works_search(request):
    query = request.GET.get('q', '').strip()[:120]
    term = search_text(query)
    book = request.GET.get('book', '')[:120]
    works = TreasuryEntry.objects.filter(kind='work').select_related('book').alias(
        search_title=search_field('title'), search_author=search_field('book__author'),
    ).defer('search_body', 'book__biography')
    if book:
        works = works.filter(book__slug=book)
    if term:
        works = works.filter(Q(search_title__icontains=term) | Q(search_author__icontains=term)
                             | Q(book__publishes_text=True, has_text=True, search_body__icontains=term))
    elif not book:
        works = works.none()
    works = works.order_by('book__author', 'book_id', 'position', 'pk')
    page = Paginator(works, PER_PAGE).get_page(request.GET.get('page'))
    for entry in page:
        entry.snippet = ''
        if term and entry.book.publishes_text:
            entry.snippet = next((line for paragraph in entry.paragraphs or [] for line in paragraph.splitlines()
                                  if term in search_text(line, limit=None)), '')
    return render(request, 'poetry/treasury_search.html', {'query': query, 'book_slug': book, 'page': page})


def skip_single_root(book, depth=3):
    """Most EPUBs wrap everything in one root section; list its contents instead of it."""
    skipped = []
    parent = None
    for _ in range(depth):
        children = list(book.entries.filter(parent=parent).only('pk', 'kind')[:2])
        if len(children) != 1 or children[0].kind != 'section':
            break
        parent = children[0]
        skipped.append(parent)
    return parent, {entry.pk for entry in skipped}


@private
@require_GET
def book_detail(request, slug, key=None):
    book = get_object_or_404(TreasuryBook, slug=slug)
    current = get_object_or_404(TreasuryEntry.objects.defer('search_body'), book=book, key=key) if key else None
    listing_root, skipped = skip_single_root(book)
    parents = entry_sections(current) if current else []
    ancestors = [parent for parent in parents if parent.pk not in skipped]
    line_layout, rows = reading_rows(current, book, parents) if current and current.kind == 'work' else (False, [])
    saved = set()
    if rows:
        digests = {
            selection_digest(book.slug, current.key, [position], [row]): position
            for position, row in enumerate(rows, 1)
        }
        saved_digests = FavoriteVerse.objects.filter(
            owner=request.user, verse__poem__treasury_selection__in=digests,
            verse__poem__archived_at__isnull=True, verse__position=1,
        ).values_list('verse__poem__treasury_selection', flat=True)
        saved = {digests[digest] for digest in saved_digests}
    sections, groups, count, page = ([], [], 0, None)
    if not current or current.kind == 'section':
        sections, groups, count, page = work_listing(book, current or listing_root, request.GET)
    merge_targets = []
    if rows:
        merge_targets = Poem.objects.filter(
            owner=request.user, treasury_book_slug=slug, treasury_entry_key=current.key,
            treasury_edition=book.dataset_digest, line_layout=line_layout,
        ).filter(archived_at__isnull=True).exclude(treasury_positions=[]).only('pk', 'title')[:20]
    origin = request.GET.get('from', '')
    treasury_back = origin if origin.startswith(reverse('treasury-works')) and url_has_allowed_host_and_scheme(origin, allowed_hosts=set()) else ''
    return render(request, 'poetry/treasury_book.html', {
        'treasury_back': treasury_back, 'entry_has_text': bool(current and book.publishes_text and current.paragraphs),
        'book': book, 'entry': current, 'ancestors': reversed(ancestors),
        'sections': sections, 'groups': groups, 'work_count': count, 'page': page,
        'work_query': request.GET.get('q', '').strip()[:120], 'merge_targets': merge_targets,
        'rows': rows, 'line_layout': line_layout, 'saved_positions': saved,
    })



def entry_sections(entry):
    parents = []
    parent = entry.parent
    while parent:
        parents.append(parent)
        parent = parent.parent
    return parents


def reading_rows(entry, book, parents):
    if not book.publishes_text:
        return False, []
    line_layout = is_line_poem(book.slug, entry.key, entry.title,
                               [(parent.key, parent.title) for parent in parents])
    if line_layout:
        return True, [
            (line, '') for paragraph in entry.paragraphs or []
            for line in paragraph.splitlines() if line.strip()
        ]
    return False, entry.couplets or []


def discover_work(exclude_id, *, poet='', length='', recent=(), keep_id=None):
    works = TreasuryEntry.objects.filter(kind='work', reading_count__gt=0)
    if length == 'short':
        works = works.filter(reading_count__lte=8)
    elif length == 'long':
        works = works.filter(reading_count__gt=8)
    if poet:
        works = works.alias(author_search=search_field('book__author')).filter(author_search__icontains=search_text(poet))

    def candidate(entry):
        if entry is None:  # A concurrent import may replace an entry.
            return None
        line_layout, rows = reading_rows(entry, entry.book, entry_sections(entry))
        if not rows or (length == 'short' and len(rows) > 8) or (length == 'long' and len(rows) <= 8):
            return None
        return {'entry': entry, 'line_layout': line_layout, 'rows': rows[:4]}

    if keep := numeric_id(keep_id):
        if result := candidate(works.select_related('book').defer('search_body').filter(pk=keep).first()):
            return result

    # Project only IDs and cap the candidate set before loading text.
    candidate_ids = list(works.order_by('?').values_list('pk', flat=True)[:64])
    exclude = numeric_id(exclude_id)
    candidate_ids.sort(key=lambda pk: (pk == exclude, pk in recent))
    for pk in candidate_ids:
        if result := candidate(works.select_related('book').defer('search_body').filter(pk=pk).first()):
            return result
    return None


def selection_digest(slug, key, positions, rows):
    identity = json.dumps([slug, key, positions, rows], ensure_ascii=False)
    return hashlib.sha256(identity.encode()).hexdigest()

def work_listing(book, root, params):
    children = defaultdict(list)
    term = search_text(params.get('q', ''))
    for child in book.entries.defer('source_url', 'paragraphs', 'search_body').iterator():
        child.book = book
        children[child.parent_id].append(child)
    root_id = root.pk if root else None
    sections = [child for child in children[root_id] if child.kind == 'section']
    parents = [(item.key, item.title) for item in ([root, *entry_sections(root)] if root else [])]
    stack = [(child, parents) for child in reversed(children[root_id])]
    grouped = defaultdict(list)
    while stack:
        child, parents = stack.pop()
        if child.kind == 'section':
            stack.extend((item, [(child.key, child.title), *parents]) for item in reversed(children[child.pk]))
        elif not term or term in search_text(child.title, limit=None):
            line_layout = is_line_poem(book.slug, child.key, child.title, parents)
            letter = '' if line_layout else child.opening_ending
            section = parents[0][1] if parents and parents[0][0] != (root.key if root else None) else ''
            grouped[letter].append((child, section))
    works = [(letter, child, section) for letter in (*ALPHABET, '') for child, section in grouped[letter]]
    page = Paginator(works, 48).get_page(params.get('page'))
    groups = defaultdict(list)
    for letter, child, section in page:
        groups[letter].append((child, section))
    return sections, list(groups.items()), len(works), page


@private
@require_POST
def save_selection(request, slug, key):
    entry = get_object_or_404(TreasuryEntry.objects.select_related('book'),
                              book__slug=slug, key=key, kind='work')
    line_layout, rows = reading_rows(entry, entry.book, entry_sections(entry))
    if not rows:
        return failure(request, 'این اثر بیتِ قابل ذخیره ندارد.')
    action = request.POST.get('action', '')
    if action == 'memorize' and (error := action_password_error(request)):
        return failure(request, error, status=403)
    if action == 'library-all':
        positions = list(range(1, len(rows) + 1))
    elif action.partition(':')[0] in ('favorite', 'unfavorite'):
        action, _, position = action.partition(':')
        positions = [position]
    elif action in ('library', 'memorize', 'merge'):
        positions = request.POST.getlist('verse')
        if action == 'memorize' and not positions:
            positions = list(range(1, len(rows) + 1))
    else:
        return failure(request, 'عملیات ناشناخته است.')
    try:
        positions = sorted(set(map(int, positions)))
    except ValueError:
        return failure(request, 'شمارهٔ بیت معتبر نیست.')
    if not positions or positions[0] < 1 or positions[-1] > len(rows):
        return failure(request, 'دست‌کم یک بیت معتبر انتخاب کنید.')

    selected = [rows[position - 1] for position in positions]
    digest = selection_digest(slug, key, positions, selected)
    if action == 'merge':
        target_id = request.POST.get('merge_poem', '')
        if not target_id.isascii() or not target_id.isdigit() or len(target_id) > 18:
            return failure(request, 'شعر مقصد را انتخاب کنید.')
        with transaction.atomic():
            poem = get_object_or_404(Poem.objects.select_for_update(), pk=target_id, owner=request.user,
                                     treasury_book_slug=slug, treasury_entry_key=key, line_layout=line_layout,
                                     treasury_edition=entry.book.dataset_digest, archived_at__isnull=True)
            if not poem.treasury_positions:
                return failure(request, 'منشأ ردیف‌های نسخهٔ مقصد در دسترس نیست.')
            added = [position for position in positions if position not in poem.treasury_positions]
            last = poem.verses.order_by('-position').values_list('position', flat=True).first() or 0
            Verse.objects.bulk_create([
                Verse(poem=poem, position=last + index, treasury_position=position, hemistich_1=rows[position - 1][0], hemistich_2=rows[position - 1][1])
                for index, position in enumerate(added, 1)
            ])
            if added:
                poem.treasury_positions.extend(added)
                poem.save(update_fields=['treasury_positions', 'updated_at'])
                poem.items.filter(scope='full').update(due_at=timezone.now(), interval_days=0, streak=0)
        message = 'گزیده به انتهای نسخهٔ شخصی افزوده شد.' if added else 'همهٔ ردیف‌ها از قبل در نسخهٔ شخصی هستند.'
        return success(request, message, poem.get_absolute_url(), target_url=poem.get_absolute_url(), target_label='دیدن شعر در دفتر')
    if action == 'unfavorite':
        FavoriteVerse.objects.filter(
            owner=request.user, verse__poem__treasury_selection=digest, verse__position=1,
        ).delete()
        return success(request, 'نشان شاه‌بیت برداشته شد.', entry.get_absolute_url(), favorite=False)
    with transaction.atomic():
        poem, created = Poem.objects.select_for_update().get_or_create(
            owner=request.user, treasury_selection=digest, defaults={
                'title': entry.title[:200], 'poet_name': entry.book.author[:160],
                'source_url': entry.source_url, 'line_layout': line_layout,
                'treasury_book_slug': slug, 'treasury_entry_key': key,
                'treasury_positions': positions, 'treasury_edition': entry.book.dataset_digest,
            },
        )
        if not created and not poem.treasury_entry_key:
            poem.treasury_book_slug = slug
            poem.treasury_entry_key = key
            poem.treasury_positions = positions
            poem.treasury_edition = entry.book.dataset_digest
            poem.save(update_fields=['treasury_book_slug', 'treasury_entry_key', 'treasury_positions', 'treasury_edition'])
            verses = list(poem.verses.all())
            for verse, original in zip(verses, positions):
                verse.treasury_position = original
            Verse.objects.bulk_update(verses[:len(positions)], ['treasury_position'], batch_size=500)
        if created:
            Verse.objects.bulk_create([
                Verse(poem=poem, position=index, treasury_position=original, hemistich_1=first, hemistich_2=second)
                for index, (original, (first, second)) in enumerate(zip(positions, selected), 1)
            ])
        if poem.archived_at:
            poem.archived_at = None
            poem.save(update_fields=['archived_at', 'updated_at'])
        if action == 'favorite':
            FavoriteVerse.objects.get_or_create(owner=request.user, verse=poem.verses.first())
        elif action == 'memorize':
            MemorizationItem.objects.get_or_create(owner=request.user, poem=poem, scope='full')

    messages = {
        'favorite': ('شاه‌بیت در دفتر ثبت شد؛ برداشتن نشان، نسخهٔ دفتر را نگه می‌دارد.', 'favorites'),
        'memorize': ('به فهرست حفظ افزوده شد.', 'memorize'),
    }
    message, target = messages.get(action, ('در کتابخانه ذخیره شد.', poem.get_absolute_url()))
    data = {'favorite': True} if action == 'favorite' else {
        'target_url': reverse('memorize') if action == 'memorize' else poem.get_absolute_url(),
        'target_label': 'دیدن فهرست حفظ' if action == 'memorize' else 'دیدن شعر در دفتر',
    }
    if action == 'memorize':
        data['remaining_due_count'] = get_due_items(request.user).count()
    return success(request, message, target, **data)
