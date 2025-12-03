# apps/posts/tasks.py

import re 
from celery import shared_task
from django.utils import timezone
from .models import Post, PostImage
from .services.image_generator import create_post_image
from .services import s3_uploader, instagram_uploader

@shared_task
def process_and_publish_post(post_id, raw_content=None):
    try:
        post = Post.objects.get(id=post_id)
    except Post.DoesNotExist:
        return

    # --- 1. CHECK FOR EXISTING IMAGE (Smart Retry) ---
    # If we are retrying a failed post, the image might already exist.
    # We should reuse it to preserve formatting (tags) that aren't stored in the DB.
    existing_image = PostImage.objects.filter(post=post, is_text_image=True).first()
    image_url = None

    if existing_image:
        print(f"Found existing image for Post #{post.post_number}. Skipping generation.")
        image_url = existing_image.image_url
    else:
        print(f"Generating image for Post #{post.post_number}...")
        
        # Use raw_content (with tags) if available, otherwise fallback to clean DB content
        message_for_image = raw_content if raw_content else post.text_content

        image_file = create_post_image(
            post_number=post.post_number,
            username=post.user.name,
            message=message_for_image,
            short_date=timezone.now().strftime("%d %b"),
            title=post.user.name.lower().replace(" ", "")
        )

        if not image_file:
            post.status = Post.PostStatus.FAILED
            post.save()
            return

        print(f"Uploading image to S3 for Post #{post.post_number}...")
        image_url = s3_uploader.upload_file_to_s3(image_file, file_type='png')
        
        if not image_url:
            post.status = Post.PostStatus.FAILED
            post.save()
            return

        # Create the PostImage record so we don't regenerate it next time
        PostImage.objects.create(post=post, image_url=image_url, is_text_image=True)

    # --- 2. PUBLISH TO INSTAGRAM ---
    print(f"Publishing to Instagram for Post #{post.post_number}...")

    # Sanitize content for the caption (remove @mentions)
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