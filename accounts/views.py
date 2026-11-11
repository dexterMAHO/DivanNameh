import hashlib
import logging
import secrets
from datetime import timedelta
from urllib.parse import urlencode
from uuid import uuid4

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.contrib.auth.views import LoginView
from django.core.mail import send_mail
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import ActionPasswordForm, EmailLoginForm, ProfilePhotoForm, ThemeForm
from .legacy_forms import PersianAuthenticationForm, PersianUserCreationForm
from .models import LoginChallenge, ProfilePhoto, User

logger = logging.getLogger(__name__)
LINK_LIFETIME = timedelta(minutes=15)
SEND_INTERVAL = timedelta(seconds=60)


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


legacy_login = LoginView.as_view(
    authentication_form=PersianAuthenticationForm,
    template_name='accounts/legacy_login.html',
    redirect_authenticated_user=True,
)


def legacy_signup(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = PersianUserCreationForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.save())
        return redirect('dashboard')
    return render(request, 'accounts/legacy_signup.html', {'form': form})


@never_cache
@require_http_methods(['GET', 'POST'])
def email_access(request):
    if not settings.PASSWORDLESS_LOGIN:
        if request.resolver_match.url_name == 'signup':
            return legacy_signup(request)
        return legacy_login(request)
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = EmailLoginForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email']
        now = timezone.now()
        last_send = request.session.get('email_link_sent_at', 0)
        if now.timestamp() - last_send < SEND_INTERVAL.total_seconds():
            return render(request, 'accounts/login.html', {'form': form, 'sent': True})
        token = secrets.token_urlsafe(32)
        digest = token_hash(token)
        with transaction.atomic():
            challenge, created = LoginChallenge.objects.select_for_update().get_or_create(
                email=email, defaults={'token_hash': digest, 'issued_at': now},
            )
            if not created and now - challenge.issued_at < SEND_INTERVAL:
                return render(request, 'accounts/login.html', {'form': form, 'sent': True})
            if not created:
                challenge.token_hash, challenge.issued_at = digest, now
                challenge.save(update_fields=['token_hash', 'issued_at'])
        link = request.build_absolute_uri(reverse('email-confirm')) + '?' + urlencode({'token': token})
        try:
            send_mail('ورود به دیوان نامه', f'برای ورود یا ساخت حساب، این پیوند را تا ۱۵ دقیقه باز کنید:\n{link}',
                      None, [email])
        except OSError as exc:
            LoginChallenge.objects.filter(email=email, token_hash=digest).delete()
            logger.warning('Sending a sign-in link failed (%s)', type(exc).__name__)
            form.add_error(None, 'ارسال پیوند ممکن نشد. کمی بعد دوباره تلاش کنید.')
        else:
            request.session['email_link_sent_at'] = now.timestamp()
            return render(request, 'accounts/login.html', {'form': form, 'sent': True})
    return render(request, 'accounts/login.html', {'form': form})


@never_cache
@require_http_methods(['GET', 'POST'])
def email_confirm(request):
    if not settings.PASSWORDLESS_LOGIN:
        return redirect('login')
    token = request.GET.get('token', '') if request.method == 'GET' else request.POST.get('token', '')
    error = None
    if request.method == 'POST' and not request.user.is_authenticated:
        with transaction.atomic():
            challenge = LoginChallenge.objects.select_for_update().filter(
                token_hash=token_hash(token), issued_at__gte=timezone.now() - LINK_LIFETIME,
            ).first()
            if challenge:
                user, _ = User.objects.get_or_create(login_email=challenge.email, defaults={
                    'email': challenge.email, 'username': f'reader-{uuid4().hex}', 'password': make_password(None),
                })
                challenge.delete()
                if user.is_active and not (user.is_staff or user.is_superuser):
                    login(request, user)
                    return redirect('dashboard')
        error = 'پیوند ورود معتبر نیست یا زمان استفاده از آن گذشته است.'
    elif request.user.is_authenticated:
        return redirect('dashboard')
    response = render(request, 'accounts/email_confirm.html', {'token': token, 'error': error})
    response['Referrer-Policy'] = 'no-referrer'
    return response


@login_required
@require_http_methods(['GET', 'POST'])
def settings_page(request):
    submitted = request.POST.get('section')
    theme_form = ThemeForm(request.POST if submitted == 'theme' else None, instance=request.user)
    password_form = ActionPasswordForm(request.POST if submitted == 'password' else None, user=request.user)
    photo_form = ProfilePhotoForm(request.POST if submitted == 'photo' else None, request.FILES)
    if request.method == 'POST':
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
    return render(request, 'accounts/settings.html', {
        'theme_form': theme_form, 'password_form': password_form, 'photo_form': photo_form,
    })


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
