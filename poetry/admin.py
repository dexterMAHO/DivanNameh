from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.template.loader import render_to_string
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.urls import reverse
from itertools import zip_longest

from .models import Poem, Verse, Tag, FavoriteVerse, PoemEditRequest
from .services.edit_requests import decide_edit, original_poem, requested_topics

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
    readonly_fields = ('poem', 'requester', 'changes', 'status', 'created_at', 'decided_at', 'decided_by')
    fields = readonly_fields
    actions = ('approve_edits', 'reject_edits')

    @admin.display(description='درخواست‌دهنده')
    def requester(self, obj):
        user = obj.requested_by or obj.poem.owner
        return format_html('<a href="{}">{}</a>', reverse('admin:accounts_user_change', args=[user.pk]), user.username)

    @admin.display(description='مقایسهٔ نسخه‌ها')
    def changes(self, obj):
        before = obj.original
        if before is None and obj.poem.updated_at == obj.poem_updated_at:
            before = original_poem(obj.poem)
        after = {**obj.payload, 'topics': requested_topics(obj)}
        labels = {
            'title': 'عنوان', 'poet_name': 'شاعر', 'source_url': 'منبع',
            'notes': 'یادداشت', 'topics': 'موضوع‌ها',
        }
        rows = []
        for key, label in labels.items():
            previous = before.get(key, '') if before else ''
            proposed = after.get(key, '')
            if key == 'topics':
                previous, proposed = '، '.join(sorted(previous)), '، '.join(sorted(proposed))
            if before is None or previous != proposed:
                rows.append((label, previous, proposed))
        previous_verses = before['verses'] if before else []
        for position, (previous, proposed) in enumerate(zip_longest(previous_verses, after['verses'], fillvalue=()), 1):
            if tuple(previous) != tuple(proposed):
                rows.append((f'بیت {position}', '\n'.join(filter(None, previous)), '\n'.join(filter(None, proposed))))
        return mark_safe(render_to_string('admin/poetry/poem_edit_changes.html', {'rows': rows, 'has_original': before is not None}))

    def _decide(self, request, queryset, *, approve):
        count = 0
        for edit in queryset:
            try:
                decide_edit(edit, request.user, approve=approve)
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
        self._decide(request, queryset, approve=False)
