"""
`python manage.py seed` — boshlang'ich ma'lumotlarni to'ldiradi.

Firestore `app/seed/page.tsx` + `lib/data/uzellar.ts` ekvivalenti:
  * uzellar / zapravkalar (reference)
  * settings/global
  * default questions (lokomotiv)

Idempotent: qayta ishga tushirsa dublikat yaratmaydi (update_or_create).
"""

from django.core.management.base import BaseCommand

from catalog.models import Question, Setting, Uzel, Zapravka
from catalog.reference import (
    DEFAULT_QUESTIONS,
    SETTINGS_GLOBAL,
    UZELLAR,
    ZAPRAVKALAR,
)
from common.timeutil import now_ms


class Command(BaseCommand):
    help = "Boshlang'ich ma'lumotlarni (uzellar, zapravkalar, settings, questions) yuklaydi"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-questions",
            action="store_true",
            help="Default savollarni qayta yozadi (avval lokomotiv default savollarni o'chiradi)",
        )

    def handle(self, *args, **options):
        ts = now_ms()

        # 1) Uzellar
        for u in UZELLAR:
            Uzel.objects.update_or_create(id=u["id"], defaults=u)
        self.stdout.write(self.style.SUCCESS(f"[OK] {len(UZELLAR)} ta uzel"))

        # 2) Zapravkalar
        for z in ZAPRAVKALAR:
            Zapravka.objects.update_or_create(id=z["id"], defaults=z)
        self.stdout.write(self.style.SUCCESS(f"[OK] {len(ZAPRAVKALAR)} ta zapravka"))

        # 3) settings/global
        Setting.objects.update_or_create(
            key="global",
            defaults={"data": SETTINGS_GLOBAL, "updatedAt": ts},
        )
        self.stdout.write(self.style.SUCCESS("[OK] settings/global"))

        # 4) Default questions
        if options["reset_questions"]:
            Question.objects.filter(
                category="lokomotiv",
                fieldKey__in=[q["fieldKey"] for q in DEFAULT_QUESTIONS],
            ).delete()

        created = 0
        for q in DEFAULT_QUESTIONS:
            obj, was_created = Question.objects.get_or_create(
                category=q["category"],
                fieldKey=q["fieldKey"],
                defaults={**q, "createdAt": ts, "updatedAt": ts},
            )
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f"[OK] {created} ta yangi savol (jami {len(DEFAULT_QUESTIONS)})"))

        self.stdout.write(self.style.SUCCESS("Seed tugadi."))
