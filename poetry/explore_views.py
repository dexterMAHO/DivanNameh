import hashlib
import secrets
from django.db.models import Q

from django import forms
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Exists, OuterRef
from django.http import HttpResponse
from accounts.models import ProfilePhoto
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.contrib import messages

from accounts.permissions import action_password_error
from .http import private
from .models import ExplorePost, ExploreLike, ExploreSave, ExploreView, Poem, Verse
from .services.poem_editor import parse_verses, validate_verses


class PostForm(forms.ModelForm):
    input_mode = forms.ChoiceField(label='روش ورود متن', required=False, choices=[('lines','هر خط یک بیت؛ جداکنندهٔ |'), ('pairs','هر دو خط یک بیت'), ('structured','ورود بیت به بیت')])
    text = forms.CharField(label='متن شعر', required=False, max_length=100000, widget=forms.Textarea(attrs={'rows': 10}), help_text='هر خط یک بیت؛ دو مصرع را با | جدا کنید. برای شعر نو هر خط یک سطر است.')
    action_password = forms.CharField(label='رمز عملیات (اختیاری)', max_length=128, required=False, widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}), help_text='بدون رمز معتبر، پست برای تأیید مدیر ارسال می‌شود.')

    class Meta:
        model = ExplorePost
        fields = ['title', 'poet_name', 'line_layout']
        labels = {'title': 'عنوان شعر', 'poet_name': 'نام شاعر', 'line_layout': 'شعر نو / سطرهای آزاد'}

    def clean(self):
        data = super().clean()
        mode = data.get('input_mode') or 'lines'
        try:
            if mode == 'structured':
                firsts = self.data.getlist('hemistich_1')
                seconds = self.data.getlist('hemistich_2')
                if len(firsts) != len(seconds):
                    raise ValidationError('مصرع‌های هر ردیف را کامل کنید.')
                data['rows'] = validate_verses([(first, '' if data.get('line_layout') else second) for first, second in zip(firsts, seconds)])
            else:
                data['rows'] = parse_verses(data.get('text', ''), mode, line_layout=data.get('line_layout', False))
        except ValidationError as error:
            self.add_error(None, error)
        return data


@require_GET
def index(request):
    posts = ExplorePost.objects.filter(status='published').select_related('author').annotate(
        author_has_photo=Exists(ProfilePhoto.objects.filter(user_id=OuterRef('author_id'))),
        like_count=Count('likes', distinct=True), save_count=Count('saves', distinct=True), view_count=Count('views', distinct=True))
    query = request.GET.get('q', '').strip()[:120]
    if query:
        from django.db.models import Q
        posts = posts.filter(Q(title__icontains=query) | Q(poet_name__icontains=query))
    sort = request.GET.get('sort', 'newest')
    ordering = {'views': '-view_count', 'likes': '-like_count', 'saves': '-save_count', 'newest': '-created_at'}
    if sort not in ordering:
        sort = 'newest'
    posts = posts.order_by(ordering[sort], '-pk')
    page = Paginator(posts, 18).get_page(request.GET.get('page'))
    context = {'post_page': page, 'feed_sort': sort, 'feed_query': query}
    context['liked_ids'] = set(ExploreLike.objects.filter(user=request.user, post_id__in=[post.pk for post in page]).values_list('post_id', flat=True)) if request.user.is_authenticated else set()
    context['own_posts'] = ExplorePost.objects.filter(author=request.user).only('pk', 'title', 'status') if request.user.is_authenticated else ()
    context['pending_posts'] = ExplorePost.objects.filter(author=request.user, status='pending').count() if request.user.is_authenticated else 0
    return render(request, 'poetry/explore.html', context)


@private
@require_http_methods(['GET', 'POST'])
def publish(request, pk=None):
    post = get_object_or_404(ExplorePost, pk=pk, author=request.user) if pk else None
    initial = {'input_mode': 'lines'}
    if post:
        initial['text'] = '\n'.join(first + (' | ' + second if second else '') for first, second in post.rows)
    form = PostForm(request.POST if request.method == 'POST' else None, instance=post, initial=initial)
    if request.method == 'POST' and form.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        post.rows = form.cleaned_data['rows']
        verified = bool(request.user.action_password) and not action_password_error(request)
        post.status = 'published' if verified or request.user.is_superuser else 'pending'
        post.save()
        messages.success(request, 'شعر منتشر شد.' if post.status == 'published' else 'شعر برای تأیید مدیر ارسال شد.')
        return redirect('explore')
    rows = post.rows if post else [('', '')]
    if request.method == 'POST' and request.POST.get('input_mode') == 'structured':
        rows = list(zip(request.POST.getlist('hemistich_1'), request.POST.getlist('hemistich_2'))) or [('', '')]
    return render(request, 'poetry/explore_publish.html', {'form': form, 'post': post, 'rows': rows})


@require_GET
def detail(request, pk):
    visible = Q(status='published')
    if request.user.is_authenticated:
        visible |= Q(author=request.user)
    post = get_object_or_404(ExplorePost.objects.select_related('author').filter(visible), pk=pk)
    if not request.session.get('explore_visitor'):
        request.session['explore_visitor'] = secrets.token_hex(24)
    identity = f'user:{request.user.pk}' if request.user.is_authenticated else request.session['explore_visitor']
    visitor = hashlib.sha256(identity.encode()).hexdigest()
    if post.status == 'published':
        ExploreView.objects.get_or_create(post=post, visitor=visitor)
    liked = request.user.is_authenticated and post.likes.filter(user=request.user).exists()
    return render(request, 'poetry/explore_post.html', {'post': post, 'liked': liked, 'author_has_photo': ProfilePhoto.objects.filter(user=post.author).exists()})


@private
@require_POST
@transaction.atomic
def action(request, pk):
    # Serialize repeat saves/likes for this post, including simultaneous clicks.
    post = get_object_or_404(ExplorePost.objects.select_for_update(), pk=pk, status='published')
    intent = request.POST.get('intent')
    if intent == 'like':
        ExploreLike.objects.get_or_create(post=post, user=request.user)
    elif intent == 'unlike':
        ExploreLike.objects.filter(post=post, user=request.user).delete()
    elif intent == 'save':
        saved, _ = ExploreSave.objects.get_or_create(post=post, user=request.user)
        if saved.poem_id is None:
            poem = Poem.objects.create(owner=request.user, title=post.title, poet_name=post.poet_name, line_layout=post.line_layout)
            Verse.objects.bulk_create([Verse(poem=poem, position=i, hemistich_1=row[0], hemistich_2=row[1]) for i, row in enumerate(post.rows, 1)])
            saved.poem = poem
            saved.save(update_fields=['poem'])
        else:
            poem = saved.poem
            if poem.archived_at:
                poem.archived_at = None
                poem.save(update_fields=['archived_at', 'updated_at'])
        messages.success(request, 'شعر به خانه اشعار اضافه شد.')
        return redirect(poem.get_absolute_url())
    else:
        from .http import failure
        return failure(request, 'عملیات معتبر نیست.')
    return redirect(post.get_absolute_url())


@require_GET
def author_photo(request, pk):
    photos = ProfilePhoto.objects.filter(user_id=pk)
    if not request.user.is_authenticated or request.user.pk != pk:
        photos = photos.filter(user__explore_posts__status='published').distinct()
    photo = get_object_or_404(photos)
    response = HttpResponse(bytes(photo.image), content_type='image/webp')
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
