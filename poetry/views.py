from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, OuterRef, Q, Subquery
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST, require_GET, require_http_methods
from accounts.permissions import action_password_error
from memorization.models import MemorizationItem, ReviewLog
from memorization.views import study_context
from .models import Poem, PoemEditRequest, Tag, TreasuryEntry, Verse, FavoriteVerse
from .forms import PoemForm, TagForm
from .http import private, success, failure, wants_json
from .services.poem_editor import save_poem
from .services.edit_requests import edit_changes, submit_edit
from .services.tags import merge_tags, save_tag
from .services.search import search_field, search_text
from .services.discovery import choose_random_poem
from .treasury_views import discover_work, entry_sections, reading_rows


@private
@require_GET
def dashboard(request):
    poems = Poem.objects.filter(owner=request.user, archived_at__isnull=True).prefetch_related('verses', 'tags')
    return render(request, 'dashboard.html', {
        **study_context(request.user),
        'poem_count': poems.count(), 'recent_poems': poems[:3],
        'item_count': MemorizationItem.objects.filter(owner=request.user).count(),
        'favorite_count': FavoriteVerse.objects.filter(owner=request.user, verse__poem__archived_at__isnull=True).count(),
        'today_count': ReviewLog.objects.filter(item__owner=request.user, reviewed_at__date=timezone.localdate()).count(),
    })


@private
@require_GET
def poem_list(request, slug=None):
    tag = get_object_or_404(Tag, owner=request.user, slug=slug) if slug else None
    archived = request.GET.get('archived') == '1'
    poet = request.GET.get('poet', '')
    poems = Poem.objects.filter(owner=request.user, archived_at__isnull=not archived).prefetch_related('verses', 'tags')
    if tag:
        poems = poems.filter(tags=tag)
    if poet:
        poems = poems.filter(poet_name=poet)
    topic_choices = Tag.objects.filter(owner=request.user)
    active_topics = list(topic_choices.filter(slug__in=request.GET.getlist('topic')))
    if active_topics:
        tagged = Poem.tags.through.objects.filter(tag_id__in=[topic.pk for topic in active_topics]).values('poem_id')
        matching = tagged.annotate(matches=Count('tag_id')).filter(matches=len(active_topics))
        poems = poems.filter(pk__in=matching.values('poem_id'))
    query = request.GET.get('q', '').strip()[:120]
    term = search_text(query)
    if term:
        matches = Verse.objects.filter(poem_id=OuterRef('pk')).alias(
            first=search_field('hemistich_1'), second=search_field('hemistich_2'),
        ).filter(Q(first__icontains=term) | Q(second__icontains=term))
        poems = poems.annotate(match_id=Subquery(matches.values('pk')[:1])).alias(
            search_title=search_field('title'), search_poet=search_field('poet_name'),
        ).filter(Q(search_title__icontains=term) | Q(search_poet__icontains=term) | Q(match_id__isnull=False))
    sort = request.GET.get('sort', '')
    orders = {'title': ('title', 'pk'), 'poet': ('poet_name', 'pk'), 'oldest': ('created_at', 'pk')}
    if sort in orders:
        poems = poems.order_by(*orders[sort])
    return render(request, 'poetry/list.html', {
        'page': Paginator(poems, 20).get_page(request.GET.get('page')),
        'tag': tag, 'archived': archived, 'poet': poet, 'query': query, 'sort': sort,
        'active_topics': active_topics, 'active_topic_slugs': {topic.slug for topic in active_topics},
        'topic_choices': topic_choices,
    })


@private
@require_GET
def poets(request):
    groups = (Poem.objects.filter(owner=request.user, archived_at__isnull=True)
              .values('poet_name').annotate(poem_count=Count('pk')).order_by('poet_name'))
    return render(request, 'poetry/poets.html', {'page': Paginator(groups, 24).get_page(request.GET.get('page'))})


