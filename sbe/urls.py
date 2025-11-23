from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('sengh/', admin.site.urls),
    path('api/v1/', include('api.urls')), 
    path('api/users/', include('apps.users.api.urls', namespace='users-api')), 
    path('api/posts/', include('apps.posts.api.urls', namespace='posts-api')),
    path('api/payments/', include('apps.payments.api.urls', namespace='payments-api'))
]
