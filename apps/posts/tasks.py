# apps/posts/tasks.py

from celery import shared_task
from django.utils import timezone
from .models import Post, PostImage
from .services.image_generator import create_post_image
from .services import s3_uploader, instagram_uploader

@shared_task
def process_and_publish_post(post_id):
    try:
        post = Post.objects.get(id=post_id)
    except Post.DoesNotExist:
        return

    print(f"Generating image for Post #{post.post_number}...")
    image_file = create_post_image(
        post_number=post.post_number,
        username=post.user.name,
        message=post.text_content,
        short_date=timezone.now().strftime("%d %b"),
        title=post.user.name.lower().replace(" ", "")
    )

    if not image_file:
        post.status = Post.PostStatus.FAILED; post.save(); return

    print(f"Uploading image to S3 for Post #{post.post_number}...")
    image_url = s3_uploader.upload_file_to_s3(image_file, file_type='png')
    
    if not image_url:
        post.status = Post.PostStatus.FAILED; post.save(); return

    PostImage.objects.create(post=post, image_url=image_url, is_text_image=True)

    print(f"Publishing to Instagram for Post #{post.post_number}...")
    caption = f"Post #{post.text_content} by {post.user.name}\n\nShared anonymously on SpeakUpSurrey.\nDisclaimer: We did not create this content and are not responsible for any resulting harm."
    media_id = instagram_uploader.publish_to_instagram(image_url, caption)
    
    if not media_id:
        post.status = Post.PostStatus.FAILED; post.save(); return

    post.status = Post.PostStatus.POSTED
    post.instagram_media_id = media_id
    post.posted_at = timezone.now()
    post.save()
    
    print(f"Successfully processed and published Post #{post.post_number}.")