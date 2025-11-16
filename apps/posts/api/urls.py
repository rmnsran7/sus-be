# apps/posts/api/urls.py

from django.urls import path
from .views import PostCreateAPIView, RecentPostsListView

app_name = 'posts-api'

urlpatterns = [
    path('create/', PostCreateAPIView.as_view(), name='create-post'),
    path('recent/', RecentPostsListView.as_view(), name='recent-posts'),
]