from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

class PersianAuthenticationForm(AuthenticationForm):
    username = forms.CharField(label='نام کاربری', widget=forms.TextInput(attrs={'autofocus': True, 'autocomplete': 'username'}), error_messages={'required': 'نام کاربری را وارد کنید.'})
    password = forms.CharField(label='رمز عبور', strip=False, widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}), error_messages={'required': 'رمز عبور را وارد کنید.'})
    error_messages = {
        'invalid_login': 'نام کاربری یا رمز عبور درست نیست.',
        'inactive': 'این حساب غیرفعال است.',
    }


class PersianUserCreationForm(UserCreationForm):
    username = forms.CharField(label='نام کاربری', max_length=150, widget=forms.TextInput(attrs={'autofocus': True, 'autocomplete': 'username'}), help_text='حداکثر ۱۵۰ نویسه؛ حروف، ارقام و @ . + - _', error_messages={'required': 'نام کاربری را وارد کنید.'})
    password1 = forms.CharField(label='رمز عبور', strip=False, widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}), help_text='دست‌کم ۸ نویسه؛ نه کاملاً عددی و نه شبیه نام کاربری.', error_messages={'required': 'رمز عبور را وارد کنید.'})
    password2 = forms.CharField(label='تکرار رمز عبور', strip=False, widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}), error_messages={'required': 'تکرار رمز عبور را وارد کنید.'})
    error_messages = {'password_mismatch': 'دو رمز واردشده یکسان نیستند.'}

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        error_messages = {'username': {'unique': 'این نام کاربری قبلاً گرفته شده است.'}}
