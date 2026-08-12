from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('rooms', views.ChatRoomViewSet, basename='chat-room')

urlpatterns = [
    path('files/<uuid:message_id>/', views.ChatFileView.as_view(), name='chat-file'),
    *router.urls,
]
