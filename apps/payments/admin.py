# apps/payments/admin.py

from django.contrib import admin
from .models import Payment

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'post', 'status', 'amount', 'currency', 'stripe_payment_intent_id', 'created_at')
    list_filter = ('status', 'currency', 'created_at')
    search_fields = ('stripe_payment_intent_id', 'post__post_number', 'post__user__name')
    readonly_fields = ('post', 'stripe_payment_intent_id', 'amount', 'currency', 'created_at', 'updated_at')

    # Payments should be system-generated, not created manually in the admin
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False