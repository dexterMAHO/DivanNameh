from memorization.services.reviews import get_due_items

def navigation(request):
    return {'due_count': get_due_items(request.user).count() if request.user.is_authenticated else 0}