@private
@require_GET
def poem_detail(request, pk):
    poem = get_object_or_404(Poem.objects.prefetch_related('verses', 'tags'), pk=pk, owner=request.user)
    favorites = set(FavoriteVerse.objects.filter(owner=request.user, verse__poem=poem).values_list('verse_id', flat=True))
    origin = request.GET.get('from', '')
    library_back = reverse('poems')
    if origin.startswith(('/poems/', '/topics/view/')) and url_has_allowed_host_and_scheme(origin, allowed_hosts=set()):
        library_back = origin
    origin_entry = None
    if poem.treasury_book_slug and poem.treasury_entry_key:
        origin_entry = TreasuryEntry.objects.select_related('book').defer('paragraphs', 'search_body').filter(
            book__slug=poem.treasury_book_slug, key=poem.treasury_entry_key, kind='work',
        ).first()
    edition_changed = bool(origin_entry and poem.treasury_edition != origin_entry.book.dataset_digest)
    comparison = None
    if edition_changed and request.GET.get('compare') == '1':
        _, reference = reading_rows(origin_entry, origin_entry.book, entry_sections(origin_entry))
        comparison = []
        for verse in poem.verses.all():
            position = verse.treasury_position
            if not position:
                continue
            saved = (verse.hemistich_1, verse.hemistich_2)
            current = reference[position - 1] if position <= len(reference) else None
            if saved != current:
                comparison.append((position, saved, current))
    return render(request, 'poetry/detail.html', {
        'library_back': library_back, 'origin_entry': origin_entry,
        'edition_changed': edition_changed, 'origin_comparison': comparison,
        'poem': poem, 'favorite_ids': favorites,
        'study_cards': poem.items.select_related('start_verse', 'end_verse'),
        'has_full_card': poem.items.filter(scope='full').exists(),
        'edit_request': poem.edit_requests.order_by('-created_at', '-pk').first(),
    })


@private
@require_http_methods(['GET', 'POST'])
def poem_edit(request, pk=None):
    poem = get_object_or_404(Poem, pk=pk, owner=request.user) if pk else None
    if poem and request.method == 'GET' and poem.edit_requests.filter(status='pending').exists():
        messages.info(request, 'درخواست قبلی هنوز در انتظار بررسی است.')
        return redirect(poem)
    initial = {'input_mode': 'structured' if poem else 'lines'}
    retry = request.GET.get('retry', '')
    rejected = None
    if poem and request.method == 'GET' and retry.isascii() and retry.isdigit() and len(retry) <= 18:
        rejected = get_object_or_404(poem.edit_requests, pk=retry, status='rejected')
        initial.update({field: rejected.payload.get(field, '') for field in ('title', 'poet_name', 'source_url', 'notes', 'new_tag')})
        initial['tags'] = Tag.objects.filter(owner=request.user, pk__in=rejected.payload.get('tags', []))
        initial['line_layout'] = rejected.payload.get('line_layout', poem.line_layout)
    form = PoemForm(request.POST or None, owner=request.user, instance=poem, initial=initial)
    if request.method == 'POST' and form.is_valid():
        try:
            if poem:
                revision = request.POST.get('revision')
                if revision and revision != poem.updated_at.isoformat(timespec='microseconds'):
                    raise ValidationError('شعر پس از بازکردن فرم تغییر کرده است. نسخهٔ تازه را در صفحهٔ شعر ببینید.')
                if error := action_password_error(request):
                    raise ValidationError(error)
                submit_edit(poem, request.user, form.cleaned_data, form.cleaned_data['verses'])
                messages.success(request, 'درخواست ویرایش برای بررسی مدیر فرستاده شد.', extra_tags=f'poem-draft-{request.user.pk}-{poem.pk}')
                return redirect(poem)
            saved = save_poem(request.user, form.cleaned_data, form.cleaned_data['verses'])
            messages.success(request, 'شعر در دفتر شما ذخیره شد.', extra_tags=f'poem-draft-{request.user.pk}-new')
            return redirect(saved)
        except (ValidationError, IntegrityError) as exc:
            form.add_error(None, ' '.join(exc.messages) if isinstance(exc, ValidationError) else 'ذخیره ممکن نشد. دوباره تلاش کنید.')
    if request.method == 'POST':
        rows = list(zip(request.POST.getlist('hemistich_1'), request.POST.getlist('hemistich_2')))
    elif rejected:
        rows = rejected.payload.get('verses', [])
    else:
        rows = [(v.hemistich_1, v.hemistich_2) for v in poem.verses.all()] if poem else [('', '')]
    return render(request, 'poetry/form.html', {'form': form, 'poem': poem, 'rows': rows or [('', '')],
                                                      'original_count': poem.verses.count() if poem else 0,
                                                      'revision': (request.POST.get('revision') or poem.updated_at.isoformat(timespec='microseconds')) if poem else '',
                                                      'retry_request': rejected})


