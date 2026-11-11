from django import forms
from django.contrib.auth.password_validation import validate_password

from .models import User


class EmailLoginForm(forms.Form):
    email = forms.EmailField(label='ایمیل', max_length=254, widget=forms.EmailInput(attrs={'autocomplete': 'email', 'dir': 'ltr'}))

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if len(email) > 254:
            raise forms.ValidationError('نشانی ایمیل طولانی است.')
        return email


class ThemeForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['theme']
        labels = {'theme': 'ظاهر سایت'}


class ActionPasswordForm(forms.Form):
    current_password = forms.CharField(label='رمز فعلی عملیات', required=False, max_length=128, widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}))
    password = forms.CharField(label='رمز جدید عملیات', max_length=128, widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))
    confirmation = forms.CharField(label='تکرار رمز جدید', max_length=128, widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if not user.action_password:
            del self.fields['current_password']

    def clean_password(self):
        password = self.cleaned_data['password']
        validate_password(password, self.user)
        return password

    def clean(self):
        data = super().clean()
        if self.user.action_password and not self.user.verify_action_password(data.get('current_password', '')):
            self.add_error('current_password', 'رمز فعلی درست نیست.')
        if data.get('password') and data.get('confirmation') != data['password']:
            self.add_error('confirmation', 'دو رمز یکسان نیستند.')
        return data
