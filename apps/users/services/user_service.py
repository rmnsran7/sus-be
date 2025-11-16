# apps/users/services/user_service.py

from django.core.exceptions import ValidationError
from ..models import User, UserActivityLog
from apps.moderation.services.content_validator import check_for_blocked_words

COOKIE_NAME = 'user_tracking_id'
COOKIE_MAX_AGE = 365 * 24 * 60 * 60  # One year in seconds

# Hardcoded list of reserved names (uses a set for fast lookups).
RESERVED_NAMES = {'admin', 'loudsurrey'}

def validate_username(name: str):
    """
    Performs all validation checks for a new username.
    Raises a ValidationError with a user-friendly message if any check fails.
    """
    if not name or not name.strip():
        raise ValidationError("Name cannot be empty.")
        
    # 1. Length Check
    if len(name) > 10:
        raise ValidationError("Name cannot be longer than 10 characters.")

    # 2. Hardcoded Reserved Names Check (case-insensitive)
    # We remove spaces to catch names like 'Loud Surrey'.
    normalized_name = name.replace(" ", "").lower()
    if normalized_name in RESERVED_NAMES:
        raise ValidationError(f"The name '{name}' is not allowed.")

    # 3. Dynamic Blocked Words Check
    if check_for_blocked_words(name):
        raise ValidationError("Your chosen name contains words that are not allowed.")

    # If all checks pass, we're good to go.
    return None

def get_client_ip(request):
    """Utility function to get the user's IP address from the request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def get_or_create_user(request, name=None):
    """
    Identifies a user by cookie. If not found, validates and creates a new user.
    """
    tracking_id = request.COOKIES.get(COOKIE_NAME)
    user = None
    created = False

    if tracking_id:
        try:
            user = User.objects.get(tracking_cookie=tracking_id)
        except User.DoesNotExist:
            pass

    if user is None and name:
        # --- THIS IS THE KEY CHANGE ---
        # Validate the name before creating the user.
        # This will raise a ValidationError if the name is invalid.
        validate_username(name)
        
        ip = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:255]
        
        user = User.objects.create(
            name=name,
            initial_ip=ip,
            initial_user_agent=user_agent
        )
        created = True
        log_user_activity(user, "user_created")

    return user, created

def set_user_cookie(response, user):
    """Attaches the user tracking cookie to the HTTP response."""
    response.set_cookie(
        COOKIE_NAME,
        value=str(user.tracking_cookie),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite='None',
        secure=True
    )

def log_user_activity(user, action_description):
    """A helper function to create a new UserActivityLog entry."""
    if user and isinstance(user, User):
        UserActivityLog.objects.create(user=user, action=action_description)