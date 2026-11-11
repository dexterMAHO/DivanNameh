from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from .http import private
from .models import TreasuryBook, TreasuryEntry


@private
@require_GET
def index(request):
    query = request.GET.get('q', '').strip()[:120]
    books = TreasuryBook.objects.all()
    if query:
        books = books.filter(author__icontains=query)
    page = Paginator(books, 36).get_page(request.GET.get('page'))
    return render(request, 'poetry/treasury.html', {'page': page, 'query': query})


@private
@require_GET
def book_detail(request, slug, key=None):
    book = get_object_or_404(TreasuryBook, slug=slug)
    current = get_object_or_404(TreasuryEntry, book=book, key=key) if key else None
    ancestors = []
    parent = current.parent if current else None
    while parent:
        ancestors.append(parent)
        parent = parent.parent
    entries = book.entries.filter(parent=current).select_related('book').defer('paragraphs')
    page = Paginator(entries, 60).get_page(request.GET.get('page'))
    return render(request, 'poetry/treasury_book.html', {
        'book': book, 'entry': current, 'ancestors': reversed(ancestors), 'page': page,
    })
