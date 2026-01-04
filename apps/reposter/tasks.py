import os
import yt_dlp
import requests
import time
from celery import shared_task
from django.conf import settings
from django.utils.crypto import get_random_string

@shared_task(bind=True)
def repost_to_instagram_task(self, target_link):
    """
    Progress States: 
    - PROGRESS: Downloading
    - PROGRESS: Uploading to Instagram
    - SUCCESS: Finished
    """
    # 1. Prepare Storage
    self.update_state(state='PROGRESS', meta={'status': 'Initializing...'})
    folder_path = os.path.join(settings.MEDIA_ROOT, 'reposter_temp')
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    
    filename = f"repost_{get_random_string(10)}"
    file_path_base = os.path.join(folder_path, filename)
    full_local_path = None # To be defined after download

    try:
        # 2. Download Media locally
        self.update_state(state='PROGRESS', meta={'status': 'Downloading from Instagram...'})
        ydl_opts = {
            'outtmpl': f'{file_path_base}.%(ext)s',
            'quiet': True,
            'format': 'best'
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(target_link, download=True)
            ext = info.get('ext')
            local_filename = f"{filename}.{ext}"
            full_local_path = f"{file_path_base}.{ext}" # Store this for cleanup
            is_video = info.get('vcodec') != 'none'

        # 3. Prepare Instagram Payload
        self.update_state(state='PROGRESS', meta={'status': 'Publishing to Instagram...'})
        
        # Instagram requires a public URL to fetch your file
        public_media_url = f"https://www.loudsurrey.online{settings.MEDIA_URL}reposter_temp/{local_filename}"
        
        # Custom hashtags as requested
        hashtags = "\n\n#surrey #loudsurrey #surreybc #surreylife #repost #desivibes"
        caption = f"{info.get('description', '')}{hashtags}"

        base_url = f"https://graph.facebook.com/{settings.GRAPH_API_VERSION}/{settings.INSTAGRAM_BUSINESS_ACCOUNT_ID}/media"
        
        payload = {
            'caption': caption,
            'access_token': settings.ACCESS_TOKEN
        }
        
        if is_video:
            payload['video_url'] = public_media_url
            payload['media_type'] = 'VIDEO'
        else:
            payload['image_url'] = public_media_url

        # Step A: Create Container
        res = requests.post(base_url, data=payload).json()
        container_id = res.get('id')
        
        if not container_id:
            return {'status': 'Failed', 'error': res}

        # Step B: Wait for Instagram to process the local file
        processed = False
        for _ in range(15):
            check = requests.get(
                f"https://graph.facebook.com/{settings.GRAPH_API_VERSION}/{container_id}",
                params={'fields': 'status_code', 'access_token': settings.ACCESS_TOKEN}
            ).json()
            if check.get('status_code') == 'FINISHED':
                processed = True
                break
            elif check.get('status_code') == 'ERROR':
                return {'status': 'Failed', 'error': 'Meta API processing error'}
            time.sleep(5)

        if not processed:
            return {'status': 'Failed', 'error': 'Instagram processing timeout'}

        # Step C: Publish
        publish_url = f"https://graph.facebook.com/{settings.GRAPH_API_VERSION}/{settings.INSTAGRAM_BUSINESS_ACCOUNT_ID}/media_publish"
        final_res = requests.post(publish_url, data={
            'creation_id': container_id,
            'access_token': settings.ACCESS_TOKEN
        }).json()

        return {'status': 'Successfully Posted', 'media_id': final_res.get('id')}

    except Exception as e:
        return {'status': 'Error', 'message': str(e)}

    finally:
        # --- NEW: Cleanup Logic ---
        # This block runs even if the upload fails or crashes
        if full_local_path and os.path.exists(full_local_path):
            try:
                os.remove(full_local_path)
                print(f"Cleaned up temporary file: {full_local_path}")
            except Exception as cleanup_error:
                print(f"Failed to delete temp file: {cleanup_error}")