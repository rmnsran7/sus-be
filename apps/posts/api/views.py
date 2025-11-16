# apps/posts/api/views.py

from django.db import transaction
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
# --- NEW: Import the pagination class ---
from rest_framework.pagination import PageNumberPagination

from ..models import Post
from ..tasks import process_and_publish_post
from apps.users.services import user_service
from apps.core.services.settings_service import get_global_settings
from apps.moderation.services.content_validator import check_for_blocked_words, analyze_with_llm
from .serializers import PostCreateSerializer, PostListSerializer

# --- NO CHANGES TO PostCreateAPIView ---
# This view is already correctly set up from our previous changes.
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
        text_content = serializer.validated_data['text_content']
        
        # 2. MODERATION ANALYSIS
        final_status = Post.PostStatus.PROCESSING
        moderation_reason = ""
        raw_llm_response = None
        requires_payment = False
        is_promotional_post = False

        if settings.enable_blocked_words_check and check_for_blocked_words(text_content):
            final_status = Post.PostStatus.PENDING_MODERATION
            moderation_reason = "Post contains blocked words."
        
        elif settings.enable_llm_analysis:
            llm_result = analyze_with_llm(text_content)
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
                    text_content=text_content,
                    post_number=Post.get_next_post_number(),
                    submission_ip=user_service.get_client_ip(request),
                    submission_user_agent=request.META.get('HTTP_USER_AGENT', '')[:255],
                    status=final_status,
                    is_promotional=is_promotional_post,
                    llm_moderation_response=raw_llm_response,
                    moderation_reason=moderation_reason
                )

                if final_status == Post.PostStatus.PROCESSING:
                    process_and_publish_post.delay(post.id)

        except Exception as e:
            print(f"ERROR during post creation transaction: {e}")
            return Response({"error": "An internal error occurred while submitting your post."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 4. RETURN RESPONSE BASED ON OUTCOME
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

# --- NEW: A standard pagination class for the infinite scroll ---
class StandardResultsSetPagination(PageNumberPagination):
    """
    Configures the pagination for the post feed. The frontend will request
    pages like ?page=1, ?page=2, etc.
    """
    page_size = 10  # Number of posts to return per page
    page_size_query_param = 'page_size' # Allows frontend to override page size if needed
    max_page_size = 50

# --- MODIFIED RecentPostsListView ---
class RecentPostsListView(generics.ListAPIView):
    """
    Provides a paginated list of all recent posts that are not waiting for payment.
    This includes posts that are posted, processing, failed, or pending moderation,
    giving the user immediate visibility into their submissions.
    """
    permission_classes = [AllowAny]
    serializer_class = PostListSerializer
    # --- CHANGE 1: Add the pagination class ---
    pagination_class = StandardResultsSetPagination

    # --- CHANGE 2: Update the queryset to show more statuses ---
    # We exclude posts awaiting payment because they are in an incomplete state.
    # The `select_related('user')` is a performance optimization to fetch the user
    # data in the same database query.
    queryset = Post.objects.exclude(
        status=Post.PostStatus.AWAITING_PAYMENT
    ).select_related('user').order_by('-created_at')