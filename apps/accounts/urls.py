from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import views

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', TokenObtainPairView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('me/', views.MeView.as_view(), name='me'),
    path('children/', views.ChildCreateView.as_view(), name='child-create'),
    path('links/', views.LinkListView.as_view(), name='link-list'),
    path('links/request/', views.LinkRequestView.as_view(), name='link-request'),
    path('links/<int:pk>/respond/', views.LinkRespondView.as_view(), name='link-respond'),
    path('consents/', views.ConsentListCreateView.as_view(), name='consents'),
]
