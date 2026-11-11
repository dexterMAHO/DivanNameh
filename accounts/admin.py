from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm
from .models import User


class ReaderAdminForm(UserChangeForm):
    def clean_login_email(self):
        email = self.cleaned_data['login_email']
        return email.lower() if email else None


@admin.register(User)
class ReaderAdmin(UserAdmin):
    form = ReaderAdminForm
    fieldsets = UserAdmin.fieldsets + (
        ('ورود خواننده', {'fields': ('login_email',)}),
    )
    search_fields = (*UserAdmin.search_fields, 'login_email')


admin.site.site_header = 'مدیریت دیوان نامه'
