import hashlib
import json
import logging
import secrets
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from .forms import ReaderLoginForm, UsernameAccessForm
from .models import User

logger = logging.getLogger(__name__)


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def readers():
    return User.objects.filter(is_active=True, is_staff=False, is_superuser=False)


def safe_next(request):
    path = request.POST.get('next', '') if request.method == 'POST' else request.GET.get('next', '')
    if url_has_allowed_host_and_scheme(path, allowed_hosts=set(), require_https=request.is_secure()):
        return path
    return ''


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
    human_check_enabled = settings.READER_HUMAN_CHECK_ENABLED
    site_key = turnstile_site_key() if human_check_enabled else ''
    target = safe_next(request)
    form_class = UsernameAccessForm if signup else ReaderLoginForm
    form = form_class(request.POST if request.method == 'POST' else None)
    if site_key or not human_check_enabled:
        del form.fields['human_answer']
    if request.method == 'POST' and form.is_valid():
        if human_check_enabled and not human_verified(request, form.cleaned_data.get('human_answer'), site_key):
            form.add_error(None, 'تأیید انسان بودن انجام نشد. دوباره تلاش کنید.')
        else:
            username = form.cleaned_data['username']
            if signup:
                try:
                    with transaction.atomic():
                        user = User.objects.create(username=username, password=make_password(None))
                except IntegrityError as error:
                    if User.objects.filter(username=username).exists():
                        form.add_error('username', 'این نام کاربری قبلاً ثبت شده است؛ از گزینهٔ ورود به حساب استفاده کنید یا نام دیگری انتخاب کنید.')
                    else:
                        diagnostic = getattr(error.__cause__, 'diag', None)
                        logger.error('Account creation integrity failure: constraint=%s column=%s',
                                     getattr(diagnostic, 'constraint_name', None),
                                     getattr(diagnostic, 'column_name', None))
                        form.add_error(None, 'ساخت حساب به دلیل مشکل ذخیره‌سازی انجام نشد. لطفاً کمی بعد دوباره تلاش کنید.')
                else:
                    login(request, user)
                    return redirect(target or 'dashboard')
            else:
                user = readers().filter(username=username).first()
                if user is None and form.cleaned_data.get('password'):
                    user = authenticate(request, username=username, password=form.cleaned_data['password'])
                if user is not None:
                    login(request, user)
                    return redirect(target or 'dashboard')
                form.add_error(None, 'ورود با این نام کاربری ممکن نیست.')
    challenge = None
    if human_check_enabled and not site_key:
        challenge = (secrets.randbelow(9) + 1, secrets.randbelow(9) + 1)
        request.session['human_answer'] = sum(challenge)
    return render(request, 'accounts/login.html', {
        'human_check_enabled': human_check_enabled, 'form': form, 'signup': signup, 'site_key': site_key, 'challenge': challenge, 'next': target,
    })


@never_cache
@require_http_methods(['GET', 'POST'])
def recover(request):
    if request.user.is_authenticated:
        return redirect('settings')
    error = False
    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        if 32 <= len(code) <= 80:
            with transaction.atomic():
                user = readers().select_for_update().filter(recovery_digest=digest(code)).first()
                if user:
                    user.recovery_digest = None
                    user.save(update_fields=['recovery_digest'])
                    login(request, user)
                    return redirect('dashboard')
        error = True
    return render(request, 'accounts/recover.html', {'error': error})


@require_POST
def sign_out(request):
    logout(request)
    return redirect('login')
