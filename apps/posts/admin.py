# apps/posts/admin.py

from django.contrib import admin, messages
from django.utils.html import format_html
import json

from .models import Post, PostImage
from .tasks import process_and_publish_post  # Import the task

class PostImageInline(admin.TabularInline):
    model = PostImage
    extra = 0
    readonly_fields = ('id', 'image_url', 'is_text_image', 'created_at')
    can_delete = False

# --- NEW ADMIN ACTION ---
@admin.action(description="🔄 Retry publishing selected posts")
def retry_failed_posts(modeladmin, request, queryset):
    count = 0
    for post in queryset:
        # Only retry posts that aren't already posted or processing to avoid duplicates
        if post.status not in [Post.PostStatus.POSTED, Post.PostStatus.PROCESSING]:
            # Reset status to PROCESSING so the admin sees immediate feedback
            post.status = Post.PostStatus.PROCESSING
            post.meta_api_error = None # Clear previous errors
            post.save()
            
            # Trigger the task asynchronously
            process_and_publish_post.delay(post.id)
            count += 1
    
    if count > 0:
        modeladmin.message_user(request, f"Successfully queued {count} post(s) for retry.", messages.SUCCESS)
    else:
        modeladmin.message_user(request, "No eligible posts selected for retry (already posted or processing).", messages.WARNING)


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    inlines = [PostImageInline]
    
    # Add the new action to the list
    actions = [retry_failed_posts]
    
    list_display = ('post_number', 'user', 'get_status_display_colored', 'meta_api_status', 'created_at', 'is_promotional')
    list_filter = ('status', 'moderation_reason', 'created_at', 'is_promotional', 'meta_api_status')
    search_fields = ('post_number', 'user__name', 'text_content')
    
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
        ('Meta API Debugging', {
            'classes': ('collapse',),
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
        else:
            color = "blue"
        return format_html('<b style="color: {};">{}</b>', color, obj.get_status_display())