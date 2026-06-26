"""
Model o'zgarishlarini avtomatik WebSocket'ga broadcast qiladi.

Har bir jadval uchun "topic" belgilangan. Yozuv saqlanganda/o'chirilganda
mos topic bo'yicha xabar yuboriladi — frontenddagi `pollSubscribe(..., wsTopics)`
shu topicni tinglab darhol qayta yuklaydi.

MUHIM:
  * `transaction.on_commit` — xabar faqat tranzaksiya commit bo'lgach yuboriladi,
    shunda klient qayta yuklaganda yangi ma'lumotni albatta ko'radi.
  * Submission o'zining boyroq broadcastiga ega (submissions/services.py), shuning
    uchun bu yerda ro'yxatga olinmaydi (dublikat bo'lmasligi uchun).
  * ActiveSession (presence) faqat login (create) va logout (delete) da broadcast
    qilinadi — har 20 soniyalik heartbeat (update) uchun emas.
"""

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from accounts.models import (
    AccessCode,
    ActiveSession,
    BlockedCode,
    DeviceLock,
    SecurityEvent,
    Staff,
)
from audit.models import AuditLog
from catalog.models import Approval, ClosedDay, Limit, Question, Setting, Variant

from .broadcast import broadcast

TOPICS = {
    AccessCode: "access_codes",
    Staff: "staff",
    BlockedCode: "blocked_codes",
    DeviceLock: "device_locks",
    ActiveSession: "presence",
    SecurityEvent: "security_events",
    Limit: "limits",
    Question: "questions",
    Variant: "variants",
    Setting: "settings",
    ClosedDay: "closed_days",
    Approval: "approvals",
    AuditLog: "audit_logs",
}


def _emit(sender, action: str, pk) -> None:
    topic = TOPICS.get(sender)
    if not topic:
        return
    payload = {"topic": topic, "action": action, "id": str(pk)}
    transaction.on_commit(lambda: broadcast(payload))


@receiver(post_save)
def on_save(sender, instance, created, **kwargs):
    if sender not in TOPICS:
        return
    # presence: faqat yangi sessiya (login); heartbeat update'larini o'tkazib yuboramiz
    if sender is ActiveSession and not created:
        return
    _emit(sender, "create" if created else "update", instance.pk)


@receiver(post_delete)
def on_delete(sender, instance, **kwargs):
    if sender not in TOPICS:
        return
    _emit(sender, "delete", instance.pk)
