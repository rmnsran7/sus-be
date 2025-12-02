# apps/posts/services/instagram_uploader.py

import requests
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

def publish_to_instagram(image_url, caption):
    """
    Publishes an image to Instagram.
    Returns a dict: {'success': bool, 'media_id': str|None, 'error': dict|None, 'status_code': int}
    """
    access_token = get_access_token()
    
    # Step 1: Create media container
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

    # Step 2: Publish the container
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