@private
@require_POST
def archive(request, pk, restore=False):
    with transaction.atomic():
        poem = get_object_or_404(Poem.objects.select_for_update(), pk=pk, owner=request.user)
        if not restore and (error := action_password_error(request, required=True)):
            messages.error(request, error)
            return redirect(poem)
        poem.archived_at = None if restore else timezone.now()
        poem.save(update_fields=['archived_at', 'updated_at'])
    return success(request, 'شعر بازگردانی شد.' if restore else 'شعر آرشیو شد.', poem.get_absolute_url())


@private
@require_GET
def edit_history(request, pk=None):
    edits = PoemEditRequest.objects.filter(poem__owner=request.user).select_related('poem').order_by('-created_at', '-pk')
    if pk is None:
        return render(request, 'poetry/edit_history.html', {'page': Paginator(edits, 20).get_page(request.GET.get('page'))})
    edit = get_object_or_404(edits, pk=pk)
    rows, has_original = edit_changes(edit)
    return render(request, 'poetry/edit_history.html', {'edit': edit, 'rows': rows, 'has_original': has_original})


def topics_page(request, form=None, editing=None, *, status=200):
    all_tags = Tag.objects.filter(owner=request.user).annotate(
        poem_count=Count('poems', filter=Q(poems__archived_at__isnull=True)),
    )
    return render(request, 'poetry/tags.html', {
        'tags': all_tags, 'form': form if editing is None and form is not None else TagForm(),
        'editing': editing, 'edit_form': form if editing else None,
    }, status=status)


@private
@require_GET
def tags(request):
    return topics_page(request)


@private
@require_POST
def tag_change(request, pk=None, action='create'):
    tag = get_object_or_404(Tag, pk=pk, owner=request.user) if pk else None
    if action == 'delete':
        if request.POST.get('confirm') != 'yes':
            return render(request, 'confirm.html', {'label': f'حذف موضوع «{tag.name}»',
                          'explanation': 'شعرها باقی می‌مانند؛ موضوع و ارتباط آن حذف می‌شود.', 'cancel_url': reverse('tags')})
        tag.delete()
        return success(request, 'موضوع حذف شد.', 'tags')
    form = TagForm(request.POST, auto_id=f'id_tag_{pk}_%s' if pk else 'id_%s')
    status = 400
    if form.is_valid():
        try:
            tag = save_tag(request.user, form.cleaned_data['name'], tag)
        except (ValidationError, IntegrityError):
            form.add_error('name', 'موضوعی با این نام وجود دارد یا نام معتبر نیست.')
            status = 409
        else:
            return success(request, 'موضوع ذخیره شد.', 'tags', tag={'id': tag.pk, 'name': tag.name, 'url': tag.get_absolute_url()})
    if wants_json(request):
        return failure(request, 'نام موضوع تکراری یا نامعتبر است.', errors=form.errors, status=status)
    return topics_page(request, form, tag, status=status)


@private
@require_POST
def tag_merge(request):
    source = request.POST.get('source', '')
    target = request.POST.get('target', '')
    if not all(value.isascii() and value.isdigit() and len(value) <= 18 for value in (source, target)):
        messages.error(request, 'دو موضوع را انتخاب کنید.')
    else:
        try:
            merge_tags(request.user, int(source), int(target))
        except ValidationError as error:
            messages.error(request, error.messages[0])
        else:
            messages.success(request, 'موضوع‌ها ادغام شدند.')
    return redirect('tags')


