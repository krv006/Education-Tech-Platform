from django.urls import path

from . import views

urlpatterns = [
    path('token/', views.RoomTokenView.as_view(), name='room-token'),
    path('leave/', views.RoomLeaveView.as_view(), name='room-leave'),
]
