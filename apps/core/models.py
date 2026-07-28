"""Core model layer: UUID + timestamp base, soft delete, audit log.

Har bir domen modeli shu qatlamdan meros oladi — ID'lar taxmin qilib bo'lmaydigan
(UUID), har bir yozuvda created/updated vaqti bor, o'chirish esa default holatda
"yumshoq" (ma'lumot yo'qolmaydi — audit va huquqiy talablar uchun).
"""
import uuid

from django.conf import settings
from django.db.models import (
    SET_NULL,
    BooleanField,
    CharField,
    DateTimeField,
    ForeignKey,
    GenericIPAddressField,
    Index,
    JSONField,
    Manager,
    Model,
    QuerySet,
    UUIDField,
)
from django.utils import timezone


class TimeStampedUUIDModel(Model):
    id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = DateTimeField(auto_now_add=True, db_index=True)
    updated_at = DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteQuerySet(QuerySet):
    def delete(self):
        return super().update(is_deleted=True, deleted_at=timezone.now())

    def hard_delete(self):
        return super().delete()


class SoftDeleteManager(Manager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_deleted=False)


class SoftDeleteModel(Model):
    """delete() belgilaydi, o'chirmaydi. `objects` faqat tiriklarni ko'radi,
    `all_objects` hammasini (admin/audit uchun)."""

    is_deleted = BooleanField(default=False)
    deleted_at = DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = Manager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at'])

    def hard_delete(self, using=None, keep_parents=False):
        return super().delete(using=using, keep_parents=keep_parents)


class AuditLog(TimeStampedUUIDModel):
    """FRD: security.audit — har bir muhim harakat kim, qachon, nima ustida.

    Yozish faqat apps.core.audit.record() orqali (service qatlamidan).
    """

    actor = ForeignKey(
        settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True,
        related_name='audit_logs',
    )
    action = CharField(max_length=64, db_index=True)  # masalan: 'link.approve'
    target_type = CharField(max_length=64, blank=True)
    target_id = CharField(max_length=64, blank=True)
    meta = JSONField(default=dict, blank=True)
    ip_address = GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [Index(fields=['target_type', 'target_id'])]

    def __str__(self):
        actor = self.actor.username if self.actor else 'system'
        return f'{actor} · {self.action} · {self.created_at:%Y-%m-%d %H:%M}'
