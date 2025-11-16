##blocked_words_views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from decouple import config
from django.core.cache import cache  

# Import from the parent 'api' directory
from .. import dynamodb_handler

# Load a secret key from your .env file for security
ADMIN_API_KEY = config('ADMIN_API_KEY', default=None)

# --- IMPORTANT ---
# This key MUST match the one you defined in 'post_views.py'
BLOCKED_WORDS_CACHE_KEY = "blocked_words_set"
# ---

class BlockedWordsView(APIView):
    """
    API endpoint for admins to add or remove blocked words.
    Requires a secret ADMIN_API_KEY in the 'X-Admin-API-Key' header.
    """
    
    def check_permissions(self, request):
        if not ADMIN_API_KEY:
            print("CRITICAL: ADMIN_API_KEY is not set. Endpoint is disabled.")
            return False
            
        api_key_header = request.headers.get('X-Admin-API-Key')
        return api_key_header == ADMIN_API_KEY

    def post(self, request, *args, **kwargs):
        """
        Adds new words to the blocklist.
        Expects {'words': 'word1,word2,word3'} in the request body.
        """
        if not self.check_permissions(request):
            return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        words_to_add = request.data.get('words')
        if not words_to_add or not isinstance(words_to_add, str):
            return Response({'error': 'Please provide a comma-separated string of words in the "words" field.'}, status=status.HTTP_400_BAD_REQUEST)

        added_count = dynamodb_handler.add_blocked_words_batch(words_to_add)
        
        if added_count > 0:
            # --- 2. CLEAR THE CACHE ---
            print("Clearing blocked words cache...")
            cache.delete(BLOCKED_WORDS_CACHE_KEY)
            # ---
        
        return Response({
            'message': f'Successfully processed request.',
            'words_added': added_count
        }, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):
        """
        Removes words from the blocklist.
        Expects {'words': 'word1,word2,word3'} in the request body.
        """
        if not self.check_permissions(request):
            return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
            
        words_to_remove = request.data.get('words')
        if not words_to_remove or not isinstance(words_to_remove, str):
            return Response({'error': 'Please provide a comma-separated string of words in the "words" field.'}, status=status.HTTP_400_BAD_REQUEST)

        removed_count = dynamodb_handler.remove_blocked_words_batch(words_to_remove)

        if removed_count > 0:
            # --- 3. CLEAR THE CACHE ---
            print("Clearing blocked words cache...")
            cache.delete(BLOCKED_WORDS_CACHE_KEY)
            # ---

        return Response({
            'message': f'Successfully processed request.',
            'words_removed': removed_count
        }, status=status.HTTP_200_OK)