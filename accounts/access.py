import hashlib
import json
import secrets
from datetime import timedelta
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from .forms import UsernameAccessForm
from .models import BrowserAccessLink, User

BROWSER_COOKIE = 'divannameh_reader_browser'
BROWSER_AGE = 90 * 24 * 60 * 60


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def readers():
    return User.objects.filter(is_active=True, is_staff=False, is_superuser=False)


def issue_browser_link(request, user):
    token = secrets.token_urlsafe(32)
    with transaction.atomic():
        owner = readers().select_for_update().filter(pk=user.pk).first()
        if owner is None:
            return None
        now = timezone.now()
        owner.browser_access_links.filter(expires_at__lte=now).delete()
        owner.browser_access_links.create(
            token_hash=digest(token), expires_at=now + timedelta(minutes=15),
        )
    return request.build_absolute_uri(reverse('confirm-browser')) + '?' + urlencode({'token': token})


def safe_next(request):
    path = request.POST.get('next', '') if request.method == 'POST' else request.GET.get('next', '')
    if url_has_allowed_host_and_scheme(path, allowed_hosts=set(), require_https=request.is_secure()):
        return path
    return ''


def trusted_browser(request, user):
    token = request.get_signed_cookie(BROWSER_COOKIE, default='', max_age=BROWSER_AGE)
    if not token:
        return False
    token_hash = digest(token)
    # Keep accepting the cookie issued before accounts supported multiple browsers.
    return (constant_time_compare(token_hash, user.browser_token_hash)
            or user.trusted_browsers.filter(token_hash=token_hash, expires_at__gt=timezone.now()).exists())


def enroll_browser(request, user, target=''):
    if trusted_browser(request, user):
        token = request.get_signed_cookie(BROWSER_COOKIE, max_age=BROWSER_AGE)
    else:
        token = secrets.token_urlsafe(32)
    now = timezone.now()
    user.trusted_browsers.filter(expires_at__lte=now).delete()
    user.trusted_browsers.update_or_create(
        token_hash=digest(token), defaults={'expires_at': now + timedelta(seconds=BROWSER_AGE)},
    )
    login(request, user)
    response = redirect(target or 'dashboard')
    response.set_signed_cookie(BROWSER_COOKIE, token, max_age=BROWSER_AGE, httponly=True,
                        secure=settings.SESSION_COOKIE_SECURE, samesite='Lax')
    return response


def turnstile_site_key():
    return settings.TURNSTILE_SITE_KEY if settings.TURNSTILE_SECRET_KEY else ''


def human_verified(request, answer, site_key):
    if not site_key:
        expected = request.session.pop('human_answer', None)
        return expected is not None and expected == answer
    token = request.POST.get('cf-turnstile-response', '')
    if not token or len(token) > 2048:
        return False
    validation = Request('https://challenges.cloudflare.com/turnstile/v0/siteverify', data=urlencode({
        'secret': settings.TURNSTILE_SECRET_KEY, 'response': token,
    }).encode())
    try:
        with urlopen(validation, timeout=6) as response:
            result = json.load(response)
    except (OSError, ValueError):
        return False
    return (result.get('success') is True and result.get('action') == 'reader-access'
            and result.get('hostname') == request.get_host().split(':', 1)[0])


@never_cache
@require_http_methods(['GET', 'POST'])
def username_access(request, signup=False):
    if request.user.is_authenticated:
        return redirect('dashboard')
    site_key = turnstile_site_key()
    target = safe_next(request)
    form = UsernameAccessForm(request.POST if request.method == 'POST' else None)
    if site_key:
        del form.fields['human_answer']
    if request.method == 'POST' and form.is_valid():
        if not human_verified(request, form.cleaned_data.get('human_answer'), site_key):
            form.add_error(None, 'تأیید انسان بودن انجام نشد. دوباره تلاش کنید.')
        else:
            username = form.cleaned_data['username']
            if signup:
                try:
                    with transaction.atomic():
                        user = User.objects.create(username=username, password=make_password(None))
                        return enroll_browser(request, user, target)
                except IntegrityError:
                    form.add_error('username', 'این نام کاربری در دسترس نیست.')
            else:
                user = readers().filter(username=username).first()
                if user and trusted_browser(request, user):
                    login(request, user)
                    return redirect(target or 'dashboard')
                form.add_error(None, 'ورود با این مرورگر ممکن نیست. از مرورگر ثبت‌شده استفاده کنید یا پیوند دسترسی بگیرید.')
    challenge = None
    if not site_key:
        challenge = (secrets.randbelow(9) + 1, secrets.randbelow(9) + 1)
        request.session['human_answer'] = sum(challenge)
    return render(request, 'accounts/login.html', {
        'form': form, 'signup': signup, 'site_key': site_key, 'challenge': challenge, 'next': target,
    })


@never_cache
@require_http_methods(['GET', 'POST'])
def confirm_browser(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    token = request.GET.get('token', '') if request.method == 'GET' else request.POST.get('token', '')
    error = None
    if request.method == 'POST':
        with transaction.atomic():
            # Lock the account for both new and legacy links before consuming a token.
            link = BrowserAccessLink.objects.filter(
                token_hash=digest(token), expires_at__gt=timezone.now(),
            ).first()
            if link:
                user = readers().select_for_update().filter(pk=link.user_id).first()
                if user:
                    consumed, _ = user.browser_access_links.filter(
                        pk=link.pk, expires_at__gt=timezone.now(),
                    ).delete()
                    if consumed:
                        return enroll_browser(request, user)
            # Previously issued links remain usable until their original expiry.
            user = readers().select_for_update().filter(
                access_link_hash=digest(token), access_link_expires_at__gt=timezone.now(),
            ).first()
            if user:
                user.access_link_hash = None
                user.access_link_expires_at = None
                user.save(update_fields=['access_link_hash', 'access_link_expires_at'])
                return enroll_browser(request, user)
        error = 'پیوند معتبر نیست یا زمان استفاده از آن گذشته است.'
    response = render(request, 'accounts/browser_confirm.html', {'token': token, 'error': error})
    response['Referrer-Policy'] = 'no-referrer'
    return response


@require_POST
def sign_out(request):
    user = request.user
    forget = request.POST.get('forget') == '1'
    if forget and user.is_authenticated:
        token = request.get_signed_cookie(BROWSER_COOKIE, default='', max_age=BROWSER_AGE)
        if token:
            token_hash = digest(token)
            with transaction.atomic():
                User.objects.select_for_update().only('pk').get(pk=user.pk)
                User.objects.filter(pk=user.pk, browser_token_hash=token_hash).update(browser_token_hash='')
                user.trusted_browsers.filter(token_hash=token_hash).delete()
    logout(request)
    response = redirect('login')
    if forget:
        response.delete_cookie(BROWSER_COOKIE, samesite='Lax')
    return response
