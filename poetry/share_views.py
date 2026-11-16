import hashlib
import json
from urllib.parse import urlsplit

from django.contrib.auth.views import redirect_to_login
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from accounts.models import User
from accounts.permissions import action_password_error

from .http import failure, private, success
from .models import Poem, PoemShare, Verse
from .services.editorial import indexed_text, public_picks, verse_url
from .services.public_library import add_review, save_public_work
from .services.share_card import render_card


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def safe_source(value):
    try:
        url = urlsplit(value)
        return value if url.scheme in ('http', 'https') and url.hostname else ''
    except ValueError:
        return ''


def linked_entry(snapshot):
    origin = snapshot.get('origin')
    if not origin:
        return None
    pick = public_picks().select_related('entry__book').filter(
        entry__book__slug=origin['book'], entry__key=origin['key'],
    ).first()
    return pick.entry if pick else None


def reading_context(snapshot):
    entry = linked_entry(snapshot)
    complete_url = ''
    if entry:
        positions = {row[0] for row in snapshot['rows']}
        first = snapshot['origin'].get('positions', {}).get(str(min(positions)))
        complete_url = verse_url(entry, first) if first and first <= len(entry.couplets or []) else entry.get_absolute_url()
    rows = snapshot['rows']
    annotated = [(position, first, second, index > 0 and position > rows[index - 1][0] + 1)
                 for index, (position, first, second) in enumerate(rows)]
    return {'snapshot': snapshot, 'complete_url': complete_url, 'shared_rows': annotated}


def source_data(request, slug=None, key=None, pk=None):
    if pk is not None:
        poem = get_object_or_404(Poem, pk=pk, owner=request.user)
        verses = list(poem.verses.all())
        origin = None
        if poem.treasury_book_slug and poem.treasury_entry_key:
            origin = {'book': poem.treasury_book_slug, 'key': poem.treasury_entry_key,
                      'positions': {str(verse.position): verse.treasury_position for verse in verses if verse.treasury_position}}
        return {
            'title': poem.title or 'شعر بی‌عنوان', 'author': poem.poet_name, 'source': safe_source(poem.source_url),
            'rows': [[verse.position, verse.hemistich_1, verse.hemistich_2] for verse in verses],
            'origin': origin, 'line_layout': poem.line_layout,
        }, f'poem:{pk}', ''
    pick = get_object_or_404(public_picks().select_related('entry__book'), entry__book__slug=slug, entry__key=key)
    entry = pick.entry
    rows = [[position, first, second] for position, (first, second) in enumerate(entry.couplets or [], 1)]
    return {
        'title': entry.title, 'author': entry.book.author, 'source': safe_source(entry.source_url), 'rows': rows,
        'origin': {'book': slug, 'key': key, 'positions': {str(row[0]): row[0] for row in rows}},
        'line_layout': False,
    }, f'treasury:{slug}:{key}', entry.get_absolute_url()


@never_cache
@require_http_methods(['GET', 'POST'])
def compose_share(request, slug=None, key=None, pk=None):
    if not request.user.is_authenticated and (pk is not None or request.method == 'POST'):
        return redirect_to_login(request.get_full_path())
    data, scope, canonical = source_data(request, slug, key, pk)
    note, mode, selection, error = '', 'read', 'all', ''
    chosen = {row[0] for row in data['rows']}
    preselected = request.GET.get('verse', '')
    if request.method == 'GET' and preselected.isascii() and preselected.isdigit() and len(preselected) <= 6:
        chosen = {int(preselected)} & chosen
        if chosen:
            selection = 'selected'
    if request.method == 'POST':
        note = request.POST.get('note', '').replace('\r\n', '\n').replace('\r', '\n').strip()
        mode = request.POST.get('mode', 'read')
        selection = request.POST.get('selection', 'all')
        if selection == 'selected':
            raw_positions = request.POST.getlist('verse')
            if any(not value.isascii() or not value.isdigit() or len(value) > 6 for value in raw_positions):
                raise Http404
            chosen = set(map(int, raw_positions))
        rows = [row for row in data['rows'] if row[0] in chosen]
        if not rows or len(rows) != len(chosen) or selection not in ('all', 'selected') or mode not in ('read', 'practice'):
            error = 'حداقل یک بیت از همین شعر انتخاب کنید.'
        elif len(note) > 280:
            error = 'یادداشت باید حداکثر ۲۸۰ نویسه باشد.'
        elif mode == 'practice' and (len(rows) != 1 or not rows[0][2]):
            error = 'برای تمرین یک بیتِ دارای دو مصرع انتخاب کنید.'
        elif request.POST.get('intent') != 'edit':
            origin = data['origin']
            if origin:
                origin = {**origin, 'positions': {str(position): origin['positions'][str(position)]
                           for position, _, _ in rows if str(position) in origin['positions']}}
            snapshot = {**data, 'rows': rows, 'origin': origin, 'note': note, 'mode': mode}
            stamp = {'owner': request.user.pk, 'scope': scope, 'snapshot': fingerprint(snapshot)}
            canonical_share = canonical and len(rows) == len(data['rows']) and mode == 'read' and not note
            if request.POST.get('intent') == 'confirm':
                try:
                    confirmed = signing.loads(request.POST.get('preview', ''), salt='poem-share', max_age=1800)
                except signing.BadSignature:
                    confirmed = None
                if confirmed == stamp:
                    if canonical_share:
                        return render(request, 'poetry/share_link.html', {
                            'url': request.build_absolute_uri(canonical),
                        })
                    share = PoemShare.objects.create(owner=request.user, snapshot=snapshot)
                    return redirect('share-created', token=share.token)
                error = 'متن یا انتخاب تغییر کرده است. پیش‌نمایش را دوباره بررسی کنید.'
            return render(request, 'poetry/share_preview.html', {
                **reading_context(snapshot), 'selection': selection, 'chosen': sorted(chosen), 'error': error,
                'preview': signing.dumps(stamp, salt='poem-share'), 'canonical_share': canonical_share,
            })
    return render(request, 'poetry/share_form.html', {
        'data': data, 'canonical': request.build_absolute_uri(canonical) if canonical else '',
        'chosen': chosen, 'selection': selection, 'note': note, 'mode': mode, 'error': error,
    }, status=400 if error else 200)


