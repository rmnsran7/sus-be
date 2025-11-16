# apps/payments/api/urls.py

from django.urls import path
from .views import CreatePaymentIntentView, StripeWebhookView

app_name = 'payments_api'

urlpatterns = [
    path('create-payment-intent/', CreatePaymentIntentView.as_view(), name='create_payment_intent'),
    path('webhook/', StripeWebhookView.as_view(), name='stripe_webhook'),
]