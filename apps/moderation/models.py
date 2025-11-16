# apps/moderation/models.py

from django.db import models
from apps.posts.models import Post # Import from the posts app

class FlaggedMessage(models.Model):
    """
    A log of messages that were flagged for administrative review, either by
    the blocked word filter or the LLM analysis.
    """
    class FlagReason(models.TextChoices):
        BLOCKED_WORD = 'BLOCKED_WORD', 'Blocked Word'
        LLM_SPAM = 'LLM_SPAM', 'LLM: Spam'
        LLM_HARMFUL = 'LLM_HARMFUL', 'LLM: Harmful Content'

    # A OneToOneField ensures a post can only be flagged once.
    post = models.OneToOneField(Post, on_delete=models.CASCADE, related_name='flag')
    
    reason = models.CharField(
        max_length=20, 
        choices=FlagReason.choices,
        help_text="The reason this post was flagged."
    )
    
    is_reviewed = models.BooleanField(
        default=False, 
        db_index=True,
        help_text="Set to True once an admin has approved or rejected the post."
    )
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Flagged Message"
        verbose_name_plural = "Flagged Messages"

    def __str__(self):
        return f"Flagged Post #{self.post.post_number} for {self.get_reason_display()}"