from io import BytesIO

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.forms import UsernameField
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import User


class UsernameAccessForm(forms.Form):
    username = UsernameField(
        label='نام کاربری', max_length=150, validators=User._meta.get_field('username').validators,
        widget=forms.TextInput(attrs={'autocomplete': 'username', 'autocapitalize': 'none'}),
    )
    human_answer = forms.IntegerField(label='حاصل جمع', required=False)


class ThemeForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['theme']
        labels = {'theme': 'حالت نمایش'}


class AppearanceForm(ThemeForm):
    class Meta(ThemeForm.Meta):
        fields = ['theme', 'palette']
        labels = {'theme': 'حالت نمایش', 'palette': 'پالت رنگی'}
        widgets = {'palette': forms.RadioSelect}


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


class ProfilePhotoForm(forms.Form):
    photo = forms.FileField(label='عکس پروفایل', widget=forms.FileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}))

    def clean_photo(self):
        upload = self.cleaned_data['photo']
        if upload.size > 1024 * 1024:
            raise forms.ValidationError('حجم عکس باید حداکثر ۱ مگابایت باشد.')
        try:
            with Image.open(upload, formats=['JPEG', 'PNG', 'WEBP']) as source:
                if max(source.size) > 4096:
                    raise forms.ValidationError('عرض و ارتفاع عکس باید حداکثر ۴۰۹۶ پیکسل باشد.')
                photo = ImageOps.exif_transpose(source).convert('RGB')
                photo.thumbnail((256, 256))
                output = BytesIO()
                photo.save(output, 'WEBP', quality=85)
        except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
            raise forms.ValidationError('یک عکس JPG، PNG یا WebP معتبر انتخاب کنید.') from exc
        return output.getvalue()
