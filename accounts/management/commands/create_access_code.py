"""
`python manage.py create_access_code <code> --name "Admin" --role admin`

Kamida bitta admin kirish kodi yaratish uchun (Firestore seed page kodlar
yaratmasdi — kodlar admin panel orqali qo'shilardi). Worker login esa `staff`
jadvalidagi tabel raqami orqali ishlaydi.
"""

from django.core.management.base import BaseCommand

from accounts.models import AccessCode
from common.timeutil import now_ms


class Command(BaseCommand):
    help = "Admin/developer kirish kodi yaratadi yoki yangilaydi"

    def add_arguments(self, parser):
        parser.add_argument("code", type=str, help="Kirish kodi (masalan 778899)")
        parser.add_argument("--name", type=str, default="Administrator", help="Ko'rinadigan ism")
        parser.add_argument(
            "--role",
            type=str,
            default="admin",
            choices=["admin", "developer"],
            help="admin yoki developer",
        )

    def handle(self, *args, **options):
        code = options["code"].strip()
        role = options["role"]
        ts = now_ms()
        obj, created = AccessCode.objects.update_or_create(
            code=code,
            defaults={
                "displayName": options["name"],
                "role": role,
                "codeType": role,
                "isActive": True,
                "updatedAt": ts,
            },
        )
        if created:
            obj.createdAt = ts
            obj.save(update_fields=["createdAt"])
        action = "yaratildi" if created else "yangilandi"
        self.stdout.write(
            self.style.SUCCESS(f"[OK] {role} kodi '{code}' ({options['name']}) {action}.")
        )
