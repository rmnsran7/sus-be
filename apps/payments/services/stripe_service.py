# apps/payments/services/stripe_service.py

import stripe
from django.conf import settings
from ..models import Payment
from apps.posts.models import Post
from apps.posts.tasks import process_and_publish_post

# Set the API key for all Stripe operations in this file
stripe.api_key = settings.STRIPE_API_SECRET_KEY

def create_payment_intent(post: Post, amount: float):
    """
    Creates a PaymentIntent with Stripe and a corresponding Payment record in our database.

    This is the function that was missing.

    Returns:
        str: The client_secret for the PaymentIntent, or None on failure.
    """
    try:
        # Stripe expects the amount in the smallest currency unit (e.g., cents for USD)
        amount_in_cents = int(amount * 100)

        # Create the PaymentIntent on Stripe's servers
        # We attach the post_id in metadata so we can track it in the webhook
        intent = stripe.PaymentIntent.create(
            amount=amount_in_cents,
            currency='usd',
            automatic_payment_methods={'enabled': True},
            metadata={
                'post_id': post.id,
                'post_number': post.post_number, # Good for logging
            }
        )

        # Create a local record of this payment attempt
        Payment.objects.create(
            post=post,
            stripe_payment_intent_id=intent.id,
            amount=amount,
            status=Payment.PaymentStatus.PENDING
        )

        return intent.client_secret
    except Exception as e:
        print(f"Error creating Stripe PaymentIntent: {e}")
        return None

def handle_webhook_event(payload: bytes, sig_header: str):
    """
    Verifies and processes a webhook event from Stripe.

    Returns:
        bool: True if the event was processed successfully, False otherwise.
    """
    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=settings.STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        print(f"Webhook signature verification failed: {e}")
        return False

    event_type = event['type']
    data_object = event['data']['object']

    if event_type == 'payment_intent.succeeded':
        print('PaymentIntent was successful!')
        payment_intent = data_object
        
        try:
            payment = Payment.objects.get(stripe_payment_intent_id=payment_intent.id)
            if payment.status == Payment.PaymentStatus.PENDING:
                payment.status = Payment.PaymentStatus.SUCCEEDED
                payment.save()
                
                post = payment.post
                if post and post.status == Post.PostStatus.AWAITING_PAYMENT:
                    post.status = Post.PostStatus.PROCESSING
                    post.save()
                    process_and_publish_post.delay(post.id)
                    print(f"Post #{post.post_number} status updated and task triggered.")
            else:
                print(f"Payment {payment.id} already processed. Ignoring webhook.")

        except Payment.DoesNotExist:
            print(f"Error: Payment with intent ID {payment_intent.id} not found in our database.")
            return False

    elif event_type == 'payment_intent.payment_failed':
        print('Payment failed.')
        payment_intent = data_object
        try:
            payment = Payment.objects.get(stripe_payment_intent_id=payment_intent.id)
            payment.status = Payment.PaymentStatus.FAILED
            payment.save()
        except Payment.DoesNotExist:
            print(f"Error: Payment with intent ID {payment_intent.id} not found.")
            return False
            
    else:
        print(f'Unhandled event type {event_type}')

    return True