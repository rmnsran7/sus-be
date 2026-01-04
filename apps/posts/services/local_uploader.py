# apps/posts/services/local_uploader.py
import os
import uuid
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

def upload_file_locally(file_obj, file_type='jpeg'):
    if file_type not in ['jpeg', 'png', 'jpg']:
        raise ValueError("Invalid file type. Must be 'jpeg' or 'png'.")

    # Generate a unique filename
    filename = f"{uuid.uuid4()}.{file_type}"
    relative_path = os.path.join('posts', filename)
    
    # Save the file to MEDIA_ROOT/posts/
    path = default_storage.save(relative_path, ContentFile(file_obj.read()))
    
    # Return the full public URL that Instagram can reach
    return f"https://loudsurrey.online{settings.MEDIA_URL}{path}"