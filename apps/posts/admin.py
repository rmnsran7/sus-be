# apps/posts/admin.py

from django.contrib import admin, messages
from django.utils.html import format_html
from django.utils import timezone
import json

from .models import Post, PostImage
from .tasks import process_and_publish_post

class PostImageInline(admin.TabularInline):
    model = PostImage
    extra = 0
    readonly_fields = ('id', 'image_url', 'is_text_image', 'created_at')
    can_delete = False

@admin.action(description="🔄 Retry publishing selected posts")
def retry_failed_posts(modeladmin, request, queryset):
    count = 0
    for post in queryset:
        if post.status not in [Post.PostStatus.POSTED, Post.PostStatus.PROCESSING]:
            post.status = Post.PostStatus.PROCESSING
            post.meta_api_error = None
            post.save()
            process_and_publish_post.delay(post.id)
            count += 1
    
    if count > 0:
        modeladmin.message_user(request, f"Successfully queued {count} post(s) for retry.", messages.SUCCESS)
    else:
        modeladmin.message_user(request, "No eligible posts selected for retry.", messages.WARNING)


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    inlines = [PostImageInline]
    actions = [retry_failed_posts]
    
    # Enables the search box for Users and the green "+" button to add new ones
    autocomplete_fields = ['user'] 
    
    list_display = ('post_number', 'user', 'get_status_display_colored', 'scheduled_time', 'created_at', 'is_promotional')
    list_filter = ('status', 'scheduled_time', 'moderation_reason', 'created_at', 'is_promotional')
    search_fields = ('post_number', 'user__name', 'text_content')
    
    readonly_fields = (
        'post_number', 'submission_ip', 'submission_user_agent', 
        'instagram_media_id', 'created_at', 'posted_at',
        'moderation_reason', 'llm_moderation_response',
        'meta_api_status', 'meta_api_error' 
    )
    
    fieldsets = (
        ('Create Post', {
            'description': "Select a user (or click + to create one) and enter the message.",
            'fields': ('user', 'text_content')
        }),
        ('Publishing Options', {
            'description': "Leave 'Scheduled time' EMPTY to Post Now. Set a time to Schedule.",
            'fields': ('status', 'scheduled_time')
        }),
        ('System Details (Read-Only)', {
            'classes': ('collapse',),
            'fields': ('post_number', 'moderation_reason', 'meta_api_status', 'meta_api_error', 'instagram_media_id', 'created_at', 'posted_at')
        }),
    )

    def save_model(self, request, obj, form, change):
        """
        Custom save logic to handle 'Post Now' vs 'Schedule'.
        """
        is_new = obj.pk is None
        
        # 1. Generate post_number if new
        if is_new and not obj.post_number:
            obj.post_number = Post.get_next_post_number()
            # Set default IP for admin-created posts if missing
            if not obj.submission_ip:
                obj.submission_ip = "127.0.0.1" 
                obj.submission_user_agent = "Admin Panel"

        # 2. Handle Scheduling Logic
        if obj.scheduled_time:
            # If a time is set, force status to SCHEDULED
            obj.status = Post.PostStatus.SCHEDULED
            super().save_model(request, obj, form, change)
            
            # Queue the task with ETA
            process_and_publish_post.apply_async(args=[obj.id], eta=obj.scheduled_time)
            messages.success(request, f"Post #{obj.post_number} scheduled for {obj.scheduled_time}.")
        
        else:
            # If no time is set, assume "Post Now" (PROCESSING)
            # Only auto-start if it was explicitly set to PROCESSING or if it's new
            if obj.status == Post.PostStatus.PROCESSING or (is_new and obj.status != Post.PostStatus.SCHEDULED):
                obj.status = Post.PostStatus.PROCESSING
                super().save_model(request, obj, form, change)
                
                # Queue immediately
                process_and_publish_post.delay(obj.id)
                messages.success(request, f"Post #{obj.post_number} is being processed now.")
            else:
                # Just save (e.g. if status was set to Failed or Awaiting Payment manually)
                super().save_model(request, obj, form, change)

    @admin.display(description='Status', ordering='status')
    def get_status_display_colored(self, obj):
        if obj.status == Post.PostStatus.POSTED:
            color = "green"
        elif obj.status == Post.PostStatus.SCHEDULED:
            color = "purple"
        elif obj.status in [Post.PostStatus.PENDING_MODERATION, Post.PostStatus.AWAITING_PAYMENT]:
            color = "orange"
        elif obj.status == Post.PostStatus.FAILED:
            color = "red"
        else:
            color = "blue"
        return format_html('<b style="color: {};">{}</b>', color, obj.get_status_display())