from django import forms
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, Max
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .http import private
from .models import Collection, CollectionItem, FavoriteVerse, Poem
from .services.tags import normalize_tag_name


class CollectionForm(forms.Form):
    name = forms.CharField(label='نام مجموعه', max_length=100)


@private
@require_http_methods(['GET', 'POST'])
def collections(request):
    form = CollectionForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        name = form.cleaned_data['name']
        try:
            collection = Collection.objects.create(owner=request.user, name=name, normalized_name=normalize_tag_name(name))
        except IntegrityError:
            form.add_error('name', 'مجموعه‌ای با این نام دارید.')
        else:
            return redirect(collection)
    rows = request.user.collections.annotate(item_count=Count('items'))
    return render(request, 'poetry/collections.html', {'collections': rows, 'form': form})


@private
@require_http_methods(['GET', 'POST'])
def collection_detail(request, pk):
    collection = get_object_or_404(request.user.collections, pk=pk)
    error = None
    if request.method == 'POST':
        with transaction.atomic():
            collection = request.user.collections.select_for_update().get(pk=pk)
            action = request.POST.get('action', '')
            if action == 'add':
                poem_ids = request.POST.getlist('poem')
                favorite_ids = request.POST.getlist('favorite')
                if not all(value.isascii() and value.isdigit() and len(value) <= 18 for value in [*poem_ids, *favorite_ids]):
                    error = 'انتخاب معتبر نیست.'
                else:
                    poems = list(Poem.objects.filter(owner=request.user, pk__in=poem_ids).exclude(
                        collectionitem__collection=collection).values_list('pk', flat=True))
                    favorites = list(FavoriteVerse.objects.filter(owner=request.user, pk__in=favorite_ids).exclude(
                        collectionitem__collection=collection).values_list('pk', flat=True))
                    last = collection.items.aggregate(last=Max('position'))['last'] or 0
                    additions = [{'poem_id': poem} for poem in poems] + [{'favorite_id': favorite} for favorite in favorites]
                    CollectionItem.objects.bulk_create([
                        CollectionItem(collection=collection, position=last + index, **target)
                        for index, target in enumerate(additions, 1)
                    ])
                    messages.success(request, 'مجموعه به‌روز شد.')
            elif action in ('up', 'down', 'remove'):
                item_id = request.POST.get('item', '')
                if not item_id.isascii() or not item_id.isdigit() or len(item_id) > 18:
                    error = 'ردیف معتبر نیست.'
                else:
                    item = get_object_or_404(collection.items, pk=item_id)
                    if action == 'remove':
                        item.delete()
                    else:
                        swap_items(collection, item, up=action == 'up')
            else:
                error = 'عملیات معتبر نیست.'
        if not error:
            return redirect(collection.get_absolute_url() + '#collection-items')
    items = collection.items.select_related('poem', 'favorite__verse__poem').prefetch_related('poem__verses')
    poems = Poem.objects.filter(owner=request.user, archived_at__isnull=True).exclude(
        collectionitem__collection=collection).prefetch_related('verses')
    favorites = FavoriteVerse.objects.filter(owner=request.user, verse__poem__archived_at__isnull=True).exclude(
        collectionitem__collection=collection).select_related('verse__poem')
    return render(request, 'poetry/collection_detail.html', {
        'collection': collection, 'items': items, 'error': error,
        'choices': Paginator(poems, 24).get_page(request.GET.get('page')),
        'favorite_choices': Paginator(favorites, 24).get_page(request.GET.get('favorite_page')),
    })


def swap_items(collection, item, *, up):
    if up:
        neighbor = collection.items.filter(position__lt=item.position).order_by('-position').first()
    else:
        neighbor = collection.items.filter(position__gt=item.position).first()
    if neighbor is None:
        return
    position = neighbor.position
    collection.items.filter(pk=neighbor.pk).update(position=0)
    collection.items.filter(pk=item.pk).update(position=position)
    collection.items.filter(pk=neighbor.pk).update(position=item.position)