def live_share(token):
    return get_object_or_404(PoemShare, token=token, revoked_at__isnull=True)


@never_cache
@require_http_methods(['GET', 'POST'])
def receive_share(request, token):
    share = live_share(token)
    snapshot = share.snapshot
    revealed = False
    answer_matches = None
    if request.method == 'POST' and snapshot['mode'] == 'practice':
        revealed = True
        answer = request.POST.get('answer', '').strip()[:1000]
        if answer and request.POST.get('intent') == 'check':
            answer_matches = indexed_text(answer)[0] == indexed_text(snapshot['rows'][0][2])[0]
    response = render(request, 'poetry/share_read.html', {
        **reading_context(snapshot), 'share': share, 'revealed': revealed, 'answer_matches': answer_matches,
    })
    response['Referrer-Policy'] = 'no-referrer'
    return response


@private
@require_GET
@never_cache
def created(request, token):
    share = get_object_or_404(PoemShare, token=token, owner=request.user, revoked_at__isnull=True)
    return render(request, 'poetry/share_link.html', {
        'share': share, 'url': request.build_absolute_uri(reverse('shared-poem', args=[token])),
    })


@private
@require_GET
@never_cache
def my_shares(request):
    shares = PoemShare.objects.filter(owner=request.user)
    return render(request, 'poetry/my_shares.html', {'page': Paginator(shares, 20).get_page(request.GET.get('page'))})


@private
@require_POST
def revoke(request, token):
    get_object_or_404(PoemShare, owner=request.user, token=token)
    PoemShare.objects.filter(owner=request.user, token=token, revoked_at__isnull=True).update(revoked_at=timezone.now())
    return redirect('my-shares')


@require_GET
@never_cache
def share_card(request, token):
    share = live_share(token)
    if not 1 <= len(share.snapshot['rows']) <= 2:
        raise Http404
    return render_card(share.snapshot, request.build_absolute_uri(reverse('shared-poem', args=[token])))


@private
@never_cache
@require_http_methods(['GET', 'POST'])
def save_received(request, token):
    share = live_share(token)
    action = request.POST.get('action') if request.method == 'POST' else request.GET.get('action', 'library')
    if action not in ('library', 'memorize'):
        raise Http404
    if request.method == 'GET':
        return render(request, 'poetry/share_save.html', {'share': share, 'action': action})
    if action == 'memorize' and (error := action_password_error(request)):
        return render(request, 'poetry/share_save.html', {'share': share, 'action': action, 'error': error}, status=403)
    try:
        poem = save_snapshot(request.user, share.snapshot, action)
    except ValidationError as error:
        return failure(request, error.messages[0])
    return success(request, 'گزیده ذخیره شد.', 'memorize' if action == 'memorize' else poem.get_absolute_url())


@transaction.atomic
def save_snapshot(owner, snapshot, action):
    User.objects.select_for_update().get(pk=owner.pk)
    entry = linked_entry(snapshot)
    if entry:
        rows = entry.couplets or []
        positions = [snapshot['origin']['positions'].get(str(row[0])) for row in snapshot['rows']]
        if all(position and position <= len(rows) and tuple(row[1:]) == rows[position - 1]
               for position, row in zip(positions, snapshot['rows'])):
            return save_public_work(owner, entry, rows, positions, 'library-all' if action == 'library' else action)
    content = {key: snapshot[key] for key in ('title', 'author', 'source', 'rows', 'line_layout')}
    poem, created = Poem.objects.get_or_create(owner=owner, treasury_selection=fingerprint({'share': content}), defaults={
        'title': content['title'][:200], 'poet_name': content['author'][:160], 'source_url': content['source'],
        'line_layout': content['line_layout'],
    })
    if created:
        Verse.objects.bulk_create([
            Verse(poem=poem, position=index, hemistich_1=row[1], hemistich_2=row[2])
            for index, row in enumerate(content['rows'], 1)
        ])
    if poem.archived_at:
        poem.archived_at = None
        poem.save(update_fields=['archived_at', 'updated_at'])
    if action == 'memorize':
        add_review(owner, poem, list(poem.verses.all()))
    return poem
