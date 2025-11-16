# apps/users/models.py

import uuid
from django.db import models

class User(models.Model):
    """
    Stores information about each unique user to track their activity,
    status, and posting history.
    """
    name = models.CharField(
        max_length=50, 
        help_text="The name the user provides on their first visit."
    )
    tracking_cookie = models.UUIDField(
        default=uuid.uuid4, 
        editable=False, 
        unique=True, 
        db_index=True, 
        help_text="Unique identifier stored in the user's browser cookie."
    )
    
    is_hard_blocked = models.BooleanField(
        default=False, 
        db_index=True, 
        help_text="If true, this user is permanently banned from posting."
    )
    flags_count = models.PositiveIntegerField(
        default=0, 
        help_text="Counter for how many times this user's posts have been flagged."
    )
    
    # Tracking Information
    initial_ip = models.GenericIPAddressField(
        null=True, 
        blank=True, 
        help_text="The first IP address used by this user."
    )
    initial_user_agent = models.CharField(
        max_length=255, 
        null=True, 
        blank=True, 
        help_text="The first user agent string from the user's browser."
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        # Show first 8 chars of UUID for a cleaner admin display
        return f"{self.name} ({str(self.tracking_cookie)[:8]})"


class UserActivityLog(models.Model):
    """
    Tracks significant user actions for analytics and moderation purposes.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activity_logs')
    action = models.CharField(
        max_length=100, 
        help_text="Description of the action (e.g., 'submit_post', 'payment_initiated')."
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name_plural = "User Activity Logs"

    def __str__(self):
        return f"{self.user.name} - {self.action} at {self.timestamp.strftime('%Y-%m-%d %H:%M')}"