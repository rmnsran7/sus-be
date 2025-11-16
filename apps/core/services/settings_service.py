# apps/core/services/settings_service.py

from django.core.cache import cache
from ..models import GlobalSettings

def get_global_settings():
    """
    Retrieves the global settings object from the cache.
    If it's not in the cache, it fetches it from the database and caches it.
    This prevents unnecessary database queries on every request.
    
    Returns:
        GlobalSettings: The singleton GlobalSettings object.
    """
    # Define a unique cache key
    cache_key = 'global_settings'
    
    # Try to get the settings from the cache
    settings = cache.get(cache_key)
    
    if settings is None:
        # If not found in cache, get from DB
        # The .get_solo() method is provided by django-solo
        settings = GlobalSettings.get_solo()
        
        # Store it in the cache for a long time (e.g., 1 day).
        # The cache will be automatically cleared when settings are saved (see models.py).
        cache.set(cache_key, settings, timeout=86400)
        
    return settings