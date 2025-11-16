# apps/users/admin.py

from django.contrib import admin
from .models import User, UserActivityLog

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """
    Admin configuration for the User model.
    """
    list_display = ('name', 'is_hard_blocked', 'flags_count', 'created_at', 'last_seen_at')
    list_filter = ('is_hard_blocked', 'created_at')
    search_fields = ('name', 'tracking_cookie', 'initial_ip')
    readonly_fields = ('tracking_cookie', 'initial_ip', 'initial_user_agent', 'created_at', 'last_seen_at')
    
    fieldsets = (
        ('User Info', {'fields': ('name', 'tracking_cookie')}),
        ('Status', {'fields': ('is_hard_blocked', 'flags_count')}),
        ('Tracking Details', {'fields': ('initial_ip', 'initial_user_agent', 'created_at', 'last_seen_at')}),
    )

@admin.register(UserActivityLog)
class UserActivityLogAdmin(admin.ModelAdmin):
    """
    Admin configuration for the UserActivityLog model.
    """
    list_display = ('user', 'action', 'timestamp')
    list_filter = ('action', 'timestamp')
    search_fields = ('user__name', 'action')
    readonly_fields = ('user', 'action', 'timestamp')
    
    # Disabling the ability to add logs from the admin, as they should be system-generated
    def has_add_permission(self, request):
        return False