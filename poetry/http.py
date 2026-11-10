from functools import wraps
from django.contrib.auth.views import redirect_to_login
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib import messages


def wants_json(request):
    return 'application/json' in request.headers.get('Accept', '')


def private(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            if wants_json(request):
                return JsonResponse({'ok': False, 'code': 'login_required'}, status=401)
            return redirect_to_login(request.get_full_path())
        return view(request, *args, **kwargs)
    return wrapped


def success(request, message, target, **data):
    if wants_json(request):
        return JsonResponse({'ok': True, 'message': message, **data})
    messages.success(request, message)
    return redirect(target)


def failure(request, message, status=400, code='invalid', errors=None):
    if wants_json(request):
        return JsonResponse({'ok': False, 'code': code, 'message': message, 'errors': errors or {}}, status=status)
    return render(request, 'error.html', {'message': message}, status=status)
