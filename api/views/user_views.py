# api/views/user_views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

# Import from the parent 'api' directory
from .. import dynamodb_handler

class InitView(APIView):
    """
    API endpoint to initialize a user session.
    """
    def get(self, request, *args, **kwargs):
        user_id = request.COOKIES.get('user_id')
        
        def get_user_info(request):
            ip_address = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR')).split(',')[0]
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            return ip_address, user_agent

        if user_id:
            return Response({'status': 'returning_user', 'user_id': user_id}, status=status.HTTP_200_OK)
        else:
            ip_address, user_agent = get_user_info(request)
            new_user_id = dynamodb_handler.create_new_user(ip_address, user_agent)

            if new_user_id:
                response_data = {'status': 'new_user_created', 'user_id': new_user_id}
                response = Response(response_data, status=status.HTTP_201_CREATED)
                response.set_cookie(key='user_id', value=new_user_id, max_age=31536000, httponly=True, samesite='Lax')
                return response
            else:
                return Response({'error': 'Failed to create user'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)