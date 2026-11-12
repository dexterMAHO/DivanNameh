from django.contrib.auth import logout
from django.utils import timezone

from .access import BROWSER_SESSION, browser_digest


class TrustedBrowserSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        browser_id = request.session.get(BROWSER_SESSION)
        if browser_id and user.is_authenticated:
            if not user.trusted_browsers.filter(pk=browser_id, expires_at__gt=timezone.now()).exists():
                logout(request)
        elif user.is_authenticated and not user.is_staff and not user.is_superuser:
            token_hash = browser_digest(request)
            if token_hash:
                # Bind sessions created before device management shipped.
                active = user.trusted_browsers.filter(token_hash=token_hash, expires_at__gt=timezone.now())
                if browser := active.values_list('pk', flat=True).first():
                    request.session[BROWSER_SESSION] = browser
                elif token_hash != user.browser_token_hash:
                    logout(request)
        return self.get_response(request)
