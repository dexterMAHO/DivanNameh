from django.contrib import admin
from poetry.admin import ReadOnlySuperuserAdmin
from .models import MemorizationItem, ReviewLog
admin.site.register(MemorizationItem, ReadOnlySuperuserAdmin)
admin.site.register(ReviewLog, ReadOnlySuperuserAdmin)
