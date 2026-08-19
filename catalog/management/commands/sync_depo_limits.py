"""
Депо лимитларини қайта ҳисоблаш: асосий + қўшимча.

Одатда бу керак эмас — ҳисоб `settings/depoLimits` ёки
`settings/depoQoshimchaLimits` ҳужжатига ҳар ёзилганда автоматик бажарилади
(`catalog/views.py` -> `SettingViewSet`). Бу буйруқ фақат қўл билан текшириш
ва деплойдан кейин бир марта юритиш учун:

    python manage.py sync_depo_limits            # ҳисоблаб ёзади
    python manage.py sync_depo_limits --dry-run  # фақат кўрсатади, ёзмайди

Ҳеч қандай миграция талаб қилмайди: `Setting.data` — JSON ҳужжат.
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from catalog.depo_limits import MAIN_KEY, sync_depo_limits
from catalog.models import Setting


class Command(BaseCommand):
    help = "Қўшимча депо лимитини асосий лимитга қўшиб қўяди (жами қиймат)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Ҳеч нарса ёзмайди, фақат жорий ҳолатни кўрсатади.",
        )

    def handle(self, *args, **options):
        before = Setting.objects.filter(pk=MAIN_KEY).first()
        items = (before.data or {}).get("items", []) if before else []

        if options["dry_run"]:
            self.stdout.write(f"{MAIN_KEY}: {len(items)} ёзув (ёзилмади)")
            self.stdout.write(json.dumps(items, ensure_ascii=False, indent=2))
            return

        changed = sync_depo_limits()
        after = Setting.objects.filter(pk=MAIN_KEY).first()
        count = len((after.data or {}).get("items", [])) if after else 0

        if changed:
            self.stdout.write(self.style.SUCCESS(f"Ҳисобланди — {count} ёзув янгиланди."))
        else:
            self.stdout.write("Ўзгариш йўқ — жами лимитлар аллақачон тўғри.")
