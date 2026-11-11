from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from .http import private
from .models import TreasuryBook, TreasuryEntry

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
    ancestors = []
    parent = current.parent if current else None
    while parent:
        if parent.pk not in skipped:
            ancestors.append(parent)
        parent = parent.parent
    entries = book.entries.filter(parent=current or listing_root).select_related('book').defer('paragraphs')
    page = Paginator(entries, 60).get_page(request.GET.get('page'))
    return render(request, 'poetry/treasury_book.html', {
        'book': book, 'entry': current, 'ancestors': reversed(ancestors), 'page': page,
    })