@private
@require_POST
def assign_tags(request, pk):
    poem = get_object_or_404(Poem, pk=pk, owner=request.user)
    ids = request.POST.getlist('tags')
    if not all(x.isdigit() for x in ids):
        return failure(request, 'موضوع معتبر نیست.')
    selected = Tag.objects.filter(owner=request.user, pk__in=ids)
    if selected.count() != len(set(ids)):
        return failure(request, 'موضوع معتبر نیست.')
    if error := action_password_error(request):
        return failure(request, error, status=403)
    data = {name: getattr(poem, name) for name in ('title', 'poet_name', 'source_url', 'notes')}
    data['tags'] = selected
    try:
        submit_edit(poem, request.user, data, list(poem.verses.values_list('hemistich_1', 'hemistich_2')))
    except ValidationError as exc:
        return failure(request, ' '.join(exc.messages), status=409)
    return success(request, 'درخواست تغییر موضوع‌ها برای مدیر فرستاده شد.', poem.get_absolute_url())


@private
@require_POST
def favorite(request, pk, remove=False):
    verse = get_object_or_404(Verse.objects.select_related('poem'), pk=pk, poem__owner=request.user)
    if remove:
        FavoriteVerse.objects.filter(owner=request.user, verse=verse).delete()
    else:
        FavoriteVerse.objects.get_or_create(owner=request.user, verse=verse)
    target = verse.poem.get_absolute_url()
    if remove and request.POST.get('return_to_favorites'):
        page = request.POST.get('page', '1')
        target = reverse('favorites')
        if page.isascii() and page.isdigit() and len(page) <= 8:
            target += f'?page={page}'
    return success(request, 'نشان شاه‌بیت برداشته شد.' if remove else 'به شاه‌بیت‌ها افزوده شد.', target, favorite=not remove)


@private
@require_GET
def favorites(request):
    rows = FavoriteVerse.objects.filter(owner=request.user, verse__poem__archived_at__isnull=True).select_related('verse__poem').prefetch_related('verse__poem__tags')
    return render(request, 'poetry/favorites.html', {'page': Paginator(rows, 20).get_page(request.GET.get('page'))})


@private
@require_GET
def discover(request, api=False):
    params = request.GET
    poet = params.get('poet', '').strip()[:120]
    topic = params.get('topic', '')[:90]
    length = params.get('length', '')
    if length not in ('short', 'long'):
        length = ''
    if api:
        poem = choose_random_poem(request.user, params.get('exclude_id'), poet=poet, topic=topic, length=length)
        data = None if poem is None else {'id': poem.pk, 'title': poem.display_title, 'poet_name': poem.poet_name,
                'detail_url': poem.get_absolute_url(), 'line_layout': poem.line_layout, 'verses': list(poem.verses.values('id', 'position', 'hemistich_1', 'hemistich_2')),
                'tags': [{'name': tag.name, 'url': tag.get_absolute_url()} for tag in poem.tags.all()]}
        return JsonResponse({'ok': True, 'poem': data})
    source = params.get('source', '')
    if source not in ('library', 'treasury'):
        source = 'both'
    personal_history = request.session.get('discover_library', [])
    treasury_history = request.session.get('discover_treasury', [])
    poem = choose_random_poem(request.user, params.get('exclude_id'), poet=poet, topic=topic, length=length,
                              recent=personal_history, keep_id=params.get('keep_poem')) if source != 'treasury' else None
    treasury = discover_work(params.get('treasury_exclude'), poet=poet, length=length, recent=treasury_history,
                             keep_id=params.get('keep_work')) if source != 'library' else None
    if poem:
        request.session['discover_library'] = [poem.pk, *[pk for pk in personal_history if pk != poem.pk]][:8]
    if treasury:
        pick_id = treasury['entry'].pk
        request.session['discover_treasury'] = [pick_id, *[pk for pk in treasury_history if pk != pick_id]][:8]
    return render(request, 'poetry/discover.html', {
        'poem': poem, 'treasury_pick': treasury, 'source': source, 'poet': poet, 'topic': topic, 'length': length,
        'topics': Tag.objects.filter(owner=request.user), 'filtered': bool(poet or topic or length),
    })
