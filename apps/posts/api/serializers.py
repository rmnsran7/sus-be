# apps/posts/api/serializers.py

from rest_framework import serializers
from ..models import Post, PostImage

class PostImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostImage
        fields = ['image_url', 'is_text_image']

class PostListSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.name', read_only=True)
    images = PostImageSerializer(many=True, read_only=True)
    
    class Meta:
        model = Post
        fields = ['post_number', 'user_name', 'text_content', 'status', 'posted_at', 'images']

class PostCreateSerializer(serializers.Serializer):
    text_content = serializers.CharField(max_length=2200, min_length=1)