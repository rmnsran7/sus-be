# apps/users/api/urls.py

from django.urls import path
from .views import UserRegistrationView, UserStatusView # Import the new view

app_name = 'users-api'

urlpatterns = [
    path('register/', UserRegistrationView.as_view(), name='register'),
    path('status/', UserStatusView.as_view(), name='status'), # Add this line
]