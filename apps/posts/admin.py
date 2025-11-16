# apps/posts/admin.py

from django.contrib import admin
from django.utils.html import format_html
import json

from .models import Post, PostImage

class PostImageInline(admin.TabularInline):
    model = PostImage
    extra = 0
    # Added 'id' to readonly_fields for clarity
    readonly_fields = ('id', 'image_url', 'is_text_image', 'created_at')
    can_delete = False

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    inlines = [PostImageInline]
    
    # --- MODIFIED: Added moderation_reason and a formatted status ---
    list_display = ('post_number', 'user', 'get_status_display_colored', 'moderation_reason', 'created_at', 'is_promotional')
    
    # --- MODIFIED: Added moderation_reason to allow filtering by flag type ---
    list_filter = ('status', 'moderation_reason', 'created_at', 'is_promotional')
    
    search_fields = ('post_number', 'user__name', 'text_content')
    
    # --- MODIFIED: Added new moderation fields to be read-only ---
    readonly_fields = (
        'post_number', 'user', 'submission_ip', 'submission_user_agent', 
        'instagram_media_id', 'created_at', 'posted_at',
        'moderation_reason', 'llm_moderation_response' # Added new fields
    )
    
    # --- MODIFIED: Reorganized fieldsets and added a new "Moderation" section ---
    fieldsets = (
        ('Post Details', {
            'fields': ('post_number', 'user', 'status')
        }),
        ('Content', {
            'fields': ('text_content',)
        }),
        # --- NEW: A dedicated section for all moderation-related information ---
        ('Moderation Details', {
            'fields': ('is_promotional', 'moderation_reason', 'llm_moderation_response'),
        }),
        ('Submission Metadata', {
            'classes': ('collapse',), # Start collapsed
            'fields': ('submission_ip', 'submission_user_agent', 'instagram_media_id', 'created_at', 'posted_at')
        }),
    )

    # --- NEW: Method to add color to the status in the list view ---
    @admin.display(description='Status', ordering='status')
    def get_status_display_colored(self, obj):
        """Returns the status with a color-coded style for the admin list view."""
        if obj.status == Post.PostStatus.POSTED:
            color = "green"
        elif obj.status in [Post.PostStatus.PENDING_MODERATION, Post.PostStatus.AWAITING_PAYMENT]:
            color = "orange"
        elif obj.status == Post.PostStatus.FAILED:
            color = "red"
        else: # PROCESSING
            color = "blue"
        return format_html('<b style="color: {};">{}</b>', color, obj.get_status_display())