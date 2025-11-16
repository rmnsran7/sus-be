# apps/moderation/admin.py

from django.contrib import admin, messages
from .models import FlaggedMessage
from apps.posts.models import Post
from apps.posts.tasks import process_and_publish_post # Import the Celery task

@admin.register(FlaggedMessage)
class FlaggedMessageAdmin(admin.ModelAdmin):
    list_display = ('get_post_number', 'get_post_content', 'reason', 'is_reviewed', 'created_at')
    list_filter = ('is_reviewed', 'reason', 'created_at')
    search_fields = ('post__text_content', 'post__user__name')
    readonly_fields = ('post', 'reason', 'created_at')
    
    # Define custom actions
    actions = ['approve_selected_posts', 'reject_selected_posts']

    @admin.action(description="Approve selected posts and send for processing")
    def approve_selected_posts(self, request, queryset):
        # Filter for only unreviewed flags
        unreviewed_flags = queryset.filter(is_reviewed=False)
        posts_to_process = []

        for flag in unreviewed_flags:
            post = flag.post
            post.status = Post.PostStatus.PROCESSING
            post.save(update_fields=['status'])
            posts_to_process.append(post.id)
            
        # Trigger Celery task for each approved post
        for post_id in posts_to_process:
            process_and_publish_post.delay(post_id)

        # Mark flags as reviewed
        updated_count = unreviewed_flags.update(is_reviewed=True)
        self.message_user(request, f"{updated_count} posts were approved and sent for processing.", messages.SUCCESS)

    @admin.action(description="Reject selected posts")
    def reject_selected_posts(self, request, queryset):
        # Filter for only unreviewed flags
        unreviewed_flags = queryset.filter(is_reviewed=False)
        
        for flag in unreviewed_flags:
            post = flag.post
            post.status = Post.PostStatus.FAILED # Or a new 'REJECTED' status
            post.save(update_fields=['status'])
        
        updated_count = unreviewed_flags.update(is_reviewed=True)
        self.message_user(request, f"{updated_count} posts were rejected.", messages.SUCCESS)
        
    # Helper methods for better display in the admin
    @admin.display(description='Post #', ordering='post__post_number')
    def get_post_number(self, obj):
        return obj.post.post_number

    @admin.display(description='Post Content')
    def get_post_content(self, obj):
        return (obj.post.text_content[:75] + '...') if len(obj.post.text_content) > 75 else obj.post.text_content