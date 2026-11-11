from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .access import enroll_browser, issue_browser_link, readers
from .forms import ActionPasswordForm, ProfilePhotoForm, ThemeForm
from .models import ProfilePhoto, User


@login_required
@never_cache
@require_http_methods(['GET', 'POST'])
def settings_page(request):
    submitted = request.POST.get('section')
    theme_form = ThemeForm(request.POST if submitted == 'theme' else None, instance=request.user)
    password_form = ActionPasswordForm(request.POST if submitted == 'password' else None, user=request.user)
    photo_form = ProfilePhotoForm(request.POST if submitted == 'photo' else None, request.FILES)
    browser_link = None
    if request.method == 'POST':
        if submitted == 'browser':
            with transaction.atomic():
                user = get_object_or_404(readers().select_for_update(), pk=request.user.pk)
                messages.success(request, 'این مرورگر برای ورود ثبت شد.')
                return enroll_browser(request, user, 'settings')
        if submitted == 'browser-link':
            browser_link = issue_browser_link(request, request.user)
        if submitted == 'theme' and theme_form.is_valid():
            User.objects.filter(pk=request.user.pk).update(theme=theme_form.cleaned_data['theme'])
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
        'browser_link': browser_link,
    })
    if browser_link:
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
