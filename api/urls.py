# api/urls.py

from django.urls import path

# Import from the specific view files inside the 'views' package
from .views import user_views
from .views import post_views
from .views import blocked_words_views  

urlpatterns = [
    # Existing paths
    path('init/', user_views.InitView.as_view(), name='init_user'),
    path('posts/', post_views.PostListView.as_view(), name='post_list_create'),
    path('admin/blocked-words/', 
         blocked_words_views.BlockedWordsView.as_view(), 
         name='admin-blocked-words'),
]