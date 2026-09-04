"""Quizzes views — yupqa qatlam: HTTP <-> service/selector.

Biznes-logika services.py da, ko'rish huquqi selectors.py da, ruxsatlar
apps.core.permissions registry'sida.
"""
from rest_framework import generics, status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.core.permissions import RequirePerm

from . import selectors, services
from .models import Quiz
from .serializers import (
    AIQuizDraftRequestSerializer,
    AttemptListSerializer,
    AttemptResultSerializer,
    AttemptSubmitSerializer,
    QuizCreateSerializer,
    QuizDetailSerializer,
    QuizListSerializer,
    QuizTakeSerializer,
)

_STAFF_ROLES = (User.Role.TEACHER, User.Role.ADMIN, User.Role.SUPER_ADMIN)


def _get_quiz(user: User, pk) -> Quiz:
    """Faqat foydalanuvchi ko'rishga haqli test qaytariladi — aks holda
    boshqa kursning testi ko'rinmasin (queryset scoped, 404, apps.lessons
    bilan bir xil naqsh)."""
    try:
        return selectors.quizzes_for(user).get(pk=pk)
    except (Quiz.DoesNotExist, ValueError, TypeError):
        raise NotFound('Test topilmadi.')


class QuizListCreateView(generics.ListCreateAPIView):
    def get_permissions(self):
        perm = 'quiz.create' if self.request.method == 'POST' else 'quiz.view'
        return [RequirePerm(perm)()]

    def get_queryset(self):
        return selectors.quizzes_for(self.request.user)

    def get_serializer_class(self):
        return QuizListSerializer

    def create(self, request, *args, **kwargs):
        serializer = QuizCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        quiz = services.create_quiz(
            teacher=request.user, course=data['course'], lesson=data.get('lesson'),
            title=data['title'], description=data.get('description', ''),
            due_at=data.get('due_at'), opens_at=data.get('opens_at'), questions=data['questions'],
        )
        return Response(QuizDetailSerializer(quiz).data, status=status.HTTP_201_CREATED)


class QuizDetailView(APIView):
    def get_permissions(self):
        perm = 'quiz.create' if self.request.method == 'DELETE' else 'quiz.view'
        return [RequirePerm(perm)()]

    def get(self, request, pk):
        quiz = _get_quiz(request.user, pk)
        if request.user.role in _STAFF_ROLES:
            return Response(QuizDetailSerializer(quiz).data)
        return Response(QuizTakeSerializer(quiz).data)

    def delete(self, request, pk):
        quiz = _get_quiz(request.user, pk)
        services.delete_quiz(teacher=request.user, quiz=quiz)
        return Response(status=status.HTTP_204_NO_CONTENT)


class QuizAttemptListCreateView(APIView):
    def get_permissions(self):
        perm = 'quiz.attempt' if self.request.method == 'POST' else 'quiz.view'
        return [RequirePerm(perm)()]

    def get(self, request, pk):
        quiz = _get_quiz(request.user, pk)
        attempts = selectors.attempts_for(request.user, quiz)
        return Response(AttemptListSerializer(attempts, many=True).data)

    def post(self, request, pk):
        quiz = _get_quiz(request.user, pk)
        serializer = AttemptSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attempt = services.submit_attempt(
            student=request.user, quiz=quiz, answers=serializer.validated_data['answers'],
        )
        return Response(AttemptResultSerializer(attempt).data, status=status.HTTP_201_CREATED)


class AIQuizDraftView(APIView):
    """O'qituvchi: o'tilgan darslar asosida AI test qoralamasi (bazaga
    yozilmaydi — tahrirlab, POST /quizzes/ orqali o'zi yaratadi)."""

    permission_classes = [RequirePerm('quiz.create')]
    throttle_scope = 'ai'

    def post(self, request):
        from apps.lessons import services as lesson_services

        serializer = AIQuizDraftRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        draft = lesson_services.generate_ai_quiz_draft(
            teacher=request.user, course_id=data['course'],
            lesson_ids=data.get('lesson_ids'), question_count=data['question_count'],
        )
        return Response(draft)
