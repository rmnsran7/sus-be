# apps/posts/services/instagram_uploader.py

import requests
from django.conf import settings

def _test_publish_to_instagram(image_url, caption):
    # Dummy function to simulate success without real API calls
    print(f"Simulated upload to Instagram with image_url='{image_url}' and caption='{caption}'")
    dummy_media_id = "1234567890_dummy_media_id"
    print(f"Successfully 'published' post with media ID: {dummy_media_id}")
    return dummy_media_id
    
def publish_to_instagram(image_url, caption):
    # Step 1: Create media container
    container_url = f"https://graph.facebook.com/{settings.GRAPH_API_VERSION}/{settings.INSTAGRAM_BUSINESS_ACCOUNT_ID}/media"
    container_payload = {'image_url': image_url, 'caption': caption, 'access_token': settings.ACCESS_TOKEN}
    
    response = requests.post(container_url, data=container_payload)
    if response.status_code != 200:
        print(f"Error creating media container: {response.json()}")
        return None
    
    container_id = response.json().get('id')
    if not container_id:
        print(f"Failed to get container ID: {response.json()}")
        return None

    # In production, you must poll the container status before publishing.
    # This example assumes it's ready instantly, which is not guaranteed.
    
    # Step 2: Publish the container
    publish_url = f"https://graph.facebook.com/{settings.GRAPH_API_VERSION}/{settings.INSTAGRAM_BUSINESS_ACCOUNT_ID}/media_publish"
    publish_payload = {'creation_id': container_id, 'access_token': settings.ACCESS_TOKEN}
    
    publish_response = requests.post(publish_url, data=publish_payload)
    if publish_response.status_code != 200:
        print(f"Error publishing media: {publish_response.json()}")
        return None
    
    media_id = publish_response.json().get('id')
    print(f"Successfully published post with media ID: {media_id}")
    return media_id
