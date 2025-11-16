import boto3
import uuid
from datetime import datetime, timezone
from decouple import config
from botocore.exceptions import ClientError

# --- Boto3 Clients and Resources ---
DYNAMODB = boto3.resource('dynamodb', region_name=config('AWS_REGION_NAME', default='us-east-1'))

USERS_TABLE = DYNAMODB.Table('users')
POSTS_TABLE = DYNAMODB.Table('posts')
BLOCKED_WORDS_TABLE = DYNAMODB.Table('blocked_words') # <-- ADDED


def create_new_user(ip_address, user_agent):
    """
    Creates a new user item in the 'users' DynamoDB table.
    """
    user_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    user_item = {
        'user_id': user_id,
        'created_at': timestamp,
        'last_seen_at': timestamp,
        'ip_address_history': [ip_address],
        'user_agent_history': [user_agent],
        'username': "Anonymous",
        'post_count': 0 
    }

    try:
        USERS_TABLE.put_item(Item=user_item)
        print(f"Successfully created user: {user_id}")
        return user_id
    except Exception as e:
        print(f"Error creating user: {e}")
        return None


def get_user_by_id(user_id):
    """
    Retrieves a single user item from the 'users' table.
    """
    try:
        response = USERS_TABLE.get_item(Key={'user_id': user_id})
        return response.get('Item')
    except Exception as e:
        print(f"Error getting user {user_id}: {e}")
        return None


def increment_post_counter():
    """
    Atomically increments the global post counter in the 'posts' table.
    If the counter item does not exist, it creates it automatically.
    """
    counter_key = {"user_id": "GLOBAL", "post_id": "COUNTER"}
    
    # Attempt to create the counter item only if it doesn't already exist.
    try:
        POSTS_TABLE.put_item(
            Item={
                "user_id": "GLOBAL",
                "post_id": "COUNTER",
                "post_num": 0
            },
            ConditionExpression="attribute_not_exists(user_id)"
        )
        print("Initialized global post counter.")
    except ClientError as e:
        if e.response['Error']['Code'] != 'ConditionalCheckFailedException':
            raise # Re-raise any other error

    # Now, safely increment the counter.
    try:
        response = POSTS_TABLE.update_item(
            Key=counter_key,
            UpdateExpression="SET post_num = post_num + :val",
            ExpressionAttributeValues={":val": 1},
            ReturnValues="UPDATED_NEW"
        )
        return int(response["Attributes"]["post_num"])
    except Exception as e:
        print(f"Error incrementing post counter: {e}")
        return None


def add_post_for_user(user_id, username, post_num, text, ip_address, image_url):
    """
    Creates a new post item in the 'posts' DynamoDB table.
    """
    post_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    post_item = {
        'user_id': user_id,
        'username': username,
        'post_id': post_id,
        'post_num': post_num,
        'created_at': timestamp,
        'original_text': text,
        'image_url': image_url, 
        'image_generation_status': 'SUCCESS', 
        'source_ip': ip_address
    }
    try:
        POSTS_TABLE.put_item(Item=post_item)
        print(f"Successfully created post {post_id} for user {user_id}")
        return post_id
    except Exception as e:
        print(f"Error creating post: {e}")
        return None


def get_posts_by_user(user_id):
    """
    Retrieves all posts for a given user_id.
    """
    from boto3.dynamodb.conditions import Key
    try:
        response = POSTS_TABLE.query(
            KeyConditionExpression=Key('user_id').eq(user_id)
        )
        return response.get('Items', [])
    except Exception as e:
        print(f"Error retrieving posts for user {user_id}: {e}")
        return []

# --- NEW FUNCTIONS FOR BLOCKED WORDS ---

def add_blocked_words_batch(comma_separated_words: str):
    """
    Adds a comma-separated string of words to the blocked_words table.
    This function handles splitting, cleaning (lowercase, whitespace),
    and batch-writing the words to DynamoDB.
    """
    # 1. Split the string by commas
    words_list = comma_separated_words.split(',')
    
    # 2. Clean, normalize (lowercase), and find unique words
    # This prevents duplicates and handles " word1, word2 "
    unique_words = {word.strip().lower() for word in words_list if word.strip()}
    
    if not unique_words:
        print("No valid words to add.")
        return 0

    # 3. Use batch_writer to efficiently add all items
    try:
        with BLOCKED_WORDS_TABLE.batch_writer() as batch:
            for word in unique_words:
                batch.put_item(
                    Item={'word': word}
                )
        print(f"Successfully added {len(unique_words)} blocked words.")
        return len(unique_words)
    except Exception as e:
        print(f"Error during batch write of blocked words: {e}")
        return 0

def is_word_blocked(word_to_check: str):
    """
    Checks if a single word exists in the blocked_words table.
    Returns True if the word is blocked, False otherwise.
    """
    # Normalize the word to match how it's stored
    word_to_check = word_to_check.lower()
    
    try:
        response = BLOCKED_WORDS_TABLE.get_item(
            Key={'word': word_to_check}
        )
        
        # 'Item' will exist in the response if the word was found
        return 'Item' in response
            
    except Exception as e:
        print(f"Error checking blocked word {word_to_check}: {e}")
        # Fail-safe: If the check fails, assume it's not blocked.
        return False

def get_all_blocked_words():
    """
    Retrieves a list of all words from the blocked_words table.
    Use this for an admin panel. Avoid calling it on every post.
    """
    try:
        response = BLOCKED_WORDS_TABLE.scan()
        words = [item['word'] for item in response.get('Items', [])]
        return words
    except Exception as e:
        print(f"Error scanning for blocked words: {e}")
        return []

def remove_blocked_words_batch(comma_separated_words: str):
    """
    Removes a comma-separated string of words from the blocked_words table.
    This function handles splitting, cleaning, and batch-deleting the words.
    """
    # 1. Split, clean, and find unique words
    unique_words = {word.strip().lower() for word in comma_separated_words.split(',') if word.strip()}

    if not unique_words:
        print("No valid words to remove.")
        return 0

    # 2. Use batch_writer to efficiently delete all items
    try:
        with BLOCKED_WORDS_TABLE.batch_writer() as batch:
            for word in unique_words:
                batch.delete_item(
                    Key={'word': word}
                )
        print(f"Successfully removed {len(unique_words)} blocked words.")
        return len(unique_words)
    except Exception as e:
        print(f"Error during batch delete of blocked words: {e}")
        return 0