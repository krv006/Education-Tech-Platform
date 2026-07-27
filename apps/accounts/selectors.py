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
