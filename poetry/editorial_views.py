import secrets

from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET

from .models import TreasurySet, TreasuryTopic
from .services.editorial import highlight, match_rank, public_picks, query_terms, quote_row, verse_url


def showcase(request, *, explore=False):
    picks = public_picks()
    prefix = 'public_' if explore else ''
    poet = request.GET.get(prefix + 'poet', '')[:120]
    topic = request.GET.get(prefix + 'topic', '')[:50]
    matched = picks
    if poet:
        matched = matched.filter(entry__book__slug=poet)
    if topic:
        matched = matched.filter(topics__slug=topic)
    if request.GET.get(prefix + 'turn') == '1':
        ids = list(matched.values_list('entry_id', flat=True))
        if ids:
            pick = matched.select_related('entry__book').get(entry_id=secrets.choice(ids))
            return redirect(pick.entry.get_absolute_url())
    cards = matched.filter(featured=True) if explore and not (poet or topic) else matched
    cards = cards.select_related('entry__book').defer('entry__search_body').order_by('entry__book__author', 'pk')
    page = Paginator(cards, 12).get_page(request.GET.get('pick_page'))
    return {
        'explore_showcase': explore,
        'poet_parameter': prefix + 'poet',
        'topic_parameter': prefix + 'topic',
        'picks': [(pick, quote_row(pick, pick.sample_position)) for pick in page],
        'pick_page': page,
        'public_poet': poet,
        'public_topic': topic,
        'public_poets': picks.order_by('entry__book__author').values_list('entry__book__slug', 'entry__book__author').distinct(),
        'public_topics': TreasuryTopic.objects.filter(treasurypick__in=picks).distinct(),
        'public_collections': TreasurySet.objects.filter(published=True) if explore else (),
    }


@require_GET
def verse_trace(request):
    query = request.GET.get('q', '').strip()[:120]
    words = query_terms(query)
    results = []
    if words:
        picks = public_picks().select_related('entry__book').defer('entry__search_body').order_by('entry__book__author', 'pk')
        for pick in picks:
            entry = pick.entry
            best = 0
            for position, (first, second) in enumerate(entry.couplets or [], 1):
                rank = max(match_rank(first, words), match_rank(second, words), match_rank(first + ' ' + second, words))
                if rank:
                    best = max(best, rank)
                    results.append((rank + 3, entry, position, first, second))
            if not best and (rank := max(match_rank(entry.title, words), match_rank(entry.book.author, words))):
                results.append((rank, entry, None, '', ''))
    results.sort(key=lambda result: -result[0])
    page = Paginator(results, 18).get_page(request.GET.get('page'))
    page.object_list = [
        {'entry': entry, 'position': position, 'first': highlight(first, words), 'second': highlight(second, words),
         'url': verse_url(entry, position) if position else entry.get_absolute_url()}
        for _, entry, position, first, second in page
    ]
    return render(request, 'poetry/verse_trace.html', {'query': query, 'page': page})


@require_GET
def literary_collection(request, slug):
    collection = get_object_or_404(TreasurySet, slug=slug, published=True)
    quotes = collection.quotes.filter(pick__in=public_picks()).select_related('pick__entry__book')
    rows = [
        (quote, row, verse_url(quote.pick.entry, quote.verse))
        for quote in quotes if (row := quote_row(quote.pick, quote.verse))
    ]
    return render(request, 'poetry/literary_collection.html', {'collection': collection, 'rows': rows})
