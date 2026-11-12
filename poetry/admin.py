from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.template.loader import render_to_string
from django.template.response import TemplateResponse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.urls import reverse

from .models import Poem, Verse, Tag, FavoriteVerse, PoemEditRequest
from .services.edit_requests import decide_edit, edit_changes

class ReadOnlySuperuserAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return request.user.is_superuser
    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

for model in [Poem, Verse, Tag, FavoriteVerse]:
    admin.site.register(model, ReadOnlySuperuserAdmin)


@admin.register(PoemEditRequest)
class PoemEditRequestAdmin(ReadOnlySuperuserAdmin):
    list_display = ('poem', 'requester', 'status', 'created_at', 'decided_by')
    list_filter = ('status',)
    list_select_related = ('poem__owner', 'requested_by', 'decided_by')
    readonly_fields = ('poem', 'requester', 'changes', 'status', 'created_at', 'decided_at', 'decided_by', 'rejection_reason')
    fields = readonly_fields
    actions = ('approve_edits', 'reject_edits')

    @admin.display(description='درخواست‌دهنده')
    def requester(self, obj):
        user = obj.requested_by or obj.poem.owner
        return format_html('<a href="{}">{}</a>', reverse('admin:accounts_user_change', args=[user.pk]), user.username)

    @admin.display(description='مقایسهٔ نسخه‌ها')
    def changes(self, obj):
        rows, has_original = edit_changes(obj)
        return mark_safe(render_to_string('admin/poetry/poem_edit_changes.html', {'rows': rows, 'has_original': has_original}))

    def _decide(self, request, queryset, *, approve, reason=''):
        count = 0
        for edit in queryset:
            try:
                decide_edit(edit, request.user, approve=approve, rejection_reason=reason)
            except ValidationError as exc:
                self.message_user(request, ' '.join(exc.messages), messages.ERROR)
            except IntegrityError:
                self.message_user(request, 'تداخل در ذخیرهٔ موضوع‌ها. درخواست را دوباره بررسی کنید.', messages.ERROR)
            else:
                count += 1
        if count:
            self.message_user(request, f'{count} درخواست بررسی شد.', messages.SUCCESS)

    @admin.action(permissions=['view'], description='تأیید و اعمال ویرایش‌های انتخاب‌شده')
    def approve_edits(self, request, queryset):
        self._decide(request, queryset, approve=True)

    @admin.action(permissions=['view'], description='رد درخواست‌های انتخاب‌شده')
    def reject_edits(self, request, queryset):
        if not request.user.is_superuser:
            return
        reason = request.POST.get('reason', '').strip()
        if request.POST.get('confirmed') and 0 < len(reason) <= 500:
            self._decide(request, queryset, approve=False, reason=reason)
            return
        return TemplateResponse(request, 'admin/poetry/reject_edits.html', {
            **self.admin_site.each_context(request), 'opts': self.model._meta,
            'edits': queryset, 'error': bool(request.POST.get('confirmed')),
            'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
        })
