from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
from memorization.models import MemorizationItem, ReviewLog
from memorization.services.reviews import get_due_items
from .models import Poem, Tag, Verse, FavoriteVerse
from .forms import PoemForm, TagForm
from .http import private, success, failure
from .services.poem_editor import save_poem
from .services.tags import save_tag
from .services.discovery import choose_random_poem


@private
@require_GET
def dashboard(request):
    poems = Poem.objects.filter(owner=request.user, archived_at__isnull=True).prefetch_related('verses', 'tags')
    return render(request, 'dashboard.html', {
        'poem_count': poems.count(), 'recent_poems': poems[:3],
        'item_count': MemorizationItem.objects.filter(owner=request.user).count(),
        'favorite_count': FavoriteVerse.objects.filter(owner=request.user, verse__poem__archived_at__isnull=True).count(),
        'today_count': ReviewLog.objects.filter(item__owner=request.user, reviewed_at__date=timezone.localdate()).count(),
    })


@private
@require_GET
def poem_list(request, slug=None):
    poems = Poem.objects.filter(owner=request.user, archived_at__isnull=request.GET.get('archived') != '1').prefetch_related('verses', 'tags')
    tag = get_object_or_404(Tag, owner=request.user, slug=slug) if slug else None
    if tag:
        poems = poems.filter(tags=tag, archived_at__isnull=True)
    return render(request, 'poetry/list.html', {'page': Paginator(poems, 20).get_page(request.GET.get('page')), 'tag': tag, 'archived': request.GET.get('archived') == '1'})


@private
@require_GET
def poem_detail(request, pk):
    poem = get_object_or_404(Poem.objects.prefetch_related('verses', 'tags'), pk=pk, owner=request.user)
    favorites = set(FavoriteVerse.objects.filter(owner=request.user, verse__poem=poem).values_list('verse_id', flat=True))
    return render(request, 'poetry/detail.html', {'poem': poem, 'favorite_ids': favorites})


@private
def poem_edit(request, pk=None):
    poem = get_object_or_404(Poem, pk=pk, owner=request.user) if pk else None
    initial = {'input_mode': 'structured'}
    form = PoemForm(request.POST or None, owner=request.user, instance=poem, initial=initial)
    if request.method == 'POST' and form.is_valid():
        try:
            saved = save_poem(request.user, form.cleaned_data, form.cleaned_data['verses'], poem)
            messages.success(request, 'شعر در دفتر شما ذخیره شد.')
            return redirect(saved)
        except (ValidationError, IntegrityError) as exc:
            form.add_error(None, ' '.join(exc.messages) if isinstance(exc, ValidationError) else 'تگ تکراری است؛ نام دیگری انتخاب کنید.')
    if request.method == 'POST':
        rows = list(zip(request.POST.getlist('hemistich_1'), request.POST.getlist('hemistich_2')))
    else:
        rows = [(v.hemistich_1, v.hemistich_2) for v in poem.verses.all()] if poem else [('', '')]
    return render(request, 'poetry/form.html', {'form': form, 'poem': poem, 'rows': rows})


@private
@require_POST
def archive(request, pk, restore=False):
    with transaction.atomic():
        poem = get_object_or_404(Poem.objects.select_for_update(), pk=pk, owner=request.user)
        poem.archived_at = None if restore else timezone.now()
        poem.save(update_fields=['archived_at', 'updated_at'])
    return success(request, 'شعر بازگردانی شد.' if restore else 'شعر آرشیو شد.', poem.get_absolute_url())


@private
@require_GET
def tags(request):
    all_tags = Tag.objects.filter(owner=request.user).annotate(poem_count=Count('poems', filter=Q(poems__archived_at__isnull=True)))
    return render(request, 'poetry/tags.html', {'tags': all_tags, 'form': TagForm()})


@private
@require_POST
def tag_change(request, pk=None, action='create'):
    tag = get_object_or_404(Tag, pk=pk, owner=request.user) if pk else None
    if action == 'delete':
        if request.POST.get('confirm') != 'yes':
            return render(request, 'confirm.html', {'label': f'حذف تگ «{tag.name}»', 'explanation': 'شعرها باقی می‌مانند؛ فقط تگ و ارتباط آن حذف می‌شود.'})
        tag.delete()
        return success(request, 'تگ حذف شد.', 'tags')
    form = TagForm(request.POST)
    if not form.is_valid():
        return failure(request, 'نام تگ معتبر نیست.', errors=form.errors)
    try:
        tag = save_tag(request.user, form.cleaned_data['name'], tag)
    except (ValidationError, IntegrityError):
        return failure(request, 'نام تگ تکراری یا نامعتبر است.', status=409)
    return success(request, 'تگ ذخیره شد.', 'tags', tag={'id': tag.pk, 'name': tag.name, 'url': tag.get_absolute_url()})


@private
@require_POST
def assign_tags(request, pk):
    poem = get_object_or_404(Poem, pk=pk, owner=request.user)
    ids = request.POST.getlist('tags')
    if not all(x.isdigit() for x in ids):
        return failure(request, 'تگ معتبر نیست.')
    selected = Tag.objects.filter(owner=request.user, pk__in=ids)
    if selected.count() != len(set(ids)):
        return failure(request, 'تگ معتبر نیست.')
    poem.tags.set(selected)
    return success(request, 'تگ‌ها ذخیره شدند.', poem.get_absolute_url())


@private
@require_POST
def favorite(request, pk, remove=False):
    verse = get_object_or_404(Verse.objects.select_related('poem'), pk=pk, poem__owner=request.user)
    if remove:
        FavoriteVerse.objects.filter(owner=request.user, verse=verse).delete()
    else:
        FavoriteVerse.objects.get_or_create(owner=request.user, verse=verse)
    return success(request, 'نشان شاه‌بیت برداشته شد.' if remove else 'به شاه‌بیت‌ها افزوده شد.', verse.poem.get_absolute_url(), favorite=not remove)


@private
@require_GET
def favorites(request):
    rows = FavoriteVerse.objects.filter(owner=request.user, verse__poem__archived_at__isnull=True).select_related('verse__poem').prefetch_related('verse__poem__tags')
    return render(request, 'poetry/favorites.html', {'page': Paginator(rows, 20).get_page(request.GET.get('page'))})


@private
@require_GET
def discover(request, api=False):
    poem = choose_random_poem(request.user, request.GET.get('exclude_id'))
    if api:
        data = None if poem is None else {'id': poem.pk, 'title': poem.display_title, 'poet_name': poem.poet_name,
                'detail_url': poem.get_absolute_url(), 'verses': list(poem.verses.values('id', 'position', 'hemistich_1', 'hemistich_2')),
                'tags': [{'name': tag.name, 'url': tag.get_absolute_url()} for tag in poem.tags.all()]}
        return JsonResponse({'ok': True, 'poem': data})
    return render(request, 'poetry/discover.html', {'poem': poem, 'only_one': Poem.objects.filter(owner=request.user, archived_at__isnull=True).count() == 1})
