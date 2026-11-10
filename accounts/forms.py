from django import forms
from django.contrib.auth.forms import AuthenticationForm

class PersianAuthenticationForm(AuthenticationForm):
    username = forms.CharField(label='نام کاربری', widget=forms.TextInput(attrs={'autofocus': True, 'autocomplete': 'username'}), error_messages={'required': 'نام کاربری را وارد کنید.'})
    password = forms.CharField(label='رمز عبور', strip=False, widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}), error_messages={'required': 'رمز عبور را وارد کنید.'})
    error_messages = {
        'invalid_login': 'نام کاربری یا رمز عبور درست نیست.',
        'inactive': 'این حساب غیرفعال است.',
    }
