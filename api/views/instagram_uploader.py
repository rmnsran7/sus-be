# api/views/instagram_uploader.py

import requests
import time
from decouple import config

# Load Instagram credentials from environment variables
IG_BUSINESS_ACCOUNT_ID = config('IG_BUSINESS_ACCOUNT_ID')
IG_PAGE_ACCESS_TOKEN = config('IG_PAGE_ACCESS_TOKEN')
GRAPH_API_VERSION = 'v24.0'
BASE_GRAPH_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
DEFAULT_SUFFIX = """#surrey #loudsurrey #surreybc #surreybc #punjabi #canadapunjabi #punjabtocanada #internationalstudents #surreylife #desivibes #punjabiwedding #studyincanada #chardikala
─────────────────────────
This content was shared anonymously on LoudSurrey
─────────────────────────
Disclaimer: We are not the creators of this content and are not responsible for any damage caused by it."""

def _handle_api_error(e):
    """Helper function to print detailed API errors."""
    print(f"Instagram API Error: {e}")
    if e.response is not None:
        try:
            print(f"Response Body: {e.response.json()}")
        except requests.exceptions.JSONDecodeError:
            print(f"Response Body: {e.response.text}")
    else:
        print("Response Body: No Response object in exception.")

def _poll_for_container_status(container_id):
    """
    Polls the media container for up to 30 seconds, waiting for
    it to be processed ('FINISHED') or to fail ('ERROR').
    """
    start_time = time.time()
    max_wait_sec = 30
    poll_interval_sec = 3
    
    while time.time() - start_time < max_wait_sec:
        status_check_url = f"https://graph.facebook.com/{container_id}?fields=status_code,status&access_token={IG_PAGE_ACCESS_TOKEN}"
        
        try:
            status_response = requests.get(status_check_url)
            status_response.raise_for_status()
            status_data = status_response.json()
            
            status_code = status_data.get('status_code')

            if status_code == 'FINISHED':
                print(f"Container {container_id} is FINISHED.")
                return True
            elif status_code == 'ERROR':
                print(f"Error: Container {container_id} processing failed.")
                print(f"Status: {status_data.get('status')}")
                return False
            elif status_code == 'IN_PROGRESS':
                print(f"Container {container_id} is IN_PROGRESS. Waiting...")
            else:
                print(f"Container {container_id} has unknown status: {status_code}. Waiting...")
        
        except requests.exceptions.RequestException as e:
            # If polling fails, print error but let the loop retry
            print(f"Warning: API error during status check for {container_id}.")
            _handle_api_error(e)

        time.sleep(poll_interval_sec)

    print(f"Error: Media container {container_id} processing did not finish after {max_wait_sec} seconds.")
    return False

def upload_to_instagram(image_url, caption):
    """
    Uploads a single image to Instagram using the Meta Graph API.
    
    The DEFAULT_SUFFIX will be automatically appended to the caption.
    """
    
    # --- 1. Suffix Handling ---
    # Combine the provided caption with the default suffix
    full_caption = f"{caption}\n\n{DEFAULT_SUFFIX}"

    try:
        # --- 2. Step 1: Create a media container ---
        media_creation_url = f"{BASE_GRAPH_URL}/{IG_BUSINESS_ACCOUNT_ID}/media"
        creation_payload = {
            'image_url': image_url,
            'caption': full_caption,  # Use the new full_caption here
            'access_token': IG_PAGE_ACCESS_TOKEN
        }
        
        print("Creating media container...")
        creation_response = requests.post(media_creation_url, data=creation_payload)
        creation_response.raise_for_status()
        
        container_id = creation_response.json().get('id')
        if not container_id:
            print("Error: Media container ID not found in response.")
            print(f"Response: {creation_response.json()}")
            return None
        
        print(f"Got container ID: {container_id}")

        # --- 3. Step 2: Poll for container status ---
        # Wait for the container to be ready (replaces the old polling logic)
        if not _poll_for_container_status(container_id):
            return None

        # --- 4. Step 3: Publish the media container ---
        print(f"Publishing container {container_id}...")
        publish_url = f"{BASE_GRAPH_URL}/{IG_BUSINESS_ACCOUNT_ID}/media_publish"
        publish_payload = {
            'creation_id': container_id,
            'access_token': IG_PAGE_ACCESS_TOKEN
        }
        
        publish_response = requests.post(publish_url, data=publish_payload)
        publish_response.raise_for_status()
        
        media_id = publish_response.json().get('id')
        print(f"Successfully published to Instagram with media ID: {media_id}")
        return media_id

    except requests.exceptions.RequestException as e:
        _handle_api_error(e)
        return None
    except Exception as e:
        print(f"An unexpected error occurred during Instagram upload: {e}")
        return None