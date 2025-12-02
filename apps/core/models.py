# apps/core/models.py

from django.db import models
from django.core.cache import cache
from solo.models import SingletonModel

# ==============================================================================
# 1. Global Application Settings
# ==============================================================================
class GlobalSettings(SingletonModel):
    """
    A singleton model to hold all global configuration for the application.
    This allows an admin to control app behavior without changing code.
    Inherits from SingletonModel to enforce only one instance.
    """
    # General Posting Control
    allow_posting_globally = models.BooleanField(
        default=True, 
        help_text="Master switch to allow or disallow all new posts."
    )
    min_time_between_posts = models.PositiveIntegerField(
        default=30, 
        help_text="Minimum time in seconds a user must wait between posts."
    )

    # Content Moderation Settings
    enable_blocked_words_check = models.BooleanField(
        default=True, 
        help_text="Enable to check submissions against the BlockedWords list."
    )
    enable_llm_analysis = models.BooleanField(
        default=True, 
        help_text="Enable to send messages to an LLM for spam/harmful/promotion checks."
    )

    # Monetization Settings
    charge_for_promotional_posts = models.BooleanField(
        default=False, 
        help_text="Enable to require payment for posts flagged as promotional."
    )
    promotional_post_fee = models.DecimalField(
        max_digits=6, decimal_places=2, default=4.99, 
        help_text="Cost for a promotional post."
    )
    
    charge_for_image_uploads = models.BooleanField(
        default=False, 
        help_text="Enable to require payment when a user uploads their own images."
    )
    image_upload_fee = models.DecimalField(
        max_digits=6, decimal_places=2, default=1.49, 
        help_text="Cost for uploading images with a post."
    )

    enable_paid_instant_post = models.BooleanField(
        default=False, 
        help_text="Allow users to pay to bypass the posting queue if API limits are hit."
    )
    instant_post_fee = models.DecimalField(
        max_digits=6, decimal_places=2, default=0.99, 
        help_text="Cost to post immediately when the queue is active."
    )

    instagram_access_token = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="The 'Never-Expiring' Page Access Token for Instagram/Facebook API."
    )

    class Meta:
        verbose_name = "Global Settings"
        verbose_name_plural = "Global Settings"

    def __str__(self):
        return "Global Application Settings"

    def save(self, *args, **kwargs):
        # When settings are saved, clear the cache to ensure the app
        # fetches the updated values.
        cache.delete('global_settings')
        super().save(*args, **kwargs)

# ==============================================================================
# 2. Blocked Words Model
# ==============================================================================
class BlockedWord(models.Model):
    """
    A list of words that are not allowed in post submissions.
    The check is case-insensitive.
    """
    word = models.CharField(
        max_length=100, 
        unique=True, 
        db_index=True,
        help_text="The word to block. Checks will be case-insensitive."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.word

    def save(self, *args, **kwargs):
        # Ensure the word is always saved in lowercase to prevent duplicates
        # and simplify lookups.
        self.word = self.word.lower()
        super().save(*args, **kwargs)