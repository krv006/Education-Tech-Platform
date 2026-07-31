from django.urls import path

from . import views

urlpatterns = [
    path('assignments/', views.AssignmentListCreateView.as_view(), name='hw-assignments'),
    path('assignments/<uuid:assignment_id>/', views.AssignmentDetailView.as_view(), name='hw-assignment'),
    path('assignments/<uuid:assignment_id>/file/', views.AssignmentFileView.as_view(), name='hw-assignment-file'),
    path('assignments/<uuid:assignment_id>/submit/', views.SubmitView.as_view(), name='hw-submit'),
    path('submissions/<uuid:submission_id>/', views.SubmissionDetailView.as_view(), name='hw-submission'),
    path('submissions/<uuid:submission_id>/file/', views.SubmissionFileView.as_view(), name='hw-submission-file'),
    path('submissions/<uuid:submission_id>/recheck/', views.RecheckView.as_view(), name='hw-recheck'),
]
