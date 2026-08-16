"""
Xodim o'chirilganda uning Face ID shabloni ham o'chadi.

API orqali o'chirishda buni `StaffViewSet.perform_destroy` bajaradi, lekin
Django admin panelidan yoki `shell` dan o'chirilsa ham shablon qolib ketmasligi
kerak: "egasiz" shablon ro'yxatda turaversa, u haqiqiy xodim o'rniga eng yaqin
nomzod bo'lib chiqib, o'sha odamning kirishiga xalaqit berishi mumkin edi.
"""

from __future__ import annotations

from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import FaceTemplate, Staff


@receiver(post_delete, sender=Staff)
def drop_face_template(sender, instance, **kwargs):
    code = (instance.tabelNumber or "").strip()
    if code:
        FaceTemplate.objects.filter(pk=code).delete()
