"""
Face ID shablonlarini saqlangan kadrlardan QAYTA quradi.

Qachon kerak bo'ladi: `accounts/face.py` dagi algoritm o'zgarsa (masalan
LBP_TOLERANCE yoki blok o'lchami) va TEMPLATE_VERSION ko'tarilsa. Shunda eski
shablonlar ishlatilmay qo'yiladi va Face ID vaqtincha ishlamaydi (foydalanuvchi
parol bilan kiraveradi). Bu buyruq ularni qayta hisoblaydi — HECH KIMDAN
qaytadan surat so'ralmaydi.

    python manage.py rebuild_face_templates          # faqat eskirganlarini
    python manage.py rebuild_face_templates --all    # hammasini majburan
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from accounts import face
from accounts.models import FaceTemplate
from common.timeutil import now_ms


class Command(BaseCommand):
    help = "Face ID shablonlarini saqlangan kadrlardan qayta quradi."

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Versiyasidan qat'i nazar hamma shablonni qayta quradi.",
        )

    def handle(self, *args, **options):
        query = FaceTemplate.objects.all()
        if not options["all"]:
            query = query.exclude(version=face.TEMPLATE_VERSION)

        total = rebuilt = skipped = 0
        for record in query:
            total += 1
            raw_samples = record.sample_list()
            if not raw_samples:
                skipped += 1
                self.stderr.write(
                    f"  {record.code}: saqlangan kadr yo'q — qayta rasm olish kerak."
                )
                continue

            vectors = face.templates_from_raw(raw_samples)
            if not vectors:
                skipped += 1
                self.stderr.write(f"  {record.code}: kadrlar buzuq.")
                continue

            record.vectors = "\n".join(vectors)
            record.sampleCount = len(vectors)
            record.version = face.TEMPLATE_VERSION
            record.updatedAt = now_ms()
            record.save(
                update_fields=["vectors", "sampleCount", "version", "updatedAt"]
            )
            rebuilt += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Tekshirildi: {total} ta · qayta qurildi: {rebuilt} ta · "
                f"o'tkazib yuborildi: {skipped} ta"
            )
        )
