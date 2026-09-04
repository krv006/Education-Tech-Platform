from django.urls import path

from . import views

urlpatterns = [
    path('ai-draft/', views.AIQuizDraftView.as_view(), name='quiz-ai-draft'),
    path('', views.QuizListCreateView.as_view(), name='quiz-list-create'),
    path('<uuid:pk>/', views.QuizDetailView.as_view(), name='quiz-detail'),
    path('<uuid:pk>/attempts/', views.QuizAttemptListCreateView.as_view(), name='quiz-attempts'),
]
