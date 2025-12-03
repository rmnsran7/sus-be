# apps/posts/api/views.py

import re # --- NEW: Import re for stripping tags ---
from django.db import transaction
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.pagination import PageNumberPagination

from ..models import Post
from ..tasks import process_and_publish_post
from apps.users.services import user_service
from apps.core.services.settings_service import get_global_settings
from apps.moderation.services.content_validator import check_for_blocked_words, analyze_with_llm
from .serializers import PostCreateSerializer, PostListSerializer

class PostCreateAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = PostCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # 1. USER VALIDATION
        user, _ = user_service.get_or_create_user(request)
        if not user or user.is_hard_blocked:
            return Response({"error": "You are not allowed to post."}, status=status.HTTP_403_FORBIDDEN)

        settings = get_global_settings()
        
        # --- NEW: Separate Raw and Clean Text ---
        raw_text_content = serializer.validated_data['text_content']
        # Strip all <tag> patterns to get clean text for DB and Moderation
        clean_text_content = re.sub(r'<[^>]+>', '', raw_text_content)
        
        # 2. MODERATION ANALYSIS (Use clean_text_content)
        final_status = Post.PostStatus.PROCESSING
        moderation_reason = ""
        raw_llm_response = None
        requires_payment = False
        is_promotional_post = False

        # check_for_blocked_words uses clean text so users can't evade filters with tags like b<b>ad</b>word
        if settings.enable_blocked_words_check and check_for_blocked_words(clean_text_content):
            final_status = Post.PostStatus.PENDING_MODERATION
            moderation_reason = "Post contains blocked words."
        
        elif settings.enable_llm_analysis:
            # Analyze the clean text for semantic meaning
            llm_result = analyze_with_llm(clean_text_content)
            raw_llm_response = llm_result.raw_data

            if llm_result.is_promotional:
                is_promotional_post = True
            
            if llm_result.is_harmful:
                final_status = Post.PostStatus.PENDING_MODERATION
                moderation_reason = "This message may contain sensitive content and is pending review."
            elif llm_result.is_spam:
                final_status = Post.PostStatus.PENDING_MODERATION
                moderation_reason = "This message has been flagged as potential spam and is pending review."
            elif is_promotional_post and settings.charge_for_promotional_posts:
                final_status = Post.PostStatus.AWAITING_PAYMENT
                moderation_reason = "Message marked as promotional. Payment required to proceed."
                requires_payment = True

        # 3. ATOMIC ACTION (Create Post & Dispatch Task)
        post = None
        try:
            with transaction.atomic():
                post = Post.objects.create(
                    user=user,
                    text_content=clean_text_content, # --- SAVE CLEAN TEXT TO DB ---
                    post_number=Post.get_next_post_number(),
                    submission_ip=user_service.get_client_ip(request),
                    submission_user_agent=request.META.get('HTTP_USER_AGENT', '')[:255],
                    status=final_status,
                    is_promotional=is_promotional_post,
                    llm_moderation_response=raw_llm_response,
                    moderation_reason=moderation_reason
                )

                if final_status == Post.PostStatus.PROCESSING:
                    # --- PASS RAW CONTENT (with tags) TO TASK ---
                    process_and_publish_post.delay(post.id, raw_content=raw_text_content)

        except Exception as e:
            print(f"ERROR during post creation transaction: {e}")
            return Response({"error": "An internal error occurred while submitting your post."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 4. RETURN RESPONSE
        if requires_payment:
            fee = settings.promotional_post_fee
            return Response({
                "message": "This post is promotional. Please complete payment to continue.", 
                "payment_required": True,
                "amount": fee,
                "currency": "cad",
                "post_id": post.id 
            }, status=status.HTTP_402_PAYMENT_REQUIRED)

        if final_status == Post.PostStatus.PENDING_MODERATION:
            return Response({"message": moderation_reason}, status=status.HTTP_202_ACCEPTED)

        return Response(
            {"message": "Your post has been submitted and will appear shortly!"},
            status=status.HTTP_202_ACCEPTED
        )

# ... (StandardResultsSetPagination and RecentPostsListView remain unchanged)
class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50

class RecentPostsListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = PostListSerializer
    pagination_class = StandardResultsSetPagination
    queryset = Post.objects.exclude(
        status=Post.PostStatus.AWAITING_PAYMENT
    ).select_related('user').order_by('-created_at')