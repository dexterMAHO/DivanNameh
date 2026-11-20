import hashlib
import secrets

from django import forms
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.contrib import messages

from accounts.permissions import action_password_error
from .editorial_views import showcase
from .http import private
from .models import ExplorePost, ExploreLike, ExploreSave, ExploreView, Poem, Verse
from .services.poem_editor import parse_verses


class PostForm(forms.ModelForm):
    text = forms.CharField(label='متن شعر', max_length=100000, widget=forms.Textarea(attrs={'rows': 10}), help_text='هر خط یک بیت؛ دو مصرع را با | جدا کنید. برای شعر نو هر خط یک سطر است.')
    action_password = forms.CharField(label='رمز عملیات (اختیاری)', max_length=128, required=False, widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}), help_text='بدون رمز معتبر، پست برای تأیید مدیر ارسال می‌شود.')

    class Meta:
        model = ExplorePost
        fields = ['title', 'poet_name', 'line_layout']
        labels = {'title': 'عنوان شعر', 'poet_name': 'نام شاعر', 'line_layout': 'شعر نو / سطرهای آزاد'}

    def clean(self):
        data = super().clean()
        if data.get('text'):
            try:
                data['rows'] = parse_verses(data['text'], 'lines', line_layout=data.get('line_layout', False))
            except ValidationError as error:
                self.add_error('text', error)
        return data


@require_GET
def index(request):
    posts = ExplorePost.objects.filter(status='published').select_related('author').annotate(
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
    context = showcase(request, explore=True)
    context.update({'post_page': Paginator(posts, 18).get_page(request.GET.get('page')), 'feed_sort': sort, 'feed_query': query})
    context['pending_posts'] = ExplorePost.objects.filter(author=request.user, status='pending').count() if request.user.is_authenticated else 0
    return render(request, 'poetry/explore.html', context)


@private
@require_http_methods(['GET', 'POST'])
def publish(request):
    form = PostForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        post.rows = form.cleaned_data['rows']
        verified = bool(request.user.action_password) and not action_password_error(request)
        post.status = 'published' if verified or request.user.is_superuser else 'pending'
        post.save()
        messages.success(request, 'شعر منتشر شد.' if post.status == 'published' else 'شعر برای تأیید مدیر ارسال شد.')
        return redirect('explore')
    return render(request, 'poetry/explore_publish.html', {'form': form})


@require_GET
def detail(request, pk):
    post = get_object_or_404(ExplorePost.objects.select_related('author'), pk=pk, status='published')
    if not request.session.get('explore_visitor'):
        request.session['explore_visitor'] = secrets.token_hex(24)
    identity = f'user:{request.user.pk}' if request.user.is_authenticated else request.session['explore_visitor']
    visitor = hashlib.sha256(identity.encode()).hexdigest()
    ExploreView.objects.get_or_create(post=post, visitor=visitor)
    liked = request.user.is_authenticated and post.likes.filter(user=request.user).exists()
    return render(request, 'poetry/explore_post.html', {'post': post, 'liked': liked})


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
