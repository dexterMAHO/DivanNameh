import secrets

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from poetry.http import failure, success

from .access import digest
from .forms import AppearanceForm, ActionPasswordForm, ProfilePhotoForm, ReadingForm, ThemeForm
from .models import ProfilePhoto, User


@login_required
@never_cache
@require_http_methods(['GET', 'POST'])
def settings_page(request):
    submitted = request.POST.get('section')
    theme_form = AppearanceForm(request.POST if submitted == 'theme' else None, instance=request.user)
    password_form = ActionPasswordForm(request.POST if submitted == 'password' else None, user=request.user)
    photo_form = ProfilePhotoForm(
        request.POST if submitted == 'photo' else None,
        request.FILES if submitted == 'photo' else None,
    )
    reading_form = ReadingForm(request.POST if submitted == 'reading' else None, instance=request.user)
    recovery_code = None
    is_reader = not request.user.is_staff and not request.user.is_superuser
    if request.method == 'POST':
        if submitted == 'reading' and reading_form.is_valid():
            User.objects.filter(pk=request.user.pk).update(**reading_form.cleaned_data)
            messages.success(request, 'تنظیمات خواندن ذخیره شد.')
            return redirect('settings')
        if submitted == 'recovery' and is_reader:
            recovery_code = secrets.token_urlsafe(32)
            User.objects.filter(pk=request.user.pk).update(recovery_digest=digest(recovery_code))
        if submitted == 'theme' and theme_form.is_valid():
            User.objects.filter(pk=request.user.pk).update(**theme_form.cleaned_data)
            messages.success(request, 'ظاهر سایت ذخیره شد.')
            return redirect('settings')
        if submitted == 'password':
            with transaction.atomic():
                user = User.objects.select_for_update().get(pk=request.user.pk)
                password_form = ActionPasswordForm(request.POST, user=user)
                if password_form.is_valid():
                    user.action_password = make_password(password_form.cleaned_data['password'])
                    user.save(update_fields=['action_password'])
                    messages.success(request, 'رمز عملیات ذخیره شد.')
                    return redirect('settings')
        if submitted == 'photo' and photo_form.is_valid():
            ProfilePhoto.objects.update_or_create(user=request.user, defaults={'image': photo_form.cleaned_data['photo']})
            messages.success(request, 'عکس پروفایل ذخیره شد.')
            return redirect('settings')
    response = render(request, 'accounts/settings.html', {
        'theme_form': theme_form, 'password_form': password_form, 'photo_form': photo_form,
        'recovery_code': recovery_code,
        'has_recovery': bool(recovery_code or request.user.recovery_digest),
        'reading_form': reading_form,
    })
    if recovery_code:
        response['Referrer-Policy'] = 'no-referrer'
    return response


@login_required
@require_GET
def profile_photo(request):
    photo = get_object_or_404(ProfilePhoto, user=request.user)
    response = HttpResponse(bytes(photo.image), content_type='image/webp')
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_required
@require_POST
def remove_profile_photo(request):
    ProfilePhoto.objects.filter(user=request.user).delete()
    messages.success(request, 'عکس پروفایل برداشته شد.')
    return redirect('settings')


@login_required
@require_POST
def header_theme(request):
    form = ThemeForm(request.POST, instance=request.user)
    if not form.is_valid():
        return failure(request, 'ظاهر انتخاب‌شده معتبر نیست.')
    theme = form.cleaned_data['theme']
    User.objects.filter(pk=request.user.pk).update(theme=theme)
    target = request.POST.get('next', '')
    if not target.startswith('/') or not url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        target = 'dashboard'
    return success(request, 'ظاهر سایت ذخیره شد.', target, theme=theme)
