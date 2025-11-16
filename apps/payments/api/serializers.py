# apps/payments/api/serializers.py

from rest_framework import serializers

class CreatePaymentIntentSerializer(serializers.Serializer):
    post_id = serializers.IntegerField(required=True)
    # The amount can be fetched from global settings on the backend
    # but could also be passed from the frontend for flexibility.