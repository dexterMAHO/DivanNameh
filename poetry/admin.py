from django.contrib import admin
from .models import Poem, Verse, Tag, FavoriteVerse

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
