from django.contrib.auth import login
from django.contrib import messages
from django.shortcuts import redirect, render

from .forms import PersianUserCreationForm


def signup(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = PersianUserCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, 'حساب شما ساخته شد؛ به دفترتان خوش آمدید.')
        return redirect('dashboard')
    return render(request, 'accounts/signup.html', {'form': form})
