from django.urls import path

from . import views

urlpatterns = [
    path('token/', views.RoomTokenView.as_view(), name='room-token'),
    path('leave/', views.RoomLeaveView.as_view(), name='room-leave'),
    path('attention/', views.AttentionView.as_view(), name='room-attention'),
    path('focus/', views.FocusEventView.as_view(), name='room-focus'),
    path('allow-share/', views.AllowShareView.as_view(), name='room-allow-share'),
    path('request-mic/', views.RequestMicView.as_view(), name='room-request-mic'),
    path('grant-mic/', views.GrantMicView.as_view(), name='room-grant-mic'),
    path('deny-mic/', views.DenyMicView.as_view(), name='room-deny-mic'),
    path('invite/', views.InviteView.as_view(), name='room-invite'),
    path('ban/', views.BanView.as_view(), name='room-ban'),
    path('unban/', views.UnbanView.as_view(), name='room-unban'),
]
