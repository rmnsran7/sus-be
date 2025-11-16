# apps/posts/services/s3_uploader.py

import boto3
import uuid
from django.conf import settings
from botocore.exceptions import NoCredentialsError

def upload_file_to_s3(file_obj, file_type='jpeg'):
    if file_type not in ['jpeg', 'png']:
        raise ValueError("Invalid file type. Must be 'jpeg' or 'png'.")

    object_name = f"posts/{uuid.uuid4()}.{file_type}"

    s3_client = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME
    )
    
    try:
        # Use put_object which is simpler and doesn't add a default ACL
        s3_client.put_object(
            Body=file_obj,
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=object_name,
            ContentType=f'image/{file_type}'
            # By not specifying 'ACL', no ACL is sent. This is what you want.
        )
        return f"https://{settings.AWS_S3_CUSTOM_DOMAIN}/{object_name}"
    except NoCredentialsError:
        print("Error: AWS credentials not available.")
        return None
    except Exception as e:
        print(f"An error occurred during S3 upload: {e}")
        return None