"""
`settings/lokomotivRaqamlari` hujjatini boshlang'ich ro'yxat bilan to'ldiradi.

Ishlatish:
    python manage.py seed_lokomotiv_raqamlari          # hujjat yo'q bo'lsa yaratadi
    python manage.py seed_lokomotiv_raqamlari --force   # borini ham qayta yozadi

Hujjat yaratilgach — ASOSIY manba o'sha bo'ladi. Admin uni API orqali
(`PATCH /api/settings/lokomotivRaqamlari/`) o'zgartirsa, bu buyruq boshqa
ishlatilmaydi (`--force` siz mavjud ro'yxatga tegmaydi).
"""

from django.core.management.base import BaseCommand

from catalog.lokomotiv_raqamlar import (
    LOKOMOTIV_RAQAM_FIELD,
    LOKOMOTIV_RAQAM_SETTING_KEY,
    normalize_raqam,
)
from catalog.models import Setting
from catalog.reference import LOKOMOTIV_RAQAMLARI
from common.timeutil import now_ms


class Command(BaseCommand):
    help = "settings/lokomotivRaqamlari hujjatini boshlang'ich ro'yxat bilan to'ldiradi"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Mavjud ro'yxat ustiga qayta yozadi (ehtiyot bo'ling)",
        )

    def handle(self, *args, **options):
        raqamlar = [normalize_raqam(r) for r in LOKOMOTIV_RAQAMLARI if normalize_raqam(r)]

        setting = Setting.objects.filter(pk=LOKOMOTIV_RAQAM_SETTING_KEY).first()
        mavjud = (
            isinstance(setting.data, dict) and setting.data.get(LOKOMOTIV_RAQAM_FIELD)
            if setting
            else None
        )

        if mavjud and not options["force"]:
            self.stdout.write(
                self.style.WARNING(
                    f"Hujjat allaqachon bor ({len(mavjud)} ta raqam) — tegilmadi. "
                    "Qayta yozish uchun: --force"
                )
            )
            return

        data = dict(setting.data) if setting and isinstance(setting.data, dict) else {}
        data[LOKOMOTIV_RAQAM_FIELD] = raqamlar

        Setting.objects.update_or_create(
            pk=LOKOMOTIV_RAQAM_SETTING_KEY,
            defaults={"data": data, "updatedAt": now_ms()},
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"settings/{LOKOMOTIV_RAQAM_SETTING_KEY} yozildi — "
                f"{len(raqamlar)} ta raqam ({len(set(raqamlar))} ta takrorsiz)."
            )
        )
