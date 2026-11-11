from django import forms
from django.contrib import admin, messages
from django.utils.html import format_html
from .access import issue_browser_link
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
    actions = ('create_reader_link',)

    @admin.action(description='ساخت پیوند یک‌بارمصرف برای مرورگر خواننده')
    def create_reader_link(self, request, queryset):
        if not request.user.is_superuser:
            return
        if queryset.count() != 1:
            self.message_user(request, 'یک حساب خواننده را انتخاب کنید.', messages.ERROR)
            return
        user = queryset.first()
        link = issue_browser_link(request, user)
        if not link:
            self.message_user(request, 'پیوند فقط برای حساب فعال خواننده صادر می‌شود.', messages.ERROR)
            return
        self.message_user(request, format_html(
            'پیوند {} تا ۱۵ دقیقه اعتبار دارد. آن را برای صاحب حساب بفرستید. <a href="{}">پیوند ثبت مرورگر</a>',
            user.username, link,
        ), messages.SUCCESS)


admin.site.site_header = 'مدیریت دیوان نامه'
