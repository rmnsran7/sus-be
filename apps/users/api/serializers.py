# apps/users/api/serializers.py

from rest_framework import serializers
from ..models import User

class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration. Requires only the name.
    """
    name = serializers.CharField(required=True, max_length=50)

    class Meta:
        model = User
        fields = ['name']

class UserDisplaySerializer(serializers.ModelSerializer):
    """
    Serializer for displaying basic user information back to the client.
    """
    class Meta:
        model = User
        fields = ['name', 'is_hard_blocked']