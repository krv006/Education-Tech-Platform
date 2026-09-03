"""Accounts selector layer — barcha o'quvchi (read-only) querylar shu yerda.

Qoida: ko'rish huquqi (kim nimani ko'radi) shu qatlamda kodlanadi, view'da emas.
"""
from django.db.models import Q, QuerySet

from .models import Consent, ParentChildLink, User


def links_for_user(user: User) -> QuerySet[ParentChildLink]:
    return ParentChildLink.objects.filter(
        Q(parent=user) | Q(student=user)
    ).select_related('parent', 'student')


def approved_children(parent: User) -> QuerySet[User]:
    return User.objects.filter(
        parent_links__parent=parent,
        parent_links__status=ParentChildLink.Status.APPROVED,
    )


def is_linked(parent: User, student) -> bool:
    return ParentChildLink.objects.filter(
        parent=parent, student=student, status=ParentChildLink.Status.APPROVED
    ).exists()


def consents_for_parent(parent: User) -> QuerySet[Consent]:
    return Consent.objects.filter(
        student__parent_links__parent=parent,
        student__parent_links__status=ParentChildLink.Status.APPROVED,
    ).select_related('student')


def teacher_rating_stats(teacher: User) -> dict:
    """O'qituvchining BARCHA darslari bo'yicha o'rtacha ball va baholar soni.

    apps.lessons ichidan lazy import — apps.accounts'ni apps.lessons'ga
    bog'lab qo'ymaslik uchun (LessonRating faqat shu funksiya ichida kerak).
    """
    from django.db.models import Avg, Count

    from apps.lessons.models import LessonRating

    agg = LessonRating.objects.filter(lesson__course__teacher=teacher).aggregate(
        avg_rating=Avg('stars'), rating_count=Count('id'),
    )
    avg = agg['avg_rating']
    return {
        'avg_rating': round(avg, 2) if avg is not None else None,
        'rating_count': agg['rating_count'],
    }


def teacher_list() -> QuerySet[User]:
    """Admin uchun: barcha o'qituvchilar (reyting statistikasi bilan, UserSerializer orqali)."""
    return User.objects.filter(role=User.Role.TEACHER).order_by('first_name', 'last_name')


def pending_teachers() -> QuerySet[User]:
    """Admin tasdig'ini kutayotgan (hali tasdiqlanmagan) o'qituvchilar."""
    return User.objects.filter(role=User.Role.TEACHER, is_approved=False).order_by('-created_at')
