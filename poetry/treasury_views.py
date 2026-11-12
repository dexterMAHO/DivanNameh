import hashlib
import json
import unicodedata
from collections import defaultdict

from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from memorization.models import MemorizationItem

from .treasury_forms import is_line_poem
from .http import failure, private, success
from .models import FavoriteVerse, Poem, TreasuryBook, TreasuryEntry, Verse

ALPHABET = tuple('آابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی')
SORTS = {
    'name': ('author', 'slug'),
    'works': ('-work_count', 'author'),
    'era': ('century', 'author'),
}
PER_PAGE = 24


def filtered_books(params):
    """Narrow the poet list by search text, first letter and lunar-hijri century."""
    books = TreasuryBook.objects.all()
    query = params.get('q', '').strip()[:120]
    if query:
        books = books.filter(Q(author__icontains=query) | Q(biography__icontains=query)
                             | Q(birth_place__icontains=query))
    letter = params.get('letter', '')[:1]
    if letter in ALPHABET:
        books = books.filter(author__startswith=letter)
    else:
        letter = ''
    century = params.get('century', '')[:2]
    books = books.filter(century=century) if century.isdigit() else books
    sort = params.get('sort') if params.get('sort') in SORTS else 'name'
    return books.order_by(*SORTS[sort]), {'query': query, 'letter': letter,
                                          'century': century if century.isdigit() else '', 'sort': sort}


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
    current = get_object_or_404(TreasuryEntry, book=book, key=key) if key else None
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
    sections, groups, count = ([], [], 0)
    if not current or current.kind == 'section':
        sections, groups, count = work_listing(book, current or listing_root)
    return render(request, 'poetry/treasury_book.html', {
        'book': book, 'entry': current, 'ancestors': reversed(ancestors),
        'sections': sections, 'groups': groups, 'work_count': count,
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
    line_layout = is_line_poem(book.slug, entry.key, entry.title,
                               [(parent.key, parent.title) for parent in parents])
    if line_layout:
        return True, [
            (line, '') for paragraph in entry.paragraphs or []
            for line in paragraph.splitlines() if line.strip()
        ]
    return False, entry.couplets or []


def discover_work(exclude_id):
    readable = (TreasuryEntry.objects.filter(kind='work', paragraphs__isnull=False)
                .exclude(paragraphs=[]).select_related('book').order_by('?'))
    previous = None
    for entry in readable.iterator(chunk_size=32):
        line_layout, rows = reading_rows(entry, entry.book, entry_sections(entry))
        if not rows:
            continue
        result = {'entry': entry, 'line_layout': line_layout, 'rows': rows[:4]}
        if str(entry.pk) != exclude_id:
            return result
        previous = result
    return previous


def selection_digest(slug, key, positions, rows):
    identity = json.dumps([slug, key, positions, rows], ensure_ascii=False)
    return hashlib.sha256(identity.encode()).hexdigest()

def work_listing(book, root):
    children = defaultdict(list)
    endings = {}
    for child in book.entries.defer('source_url').iterator():
        child.book = book
        children[child.parent_id].append(child)
        if child.kind == 'work':
            endings[child.pk] = ending_letter(child)
        # The listing only needs the title, hierarchy and ending letter.
        child.paragraphs = None
    root_id = root.pk if root else None
    sections = [child for child in children[root_id] if child.kind == 'section']
    parents = [(item.key, item.title) for item in ([root, *entry_sections(root)] if root else [])]
    stack = [(child, parents) for child in reversed(children[root_id])]
    grouped = defaultdict(list)
    while stack:
        child, parents = stack.pop()
        if child.kind == 'section':
            stack.extend((item, [(child.key, child.title), *parents]) for item in reversed(children[child.pk]))
        else:
            line_layout = is_line_poem(book.slug, child.key, child.title, parents)
            letter = '' if line_layout else endings[child.pk]
            section = parents[0][1] if parents and parents[0][0] != (root.key if root else None) else ''
            grouped[letter].append((child, section))
    groups = [(letter, grouped[letter]) for letter in (*ALPHABET, '') if grouped[letter]]
    return sections, groups, sum(len(works) for _, works in groups)


PERSIAN_LETTERS = str.maketrans('يكأإىؤئةۀ', 'یکاایویهه')


def ending_letter(entry):
    # The imported editions have no rhyme metadata. The first rhyming line
    # provides a browsing cue even when the last couplet has a different ending.
    couplets = entry.couplets
    if not couplets:
        return ''
    ending = unicodedata.normalize('NFKC', couplets[0][1]).translate(PERSIAN_LETTERS)
    return next((char for char in reversed(ending) if char in ALPHABET), '')


@private
@require_POST
def save_selection(request, slug, key):
    entry = get_object_or_404(TreasuryEntry.objects.select_related('book'),
                              book__slug=slug, key=key, kind='work')
    line_layout, rows = reading_rows(entry, entry.book, entry_sections(entry))
    if not rows:
        return failure(request, 'این اثر بیتِ قابل ذخیره ندارد.')
    action = request.POST.get('action', '')
    if action == 'library-all':
        positions = list(range(1, len(rows) + 1))
    elif action.partition(':')[0] in ('favorite', 'unfavorite'):
        action, _, position = action.partition(':')
        positions = [position]
    elif action in ('library', 'memorize'):
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
    if action == 'unfavorite':
        FavoriteVerse.objects.filter(
            owner=request.user, verse__poem__treasury_selection=digest, verse__position=1,
        ).delete()
        return success(request, 'نشان شاه‌بیت برداشته شد.', entry.get_absolute_url(), favorite=False)
    with transaction.atomic():
        poem, created = Poem.objects.get_or_create(
            owner=request.user, treasury_selection=digest, defaults={
                'title': entry.title[:200], 'poet_name': entry.book.author[:160],
                'source_url': entry.source_url, 'line_layout': line_layout,
            },
        )
        if created:
            Verse.objects.bulk_create([
                Verse(poem=poem, position=index, hemistich_1=first, hemistich_2=second)
                for index, (first, second) in enumerate(selected, 1)
            ])
        if poem.archived_at:
            poem.archived_at = None
            poem.save(update_fields=['archived_at', 'updated_at'])
        if action == 'favorite':
            FavoriteVerse.objects.get_or_create(owner=request.user, verse=poem.verses.first())
        elif action == 'memorize':
            MemorizationItem.objects.get_or_create(owner=request.user, poem=poem, scope='full')

    messages = {
        'favorite': ('بیت به شاه‌بیت‌ها افزوده شد.', 'favorites'),
        'memorize': ('به فهرست حفظ افزوده شد.', 'memorize'),
    }
    message, target = messages.get(action, ('در کتابخانه ذخیره شد.', poem.get_absolute_url()))
    return success(request, message, target, **({'favorite': True} if action == 'favorite' else {}))
