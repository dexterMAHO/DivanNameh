from memorization.services.reviews import get_due_items
from accounts.models import ProfilePhoto

def navigation(request):
    if not request.user.is_authenticated:
        return {}
    return {
        'due_count': get_due_items(request.user).count(),
        'has_profile_photo': ProfilePhoto.objects.filter(user=request.user).exists(),
    }
