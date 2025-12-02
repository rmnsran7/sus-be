# apps/posts/services/instagram_uploader.py

import requests
import time
from django.conf import settings
from apps.core.models import GlobalSettings

def get_access_token():
    """Retrieves access token from DB, falls back to settings."""
    try:
        gs = GlobalSettings.objects.get()
        if gs.instagram_access_token:
            return gs.instagram_access_token
    except Exception:
        pass
    return settings.ACCESS_TOKEN

def wait_for_media_processing(container_id, access_token, timeout=60, interval=5):
    """
    Polls the container status until it is FINISHED or times out.
    Returns (True, None) if ready, or (False, error_dict) if failed/timed out.
    """
    start_time = time.time()
    url = f"https://graph.facebook.com/{settings.GRAPH_API_VERSION}/{container_id}"
    params = {
        'access_token': access_token,
        'fields': 'status_code,status'
    }

    print(f"Polling status for container {container_id}...")

    while time.time() - start_time < timeout:
        response = requests.get(url, params=params)
        
        if response.status_code != 200:
            return False, response.json()

        data = response.json()
        status_code = data.get('status_code')

        if status_code == 'FINISHED':
            print("Container processing FINISHED. Ready to publish.")
            return True, None
        
        elif status_code == 'ERROR':
            return False, {'message': 'Container processing failed', 'details': data}
        
        elif status_code == 'EXPIRED':
            return False, {'message': 'Container ID expired', 'details': data}

        # If IN_PROGRESS or other status, wait and retry
        print(f"Status is {status_code}. Waiting {interval}s...")
        time.sleep(interval)

    return False, {'message': 'Timed out waiting for media processing', 'last_status': status_code}

def publish_to_instagram(image_url, caption):
    """
    Publishes an image to Instagram with status polling.
    Returns: {'success': bool, 'media_id': str|None, 'error': dict|None, 'status_code': int}
    """
    access_token = get_access_token()
    
    # ---------------------------------------------------------
    # Step 1: Create media container
    # ---------------------------------------------------------
    container_url = f"https://graph.facebook.com/{settings.GRAPH_API_VERSION}/{settings.INSTAGRAM_BUSINESS_ACCOUNT_ID}/media"
    container_payload = {
        'image_url': image_url, 
        'caption': caption, 
        'access_token': access_token
    }
    
    response = requests.post(container_url, data=container_payload)
    
    if response.status_code != 200:
        print(f"Error creating media container: {response.json()}")
        return {
            'success': False, 
            'media_id': None, 
            'error': response.json(),
            'status_code': response.status_code
        }
    
    container_id = response.json().get('id')
    if not container_id:
        return {
            'success': False, 
            'media_id': None, 
            'error': {'message': 'No container ID returned', 'response': response.json()},
            'status_code': response.status_code
        }

    # ---------------------------------------------------------
    # Step 2: Poll status until FINISHED (Fix for Error 2207027)
    # ---------------------------------------------------------
    is_ready, processing_error = wait_for_media_processing(container_id, access_token)
    
    if not is_ready:
        print(f"Media processing failed: {processing_error}")
        return {
            'success': False,
            'media_id': None,
            'error': processing_error,
            'status_code': 400 # Bad Request / Timeout
        }

    # ---------------------------------------------------------
    # Step 3: Publish the container
    # ---------------------------------------------------------
    publish_url = f"https://graph.facebook.com/{settings.GRAPH_API_VERSION}/{settings.INSTAGRAM_BUSINESS_ACCOUNT_ID}/media_publish"
    publish_payload = {
        'creation_id': container_id, 
        'access_token': access_token
    }
    
    publish_response = requests.post(publish_url, data=publish_payload)
    
    if publish_response.status_code != 200:
        print(f"Error publishing media: {publish_response.json()}")
        return {
            'success': False, 
            'media_id': None, 
            'error': publish_response.json(),
            'status_code': publish_response.status_code
        }
    
    media_id = publish_response.json().get('id')
    print(f"Successfully published post with media ID: {media_id}")
    
    return {
        'success': True, 
        'media_id': media_id, 
        'error': None,
        'status_code': 200
    }