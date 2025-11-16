# api/models.py

import uuid
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator

# ==============================================================================
# 1. Global Application Settings
# ==============================================================================
class GlobalSettings(models.Model):
    """
    A singleton model to hold all global configuration for the application.
    This allows an admin to control app behavior without changing code.
    """
    # General Posting Control
    allow_posting_globally = models.BooleanField(default=True, help_text="Master switch to allow or disallow all new posts.")
    min_time_between_posts = models.PositiveIntegerField(default=60, help_text="Minimum time in seconds a user must wait between posts.")

    # Content Moderation Settings
    enable_blocked_words_check = models.BooleanField(default=True, help_text="Enable to check submissions against the BlockedWords list.")
    enable_llm_analysis = models.BooleanField(default=True, help_text="Enable to send messages to an LLM for spam/harmful/promotion checks.")

    # Monetization Settings
    charge_for_promotional_posts = models.BooleanField(default=False, help_text="Enable to require payment for posts flagged as promotional.")
    promotional_post_fee = models.DecimalField(max_digits=6, decimal_places=2, default=5.00, help_text="Cost for a promotional post.")
    
    charge_for_image_uploads = models.BooleanField(default=False, help_text="Enable to require payment when a user uploads their own images.")
    image_upload_fee = models.DecimalField(max_digits=6, decimal_places=2, default=2.00, help_text="Cost for uploading images with a post.")

    enable_paid_instant_post = models.BooleanField(default=False, help_text="Allow users to pay to bypass the posting queue if API limits are hit.")
    instant_post_fee = models.DecimalField(max_digits=6, decimal_places=2, default=1.00, help_text="Cost to post immediately when the queue is active.")

    class Meta:
        verbose_name_plural = "Global Settings"

    def __str__(self):
        return "Global Application Settings"

# ==============================================================================
# 2. User Tracking Model
# ==============================================================================
class User(models.Model):
    """
    Stores information about each unique user to track their activity,
    status, and posting history.
    """
    name = models.CharField(max_length=50, help_text="The name the user provides on their first visit.")
    tracking_cookie = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True, help_text="Unique identifier stored in the user's browser cookie.")
    
    is_hard_blocked = models.BooleanField(default=False, db_index=True, help_text="If true, this user is permanently banned from posting.")
    flags_count = models.PositiveIntegerField(default=0, help_text="Counter for how many times this user's posts have been flagged.")
    
    # Tracking Information
    initial_ip = models.GenericIPAddressField(null=True, blank=True, help_text="The first IP address used by this user.")
    initial_user_agent = models.CharField(max_length=255, null=True, blank=True, help_text="The first user agent string from the user's browser.")
    
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({str(self.tracking_cookie)[:8]})"

# ==============================================================================
# 3. Posts and Related Models
# ==============================================================================
class Post(models.Model):
    """
    The central model representing every message submitted by users,
    tracking its content, status, and associated metadata.
    """
    class PostStatus(models.TextChoices):
        PENDING_REVIEW = 'PENDING_REVIEW', 'Pending Review'
        AWAITING_PAYMENT = 'AWAITING_PAYMENT', 'Awaiting Payment'
        SCHEDULED = 'SCHEDULED', 'Scheduled'
        POSTED = 'POSTED', 'Posted'
        REJECTED = 'REJECTED', 'Rejected'
        FLAGGED = 'FLAGGED', 'Flagged' # Generic flagged state

    post_number = models.PositiveIntegerField(unique=True, db_index=True, validators=[MinValueValidator(2100)], help_text="Unique, sequential post number starting from 2100.")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    text_content = models.TextField(max_length=2200) # Instagram's caption limit
    
    status = models.CharField(max_length=20, choices=PostStatus.choices, default=PostStatus.PENDING_REVIEW, db_index=True)
    
    # Metadata captured at submission
    submission_ip = models.GenericIPAddressField()
    submission_user_agent = models.CharField(max_length=255)
    
    # Instagram API Information
    instagram_media_id = models.CharField(max_length=100, null=True, blank=True, help_text="The media ID returned by the Instagram API upon successful posting.")
    
    created_at = models.DateTimeField(auto_now_add=True)
    posted_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp of when the post was successfully uploaded to Instagram.")

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Post #{self.post_number} by {self.user.name}"

class PostImage(models.Model):
    """
    Stores images associated with a Post. This can be the auto-generated
    textual image or user-uploaded images.
    """
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='images')
    image_url = models.URLField(max_length=1024, help_text="URL to the image stored in S3.")
    is_text_image = models.BooleanField(default=False, help_text="True if this is the auto-generated image from text, False for user uploads.")
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for Post #{self.post.post_number}"

# ==============================================================================
# 4. Moderation and Logging Models
# ==============================================================================
class FlaggedMessage(models.Model):
    """
    A log of messages that were flagged for administrative review, either by
    the blocked word filter or the LLM analysis.
    """
    class FlagReason(models.TextChoices):
        BLOCKED_WORD = 'BLOCKED_WORD', 'Blocked Word'
        LLM_SPAM = 'LLM_SPAM', 'LLM: Spam'
        LLM_HARMFUL = 'LLM_HARMFUL', 'LLM: Harmful Content'

    post = models.OneToOneField(Post, on_delete=models.CASCADE, related_name='flag')
    reason = models.CharField(max_length=20, choices=FlagReason.choices)
    is_reviewed = models.BooleanField(default=False, help_text="Admin has reviewed this flag.")
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Flagged Post #{self.post.post_number} for {self.get_reason_display()}"

class BlockedWord(models.Model):
    """
    A list of words that are not allowed in post submissions.
    """
    word = models.CharField(max_length=100, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.word

class UserActivityLog(models.Model):
    """
    Tracks significant user actions for analytics and moderation purposes.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activity_logs')
    action = models.CharField(max_length=100, help_text="Description of the action (e.g., 'submit_post', 'payment_initiated').")
    
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.name} - {self.action} at {self.timestamp.strftime('%Y-%m-%d %H:%M')}"