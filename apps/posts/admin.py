# apps/posts/admin.py

from django.contrib import admin
from django.utils.html import format_html
import json

from .models import Post, PostImage

class PostImageInline(admin.TabularInline):
    model = PostImage
    extra = 0
    readonly_fields = ('id', 'image_url', 'is_text_image', 'created_at')
    can_delete = False

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    inlines = [PostImageInline]
    
    list_display = ('post_number', 'user', 'get_status_display_colored', 'meta_api_status', 'created_at', 'is_promotional')
    
    list_filter = ('status', 'moderation_reason', 'created_at', 'is_promotional', 'meta_api_status')
    
    search_fields = ('post_number', 'user__name', 'text_content')
    
    # --- UPDATED: Added meta_api_error and meta_api_status ---
    readonly_fields = (
        'post_number', 'user', 'submission_ip', 'submission_user_agent', 
        'instagram_media_id', 'created_at', 'posted_at',
        'moderation_reason', 'llm_moderation_response',
        'meta_api_status', 'meta_api_error' 
    )
    
    fieldsets = (
        ('Post Details', {
            'fields': ('post_number', 'user', 'status')
        }),
        ('Content', {
            'fields': ('text_content',)
        }),
        ('Moderation Details', {
            'fields': ('is_promotional', 'moderation_reason', 'llm_moderation_response'),
        }),
        # --- NEW SECTION: API Debugging ---
        ('Meta API Debugging', {
            'classes': ('collapse',), # Collapsed by default to keep UI clean
            'fields': ('meta_api_status', 'meta_api_error'),
            'description': "Details returned by Facebook/Instagram during upload. Check 'meta_api_error' for failure reasons."
        }),
        ('Submission Metadata', {
            'classes': ('collapse',),
            'fields': ('submission_ip', 'submission_user_agent', 'instagram_media_id', 'created_at', 'posted_at')
        }),
    )

    @admin.display(description='Status', ordering='status')
    def get_status_display_colored(self, obj):
        if obj.status == Post.PostStatus.POSTED:
            color = "green"
        elif obj.status in [Post.PostStatus.PENDING_MODERATION, Post.PostStatus.AWAITING_PAYMENT]:
            color = "orange"
        elif obj.status == Post.PostStatus.FAILED:
            color = "red"
        else: # PROCESSING
            color = "blue"
        return format_html('<b style="color: {};">{}</b>', color, obj.get_status_display())