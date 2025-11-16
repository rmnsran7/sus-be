# apps/core/admin.py

from django.contrib import admin
from solo.admin import SingletonModelAdmin
from .models import GlobalSettings, BlockedWord

# Register the singleton model for Global Settings
admin.site.register(GlobalSettings, SingletonModelAdmin)

# Register the BlockedWord model with a custom admin class for better usability
@admin.register(BlockedWord)
class BlockedWordAdmin(admin.ModelAdmin):
    """
    Admin configuration for BlockedWord model.
    """
    list_display = ('word', 'created_at')
    search_fields = ('word',)
    list_per_page = 50