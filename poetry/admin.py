from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils.html import format_html

from .models import Poem, Verse, Tag, FavoriteVerse, PoemEditRequest
from .services.edit_requests import decide_edit

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
    list_display = ('poem', 'status', 'created_at', 'decided_by')
    list_filter = ('status',)
    list_select_related = ('poem', 'decided_by')
    readonly_fields = ('poem', 'proposed_text', 'status', 'created_at', 'decided_at', 'decided_by')
    fields = readonly_fields
    actions = ('approve_edits', 'reject_edits')

    @admin.display(description='پیشنهاد کاربر')
    def proposed_text(self, obj):
        payload = obj.payload
        verses = '\n\n'.join('\n'.join(filter(None, verse)) for verse in payload['verses'])
        names = Tag.objects.filter(owner_id=obj.poem.owner_id, pk__in=payload['tags']).values_list('name', flat=True)
        topics = '، '.join(filter(None, [*names, payload['new_tag']]))
        text = (f"عنوان: {payload['title']}\nشاعر: {payload['poet_name']}\n"
                f"منبع: {payload['source_url']}\nموضوع‌ها: {topics}\n"
                f"یادداشت: {payload['notes']}\n\n{verses}")
        return format_html('<pre dir="rtl" style="white-space: pre-wrap">{}</pre>', text)

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
