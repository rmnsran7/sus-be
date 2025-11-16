from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import uuid
from datetime import datetime
import boto3
from decouple import config
import os
from django.conf import settings
import re
from django.core.cache import cache  # <-- ADDED FOR CACHING

# Import from the parent 'api' directory
from .. import dynamodb_handler
from ..image_generator import InstagramPostGenerator, InstagramPostError

# Import from the local 'views' directory
from .instagram_uploader import upload_to_instagram

# S3 Configuration
S3_BUCKET_NAME = config('S3_BUCKET_NAME')
S3_REGION = config('AWS_REGION_NAME')
s3_client = boto3.client('s3', region_name=S3_REGION)

# --- NEW CACHING LOGIC FOR BLOCKED WORDS ---
BLOCKED_WORDS_CACHE_KEY = "blocked_words_set"
CACHE_TIMEOUT_SECONDS = 3600  # 1 hour

def get_blocked_words_set():
    """
    Retrieves the set of blocked words, using the Django cache.
    If not in cache, fetches from DynamoDB and caches it for 1 hour.
    """
    # 1. Try to get from cache
    blocked_words = cache.get(BLOCKED_WORDS_CACHE_KEY)
    
    if blocked_words is None:
        print("Cache miss. Fetching blocked words from DynamoDB...")
        try:
            # 2. If not in cache, fetch from DB
            # We use get_all_blocked_words (which you built with pagination)
            words_list = dynamodb_handler.get_all_blocked_words()
            
            # Convert to a set for O(1) lookups
            blocked_words = set(words_list)
            
            # 3. Store in cache for 1 hour
            cache.set(BLOCKED_WORDS_CACHE_KEY, blocked_words, CACHE_TIMEOUT_SECONDS)
            print(f"Cached {len(blocked_words)} blocked words.")
        
        except Exception as e:
            # FAIL-SAFE: If DB call fails, log it and return an empty set.
            # This "fails open", preventing a DB error from blocking all posts.
            print(f"CRITICAL: Failed to fetch blocked words from DynamoDB: {e}")
            return set()
            
    return blocked_words
# --- END NEW CACHING LOGIC ---


class PostListView(APIView):
    """
    API endpoint to list posts for a user (GET) or create a new one (POST).
    """
    def get(self, request, *args, **kwargs):
        user_id = request.COOKIES.get('user_id')
        if not user_id:
            return Response({'error': 'This method is not allowed. You can\'t view posts.'}, status=status.HTTP_401_UNAUTHORIZED)
        posts = dynamodb_handler.get_posts_by_user(user_id)
        return Response({'posts': posts}, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        user_id = request.COOKIES.get('user_id')
        if not user_id:
            return Response({'error': 'This method is not allowed.'}, status=status.HTTP_401_UNAUTHORIZED)
        
        text = request.data.get('text', '').strip()
        
        # Validate message length
        if not (10 <= len(text) <= 750):
            return Response({'error': 'Text content must be between 10 and 750 characters.'}, status=status.HTTP_400_BAD_REQUEST)

        # --- NEW: BLOCKED WORD CHECK ---
        try:
            blocked_words_set = get_blocked_words_set()
            if blocked_words_set: 
                # Normalize post text: lowercase and split into words
                # re.findall(r'\w+') is great for splitting "Hello, world!" into ["hello", "world"]
                words_in_post = set(re.findall(r'\w+', text.lower()))
                
                # Find the intersection (any matches)
                found_blocked_words = words_in_post.intersection(blocked_words_set)
                
                if found_blocked_words:
                    # Get the first blocked word to show the user
                    first_blocked = next(iter(found_blocked_words))
                    return Response(
                        {'error': f'Your post contains blocked words.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        except Exception as e:
            # Log this error but "fail open" (allow the post)
            # We don't want a cache error to block all users.
            print(f"Error during blocked word check: {e}. Allowing post.")
        # --- END: BLOCKED WORD CHECK ---

        # Get username from request or fall back to DB
        username = request.data.get('username')
        if not username:
            user_data = dynamodb_handler.get_user_by_id(user_id)
            username = user_data.get('username', 'Anonymous') if user_data else 'Anonymous'

        # --- Updated Validation ---
        if username != 'Anonymous':
            is_valid_chars = re.match(r'^[a-zA-Z_\- ]+$', username)
            is_valid_length = 3 <= len(username) <= 20
            if not is_valid_length or not is_valid_chars:
                username = 'Anonymous'

        one_year_in_seconds = 31_536_000
        
        response_data = None
        response_status = None
        image_url = None
        
        post_id = str(uuid.uuid4())
        file_name = f"{post_id}.png"
        output_path = None

        try:
            post_num = dynamodb_handler.increment_post_counter()
            if post_num is None:
                raise Exception("Failed to get post number from counter.")

            formatted_date = datetime.now().strftime('%d %b')
            
            temp_dir = os.path.join(settings.BASE_DIR, "temp_images")
            os.makedirs(temp_dir, exist_ok=True)
            output_path = os.path.join(temp_dir, file_name)

            generator = InstagramPostGenerator(
                username=username,
                post_id=f"#{post_num}",
                message=text,
                short_date=formatted_date,
                title="Loud Surrey",
            )
            generator.generate_image(output_path)

            with open(output_path, 'rb') as f:
                s3_client.upload_fileobj(
                    Fileobj=f,
                    Bucket=S3_BUCKET_NAME,
                    Key=file_name,
                    ExtraArgs={'ContentType': 'image/png', 'ACL': 'public-read'}
                )
            
            image_url = f"https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/{file_name}"

            instagram_media_id = upload_to_instagram(image_url=image_url, caption=text)
            
            if not instagram_media_id:
                print(f"Critical: Post {post_id} failed to upload to Instagram. Aborting save.")
                response_data = {'error': 'Image was created but failed to upload to Instagram. Check server logs.'}
                response_status = status.HTTP_500_INTERNAL_SERVER_ERROR

        except InstagramPostError as e:
            print(f"Error generating Instagram post image: {e}")
            response_data = {'error': f'Image generation failed: {e}'}
            response_status = status.HTTP_500_INTERNAL_SERVER_ERROR
        except Exception as e:
            print(f"Error during image processing or S3 upload: {e}")
            response_data = {'error': 'Failed to generate or upload image.'}
            response_status = status.HTTP_500_INTERNAL_SERVER_ERROR
        finally:
            if output_path and os.path.exists(output_path):
                os.remove(output_path)

        if response_data is None:
            ip_address = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR')).split(',')[0]
            created_post_id = dynamodb_handler.add_post_for_user(
                user_id=user_id,
                username=username,
                post_num=post_num,
                text=text,
                ip_address=ip_address,
                image_url=image_url,
            )
            
            if created_post_id:
                response_data = {'success': 'True', 'post_id': created_post_id}
                response_status = status.HTTP_201_CREATED
            else:
                response_data = {'success': 'False', 'error': 'Failed to save post record.'}
                response_status = status.HTTP_500_INTERNAL_SERVER_ERROR

        response = Response(response_data, status=response_status)
        
        response.set_cookie(
            'username',
            username,
            max_age=one_year_in_seconds,
            httponly=True,
            samesite='Lax'
        )

        return response