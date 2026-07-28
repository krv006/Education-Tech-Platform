from django.urls import path

from . import views

urlpatterns = [
    path('token/', views.RoomTokenView.as_view(), name='room-token'),
    path('leave/', views.RoomLeaveView.as_view(), name='room-leave'),
    path('attention/', views.AttentionView.as_view(), name='room-attention'),
    path('focus/', views.FocusEventView.as_view(), name='room-focus'),
    path('allow-share/', views.AllowShareView.as_view(), name='room-allow-share'),
]
