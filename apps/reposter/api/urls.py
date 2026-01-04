from django.urls import path
from ..views import ReposterStartView, ReposterStatusView

urlpatterns = [
    # Matches /api/reposter/?link=...
    path('', ReposterStartView.as_view(), name='reposter-start'),
    path('status/<str:task_id>/', ReposterStatusView.as_view(), name='reposter-status'),
]