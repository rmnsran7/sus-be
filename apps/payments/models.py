# apps/payments/models.py

from django.db import models
from django.conf import settings

# It's good practice to import models this way to avoid circular dependencies
from apps.posts.models import Post

class Payment(models.Model):
    """
    Logs every transaction attempt, its status, and its purpose.
    """
    class PaymentStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        SUCCEEDED = 'SUCCEEDED', 'Succeeded'
        FAILED = 'FAILED', 'Failed'

    class PaymentReason(models.TextChoices):
        PROMOTIONAL_POST = 'PROMOTIONAL_POST', 'Promotional Post'
        IMAGE_UPLOAD = 'IMAGE_UPLOAD', 'Image Upload Fee'
        INSTANT_POST = 'INSTANT_POST', 'Paid Instant Post'

    # Our internal records
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='payments')
    post = models.ForeignKey(Post, on_delete=models.SET_NULL, null=True, related_name='payments')
    
    status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING, db_index=True)
    reason = models.CharField(max_length=20, choices=PaymentReason.choices, default=PaymentReason.PROMOTIONAL_POST)
    amount = models.DecimalField(max_digits=7, decimal_places=2, help_text="Amount in the specified currency.")
    currency = models.CharField(max_length=3, default="usd")

    # Stripe-specific information
    stripe_payment_intent_id = models.CharField(max_length=100, unique=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment {self.id} for Post {self.post_id} - {self.get_status_display()}"