from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('courses', views.CourseViewSet, basename='course')
router.register('lessons', views.LessonViewSet, basename='lesson')
router.register('attendance', views.AttendanceViewSet, basename='attendance')

urlpatterns = router.urls
