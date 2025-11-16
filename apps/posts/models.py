# apps/posts/models.py

from django.db import models, transaction
from django.core.validators import MinValueValidator
from apps.users.models import User  # Import User model from the users app

class Post(models.Model):
    class PostStatus(models.TextChoices):
        AWAITING_PAYMENT = 'AWAITING_PAYMENT', 'Awaiting Payment'
        PENDING_MODERATION = 'PENDING_MODERATION', 'Pending Moderation'
        PROCESSING = 'PROCESSING', 'Processing'
        POSTED = 'POSTED', 'Posted'
        FAILED = 'FAILED', 'Failed'

    post_number = models.PositiveIntegerField(
        unique=True,
        db_index=True,
        validators=[MinValueValidator(2100)],
        help_text="Unique, sequential post number starting from 2100."
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    text_content = models.TextField(max_length=2200, help_text="The user's message (max 2200 chars for Instagram).")
    
    status = models.CharField(
        max_length=20,
        choices=PostStatus.choices,
        default=PostStatus.PROCESSING,
        db_index=True
    )
    
    # --- NEW FIELD ADDED HERE ---
    is_promotional = models.BooleanField(
        default=False, 
        db_index=True,
        help_text="Set to True if the LLM analysis identifies the post as promotional."
    )

    # NEW: Field to store the raw JSON response from the LLM
    llm_moderation_response = models.JSONField(
        null=True,
        blank=True,
        help_text="The raw JSON response from the LLM moderation analysis."
    )

    # NEW: Field to store why a post was flagged
    moderation_reason = models.CharField(
        max_length=255,
        blank=True,
        help_text="The reason this post was flagged (e.g., Blocked Word, LLM Harmful)."
    )
    
    submission_ip = models.GenericIPAddressField()
    submission_user_agent = models.CharField(max_length=255)
    
    instagram_media_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="The media ID returned by the Instagram API upon successful posting."
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    posted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of when the post was successfully uploaded to a social media platform."
    )

    class Meta:
        ordering = ['-post_number']

    def __str__(self):
        return f"Post #{self.post_number} by {self.user.name}"

    @classmethod
    def get_next_post_number(cls):
        with transaction.atomic():
            last_post = cls.objects.select_for_update().order_by('-post_number').first()
            if last_post:
                return last_post.post_number + 1
            return 2100

class PostImage(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='images')
    image_url = models.URLField(max_length=1024, help_text="URL to the image stored in S3.")
    is_text_image = models.BooleanField(
        default=False,
        help_text="True if this is the auto-generated image from text, False for user uploads."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        type_of_image = "Text Image" if self.is_text_image else "User Upload"
        return f"{type_of_image} for Post #{self.post.post_number}"