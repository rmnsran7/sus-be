# apps/posts/tasks.py

import re 
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from .models import Post, PostImage
from .services.image_generator import create_post_image
from .services import s3_uploader, instagram_uploader

@shared_task
def process_and_publish_post(post_id, raw_content=None):
    try:
        # --- 1. INITIAL CHECK & LOCK ---
        # We lock the row to prevent race conditions where two tasks run simultaneously.
        with transaction.atomic():
            try:
                # select_for_update() ensures no one else can modify this post until we release the lock
                post = Post.objects.select_for_update().get(id=post_id)
            except Post.DoesNotExist:
                print(f"Post {post_id} not found.")
                return

            # A. IDEMPOTENCY CHECK: If already posted or has media ID, stop.
            if post.status == Post.PostStatus.POSTED or post.instagram_media_id:
                print(f"Post #{post.post_number} is already published. Aborting duplicate task.")
                return

            # B. SCHEDULING CHECK
            # If the post is SCHEDULED, we ensure it's actually time to post.
            if post.status == Post.PostStatus.SCHEDULED:
                if not post.scheduled_time:
                    return # Invalid state
                
                # Check if it's too early (allow 30s buffer)
                time_diff = post.scheduled_time - timezone.now()
                if time_diff.total_seconds() > 30:
                    print(f"Skipping Post #{post.post_number}: Scheduled for {post.scheduled_time}, but task ran too early.")
                    return

            # C. UPDATE STATUS
            # Mark as PROCESSING immediately so other workers (and the admin panel) know we are busy.
            # This update happens inside the lock, so it's safe.
            if post.status != Post.PostStatus.PROCESSING:
                post.status = Post.PostStatus.PROCESSING
                post.save()
    
    except Exception as e:
        print(f"Error during initialization of task for post {post_id}: {e}")
        return

    # --- 2. IMAGE GENERATION & UPLOAD (Outside Atomic Block) ---
    # We perform slow network/CPU operations outside the DB lock to prevent database bottlenecks.
    try:
        # We use the data from the 'post' object we fetched earlier.
        # NOTE: We use post_id for DB lookups to ensure we are using the correct reference.

        # --- CHECK FOR EXISTING IMAGE (Smart Retry) ---
        existing_image = PostImage.objects.filter(post_id=post_id, is_text_image=True).first()
        image_url = None

        if existing_image:
            print(f"Found existing image for Post #{post.post_number}. Skipping generation.")
            image_url = existing_image.image_url
        else:
            print(f"Generating image for Post #{post.post_number}...")
            message_for_image = raw_content if raw_content else post.text_content

            image_file = create_post_image(
                post_number=post.post_number,
                username=post.user.name,
                message=message_for_image,
                short_date=timezone.now().strftime("%d %b"),
                title=post.user.name.lower().replace(" ", "")
            )

            if not image_file:
                _fail_post(post_id, "Image generation failed")
                return

            print(f"Uploading image to S3 for Post #{post.post_number}...")
            image_url = s3_uploader.upload_file_to_s3(image_file, file_type='png')
            
            if not image_url:
                _fail_post(post_id, "S3 upload failed")
                return

            PostImage.objects.create(post_id=post_id, image_url=image_url, is_text_image=True)

        # --- PUBLISH TO INSTAGRAM ---
        print(f"Publishing to Instagram for Post #{post.post_number}...")

        clean_text = re.sub(r'(?<!\S)@\w+', ' ', post.text_content)

        caption = (
            f"📢 Post #{post.post_number}\n\n"
            f"{clean_text}\n\n"
            f"👤 Submitted by: {post.user.name}\n\n"
            f"Shared anonymously on LoudSurrey.\n"
            f"⚠️ Disclaimer: We did not create this content and are not responsible for any resulting harm."
            f"\n\n #surreybc #newtonsurrey #surreycentral #strawberryhill #punjabiincanada #surreypind #internationalstudents #kpu #gediroute #surreylife #surreywale"
        )

        result = instagram_uploader.publish_to_instagram(image_url, caption)
        
        # --- 3. SAVE RESULT (Atomic Lock Again) ---
        with transaction.atomic():
            # Re-lock to safely update final status.
            # This ensures we don't overwrite a status if another process somehow intervened.
            post = Post.objects.select_for_update().get(id=post_id)
            
            # Double check: did someone else finish it while we were uploading?
            if post.status == Post.PostStatus.POSTED:
                print(f"Post #{post.post_number} was finished by another worker. Skipping save.")
                return

            if result['success']:
                post.status = Post.PostStatus.POSTED
                post.instagram_media_id = result['media_id']
                post.posted_at = timezone.now()
                post.meta_api_error = None
                post.meta_api_status = 200
                post.save()
                print(f"Successfully processed and published Post #{post.post_number}.")
            else:
                post.status = Post.PostStatus.FAILED
                post.meta_api_error = result['error']
                post.meta_api_status = result['status_code']
                post.save()
                print(f"Failed to publish Post #{post.post_number}. Error: {result['error']}")

    except Exception as e:
        print(f"Error in process_and_publish_post for {post_id}: {e}")
        _fail_post(post_id, str(e))

def _fail_post(post_id, error_message):
    """Helper to safely mark post as failed inside a lock."""
    try:
        with transaction.atomic():
            post = Post.objects.select_for_update().get(id=post_id)
            post.status = Post.PostStatus.FAILED
            post.meta_api_error = error_message
            post.save()
    except Exception:
        pass