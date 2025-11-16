# apps/users/api/views.py

from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from ..services import user_service
from .serializers import UserRegistrationSerializer, UserDisplaySerializer

class UserRegistrationView(APIView):
    """
    API endpoint for new users to register by providing a name.
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = UserRegistrationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        name = serializer.validated_data['name']
        
        try:
            # The service call is now wrapped in a try/except block
            # to catch the validation errors we added.
            user, created = user_service.get_or_create_user(request, name=name)

            if not user:
                 return Response({"error": "Could not create or identify user."}, status=status.HTTP_400_BAD_REQUEST)

            response_serializer = UserDisplaySerializer(user)
            response = Response(response_serializer.data, status=status.HTTP_201_CREATED)
            user_service.set_user_cookie(response, user)
            return response
            
        except ValidationError as e:
            # If validate_username raises an error, we catch it here
            # and return it as a 400 Bad Request to the frontend.
            return Response({"error": e.message}, status=status.HTTP_400_BAD_REQUEST)
        

class UserStatusView(APIView):
    """
    Checks the user's status based on their tracking cookie.
    This is the first API call the frontend should make on load.
    """
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        user, created = user_service.get_or_create_user(request, name=None)

        if user:
            serializer = UserDisplaySerializer(user)
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        return Response(
            {"error": "User not found. Please register."},
            status=status.HTTP_401_UNAUTHORIZED
        )