# apps/payments/api/views.py

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
# permission_classes is not needed here as we do manual checks
from rest_framework.permissions import AllowAny 

from ..services import stripe_service
from .serializers import CreatePaymentIntentSerializer
from apps.posts.models import Post
from apps.core.services.settings_service import get_global_settings
# --- IMPORT YOUR USER SERVICE ---
from apps.users.services import user_service

class CreatePaymentIntentView(APIView):
    """
    Creates a Stripe Payment Intent and returns the client secret to the frontend.
    """
    def post(self, request, *args, **kwargs):
        serializer = CreatePaymentIntentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # --- CORRECT WAY TO GET THE USER ---
        user, _ = user_service.get_or_create_user(request)
        if not user:
            # If for some reason the user has no cookie, deny access.
            return Response({"error": "User not identified."}, status=status.HTTP_401_UNAUTHORIZED)
        
        post_id = serializer.validated_data['post_id']
        try:
            # --- CORRECT QUERY ---
            # Now we use the user object from our service to ensure the user owns the post.
            post = Post.objects.get(id=post_id, user=user)
        except Post.DoesNotExist:
            return Response({"error": "Post not found or you do not have permission to pay for it."}, status=status.HTTP_404_NOT_FOUND)

        # Get the fee from global settings for security
        settings = get_global_settings()
        # This logic can be expanded to check if it's a promotional post, image post, etc.
        amount = settings.promotional_post_fee 
        
        client_secret = stripe_service.create_payment_intent(post=post, amount=float(amount))
        
        if client_secret:
            return Response({'clientSecret': client_secret})
        
        return Response(
            {"error": "Could not initiate payment."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# StripeWebhookView remains the same

class StripeWebhookView(APIView):
    """
    Receives webhook events from Stripe.
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

        if not sig_header:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        
        # The service function returns a single boolean value.
        # We assign it to a single variable.
        success = stripe_service.handle_webhook_event(
            payload=payload, 
            sig_header=sig_header
        )

        # Now, we check the boolean and return the appropriate HTTP status.
        # This is what Stripe's servers expect.
        if success:
            return Response(status=status.HTTP_200_OK)
        
        # If the signature was invalid or something went wrong, tell Stripe it failed.
        return Response(status=status.HTTP_400_BAD_REQUEST)