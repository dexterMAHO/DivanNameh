from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def health(request):
    """Liveness only: no user data, secrets or database query."""
    return JsonResponse({'status': 'ok'})
