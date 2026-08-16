"""
Face ID uchun avtomatik testlar.

Ishga tushirish (bazaga TEGMAYDI — Django vaqtinchalik test bazasi yaratadi):

    python manage.py test accounts.tests_face -v 2

Tekshiriladi:
  * yangi xodimga surat majburiyligi;
  * `/staff/` ro'yxati AVVALGIDEK qolgani (suratsiz, faqat bayroqlar qo'shilgan);
  * to'g'ri odam kiritilishi, begona rad etilishi;
  * takroriy (replay) kadrlar rad etilishi;
  * bloklangan kod / bloklangan qurilma Face ID orqali ham o'tolmasligi;
  * Face ID xatosi qurilmaning PAROL urinishlari hisobini o'zgartirmasligi.
"""

from __future__ import annotations

import base64
import random

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from catalog.models import Uzel, Zapravka

from . import face, face_service
from .authentication import create_access_token
from .models import AccessCode, BlockedCode, DeviceLock, FaceTemplate, Staff
from .serializers import AccessCodeSerializer, StaffSerializer

N = face.FACE_SIZE
TINY_JPEG = "data:image/jpeg;base64," + base64.b64encode(b"fake-jpeg-bytes").decode()


def _person(pid: int) -> dict:
    r = random.Random(1000 + pid)
    return {
        "ex": r.uniform(-5, 5),
        "ey": r.uniform(-5, 5),
        "eye_r": r.uniform(16, 34),
        "mouth_w": r.uniform(10, 22),
        "mouth_y": r.uniform(0.68, 0.78),
        "brow": r.uniform(2, 9),
        "skin": r.uniform(120, 185),
        "face_w": r.uniform(0.30, 0.38),
        "texture": [
            (r.randrange(N), r.randrange(N), r.randrange(3, 9), r.randint(-35, 35))
            for _ in range(70)
        ],
    }


def frame(pid: int, nonce: int = 0, noise: int = 6, light: int = 0) -> str:
    """Sintetik yuz kadri (96x96 kulrang) -> base64. Har chaqiruvda biroz farqli."""
    p = _person(pid)
    rnd = random.Random((pid + 1) * 7919 + nonce)
    px = bytearray(N * N)
    for y in range(N):
        for x in range(N):
            dx = (x - N / 2) / (N * p["face_w"])
            dy = (y - N / 2) / (N * 0.44)
            inside = dx * dx + dy * dy < 1
            px[y * N + x] = int(p["skin"] - 12 * (dx * dx + dy * dy)) if inside else 38
    for tx, ty, tr, tv in p["texture"]:
        for y in range(max(0, ty - tr), min(N, ty + tr)):
            for x in range(max(0, tx - tr), min(N, tx + tr)):
                if (x - tx) ** 2 + (y - ty) ** 2 <= tr * tr:
                    px[y * N + x] = max(0, min(255, px[y * N + x] + tv // 2))
    for y in range(N):
        for x in range(N):
            value = None
            for cx in (N * 0.34 + p["ex"], N * 0.66 + p["ex"]):
                if (x - cx) ** 2 + (y - (N * 0.40 + p["ey"])) ** 2 < p["eye_r"]:
                    value = 40
            if abs(y - (N * 0.33 + p["ey"] - p["brow"])) < 2.5 and N * 0.24 < x < N * 0.76:
                value = 65
            if abs(x - N / 2) < p["mouth_w"] and abs(y - N * p["mouth_y"]) < 3:
                value = 58
            if value is not None:
                px[y * N + x] = value
    out = bytes(
        max(0, min(255, value + light + rnd.randint(-noise, noise))) for value in px
    )
    return base64.b64encode(out).decode("ascii")


def frames(pid: int, count: int = 3, base_nonce: int = 0) -> list[str]:
    return [frame(pid, nonce=base_nonce + i, noise=8) for i in range(count)]


class FaceIdTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        uzel = Uzel.objects.create(id="toshkent", name="Toshkent")
        Zapravka.objects.create(
            id="toshkent-yo", uzelId=uzel, name="Toshkent YO", slug="toshkent-yo"
        )

    def setUp(self):
        cache.clear()  # throttle / cooldown hisoblagichlari tozalansin
        self.client = APIClient()

    # ── yordamchilar ────────────────────────────────────────────────────────
    def _create_staff(self, tabel: str, pid: int, name: str = "Test Xodim"):
        serializer = StaffSerializer(
            data={
                "erju": "Toshkent",
                "zapravka": "Toshkent YO",
                "tabelNumber": tabel,
                "fullName": name,
                "photo": TINY_JPEG,
                "faceSamples": frames(pid, 3, base_nonce=0),
            },
            context={"request": None},
        )
        serializer.is_valid(raise_exception=True)
        return serializer.save()

    def _face_login(self, pid: int, device_id: str = "dev-1", nonce: int = 500):
        return self.client.post(
            "/api/auth/face-login/",
            {"samples": frames(pid, 3, base_nonce=nonce), "deviceId": device_id},
            format="json",
        )

    # ── testlar ─────────────────────────────────────────────────────────────
    def test_photo_is_required_for_new_staff(self):
        serializer = StaffSerializer(
            data={
                "erju": "Toshkent",
                "zapravka": "Toshkent YO",
                "tabelNumber": "9001",
                "fullName": "Suratsiz",
            },
            context={"request": None},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        with self.assertRaises(Exception):
            serializer.save()
        self.assertFalse(Staff.objects.filter(tabelNumber="9001").exists())

    def test_staff_list_has_no_photo_but_has_flags(self):
        self._create_staff("1001", 1)
        token = create_access_token(
            {"code": "adm", "role": "admin", "displayName": "Admin"}
        )["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = self.client.get("/api/staff/?limit=10")
        self.assertEqual(response.status_code, 200)
        row = response.json()["results"][0]
        self.assertNotIn("photo", row)          # surat ro'yxatga TUSHMAYDI
        self.assertNotIn("faceSamples", row)    # biometrik ma'lumot ham
        self.assertTrue(row["hasPhoto"])
        self.assertTrue(row["hasFace"])
        # Surat alohida endpointda bor
        detail = self.client.get(f"/api/staff/{row['id']}/photo/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["photo"], TINY_JPEG)

    def test_face_template_never_leaves_the_server(self):
        self._create_staff("1002", 2)
        token = create_access_token(
            {"code": "adm", "role": "admin", "displayName": "Admin"}
        )["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        body = self.client.get("/api/staff/?limit=10").content.decode()
        record = FaceTemplate.objects.get(code="1002")
        self.assertNotIn(record.vector_list()[0][:40], body)

    def test_correct_person_logs_in(self):
        self._create_staff("1003", 3, name="Ali Valiyev")
        for pid in (4, 5, 6, 7):  # boshqa xodimlar (jamoa)
            self._create_staff(f"20{pid}", pid)

        response = self._face_login(3)
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertIn("token", data)
        self.assertEqual(data["session"]["code"], "1003")
        self.assertEqual(data["session"]["role"], "worker")
        self.assertEqual(data["session"]["stationId"], "toshkent-yo")
        self.assertEqual(data["session"]["displayName"], "Ali Valiyev")

    def test_stranger_is_rejected(self):
        for pid in (3, 4, 5, 6, 7):
            self._create_staff(f"30{pid}", pid)
        response = self._face_login(777)
        self.assertEqual(response.status_code, 401, response.content)

    def test_replay_of_identical_frames_is_rejected(self):
        self._create_staff("1004", 8)
        one = frame(8, nonce=1, noise=8)
        response = self.client.post(
            "/api/auth/face-login/",
            {"samples": [one, one, one], "deviceId": "dev-replay"},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["reason"], "replay")

    def test_blocked_code_cannot_pass_face_id(self):
        self._create_staff("1005", 9)
        for pid in (10, 11, 12, 13):
            self._create_staff(f"40{pid}", pid)
        BlockedCode.objects.create(code="1005")
        response = self._face_login(9)
        self.assertEqual(response.status_code, 403, response.content)

    def test_blocked_device_cannot_pass_face_id(self):
        self._create_staff("1006", 14)
        DeviceLock.objects.create(deviceId="dev-blocked", isBlocked=True, attempts=3)
        response = self._face_login(14, device_id="dev-blocked")
        self.assertEqual(response.status_code, 403, response.content)

    def test_face_failure_does_not_touch_password_attempts(self):
        """Yuz tanilmasa ham foydalanuvchi PAROL bilan kira olishi shart."""
        for pid in (15, 21, 22, 23, 24):
            self._create_staff(f"70{pid}", pid)
        DeviceLock.objects.create(deviceId="dev-2", attempts=1)
        self._face_login(888, device_id="dev-2")
        lock = DeviceLock.objects.get(pk="dev-2")
        self.assertEqual(lock.attempts, 1)
        self.assertFalse(lock.isBlocked)

    def test_changing_tabel_moves_the_template(self):
        staff = self._create_staff("1008", 16)
        serializer = StaffSerializer(
            staff,
            data={"tabelNumber": "1009"},
            partial=True,
            context={"request": None},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        self.assertFalse(FaceTemplate.objects.filter(code="1008").exists())
        self.assertTrue(FaceTemplate.objects.filter(code="1009").exists())

    def test_outdated_templates_are_rebuilt_from_stored_frames(self):
        """Algoritm yangilanganda hech kimdan qayta surat so'ralmasin.

        `migrate` ham, `rebuild_face_templates` buyrug'i ham AYNAN shu yo'ldan
        boradi (`face.templates_from_raw`), shuning uchun bu test ikkalasini
        birdek qamrab oladi.
        """
        self._create_staff("1013", 19, name="Eski Shablon")
        for pid in (25, 26, 27, 28):
            self._create_staff(f"80{pid}", pid)

        # Eski versiyadagi (mos kelmaydigan) shablon holatiga keltiramiz.
        FaceTemplate.objects.all().update(version=face.TEMPLATE_VERSION - 1)
        self.assertEqual(face_service.load_enrolled(), [])
        self.assertEqual(self._face_login(19).status_code, 401)

        call_command("rebuild_face_templates", verbosity=0)

        record = FaceTemplate.objects.get(code="1013")
        self.assertEqual(record.version, face.TEMPLATE_VERSION)
        self.assertTrue(record.vector_list())
        response = self._face_login(19, nonce=600)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["session"]["code"], "1013")

    def test_deleting_staff_removes_the_template(self):
        staff = self._create_staff("1010", 17)
        token = create_access_token(
            {"code": "adm", "role": "admin", "displayName": "Admin"}
        )["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = self.client.delete(f"/api/staff/{staff.id}/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(FaceTemplate.objects.filter(code="1010").exists())

    def test_same_photo_cannot_be_used_twice(self):
        self._create_staff("1011", 18)
        serializer = StaffSerializer(
            data={
                "erju": "Toshkent",
                "zapravka": "Toshkent YO",
                "tabelNumber": "1012",
                "fullName": "Ikkinchi",
                "photo": TINY_JPEG,
                "faceSamples": frames(18, 3, base_nonce=0),  # AYNI kadrlar
            },
            context={"request": None},
        )
        serializer.is_valid(raise_exception=True)
        with self.assertRaises(Exception):
            serializer.save()


class AdminFaceIdTests(TestCase):
    """Admin (kirish kodi) uchun Face ID — "Бошқарув > Admin qo'shish" oqimi.

    Asosiy talab: admin ham xodim kabi yuz bilan kiradi, LEKIN oddiy xodim
    bilan hech qachon chalkashmaydi va faqat o'ziga biriktirilgan bo'limlarga
    tushadi.
    """

    @classmethod
    def setUpTestData(cls):
        uzel = Uzel.objects.create(id="toshkent", name="Toshkent")
        Zapravka.objects.create(
            id="toshkent-yo", uzelId=uzel, name="Toshkent YO", slug="toshkent-yo"
        )

    def setUp(self):
        cache.clear()
        self.client = APIClient()

    # ── yordamchilar ────────────────────────────────────────────────────────
    def _create_staff(self, tabel: str, pid: int, name: str = "Test Xodim"):
        serializer = StaffSerializer(
            data={
                "erju": "Toshkent",
                "zapravka": "Toshkent YO",
                "tabelNumber": tabel,
                "fullName": name,
                "photo": TINY_JPEG,
                "faceSamples": frames(pid, 3, base_nonce=0),
            },
            context={"request": None},
        )
        serializer.is_valid(raise_exception=True)
        return serializer.save()

    def _admin_data(self, code: str, pid: int | None, name: str, **extra) -> dict:
        data = {
            "code": code,
            "displayName": name,
            "role": "admin",
            "codeType": "admin",
            "isActive": True,
            **extra,
        }
        if pid is not None:
            data["photo"] = TINY_JPEG
            data["faceSamples"] = frames(pid, 3, base_nonce=0)
        return data

    def _create_admin(self, code: str, pid: int, name: str = "Test Admin", **extra):
        serializer = AccessCodeSerializer(
            data=self._admin_data(code, pid, name, **extra), context={"request": None}
        )
        serializer.is_valid(raise_exception=True)
        return serializer.save()

    def _face_login(self, pid: int, device_id: str = "dev-a", nonce: int = 500):
        return self.client.post(
            "/api/auth/face-login/",
            {"samples": frames(pid, 3, base_nonce=nonce), "deviceId": device_id},
            format="json",
        )

    # ── testlar ─────────────────────────────────────────────────────────────
    def test_photo_is_required_for_new_admin(self):
        serializer = AccessCodeSerializer(
            data=self._admin_data("adm1", None, "Suratsiz"), context={"request": None}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        with self.assertRaises(Exception):
            serializer.save()
        self.assertFalse(AccessCode.objects.filter(pk="adm1").exists())

    def test_developer_code_does_not_require_photo(self):
        """Bo'sh bazada birinchi kirish yo'li yopilib qolmasligi kerak."""
        serializer = AccessCodeSerializer(
            data={
                "code": "dev1",
                "displayName": "Dasturchi",
                "role": "developer",
                "codeType": "developer",
                "isActive": True,
            },
            context={"request": None},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        self.assertTrue(AccessCode.objects.filter(pk="dev1").exists())

    def test_admin_logs_in_by_face_with_own_sections(self):
        for pid in (31, 32, 33, 34):  # oddiy xodimlar (jamoa)
            self._create_staff(f"90{pid}", pid)
        self._create_admin(
            "adm7", 41, "Aliyev V.", allowedSections=["hisobotlar", "limit"]
        )

        response = self._face_login(41)
        self.assertEqual(response.status_code, 200, response.content)
        session = response.json()["session"]
        self.assertEqual(session["code"], "adm7")
        self.assertEqual(session["role"], "admin")
        self.assertEqual(session["displayName"], "Aliyev V.")
        # Faqat biriktirilgan bo'limlar — Face ID qo'shimcha huquq bermaydi.
        self.assertEqual(sorted(session["allowedSections"]), ["hisobotlar", "limit"])

    def test_worker_face_cannot_be_enrolled_as_admin(self):
        """Bitta odam ham xodim, ham admin bo'lib qololmaydi."""
        self._create_staff("9101", 42, name="Ali Valiyev")
        serializer = AccessCodeSerializer(
            data=self._admin_data("adm8", 42, "O'sha odam"), context={"request": None}
        )
        serializer.is_valid(raise_exception=True)
        with self.assertRaises(Exception):
            serializer.save()
        self.assertFalse(AccessCode.objects.filter(pk="adm8").exists())
        self.assertFalse(FaceTemplate.objects.filter(code="adm8").exists())

    def test_admin_code_cannot_equal_staff_tabel(self):
        self._create_staff("5150", 43)
        serializer = AccessCodeSerializer(
            data=self._admin_data("5150", 44, "Nusxa kod"), context={"request": None}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("code", serializer.errors)

    def test_staff_tabel_cannot_equal_admin_code(self):
        self._create_admin("5151", 45)
        serializer = StaffSerializer(
            data={
                "erju": "Toshkent",
                "zapravka": "Toshkent YO",
                "tabelNumber": "5151",
                "fullName": "Nusxa kod",
                "photo": TINY_JPEG,
                "faceSamples": frames(46, 3),
            },
            context={"request": None},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("tabelNumber", serializer.errors)

    def test_ambiguity_between_admin_and_worker_blocks_login(self):
        """Guruhlararo ikkilanishda tizim KIRITMAYDI (parol yo'li ochiq qoladi).

        Shablonlar ataylab to'g'ridan-to'g'ri yoziladi — ya'ni bazada allaqachon
        bir-biriga o'xshash admin va xodim turgan holat (eski ma'lumot yoki
        chegara o'zgargan holat) tekshiriladi.
        """
        staff = self._create_staff("9200", 47, name="Xodim")
        AccessCode.objects.create(code="adm9", displayName="Admin", role="admin")
        # Adminga AYNAN o'sha odamning kadrlari yoziladi — bu ro'yxatga olish
        # bosqichida to'silardi, shuning uchun servis darajasida qo'yiladi.
        face_service.enroll("adm9", [face.decode_sample(f) for f in frames(47, 3, 90)])

        response = self._face_login(47, device_id="dev-x")
        self.assertEqual(response.status_code, 401, response.content)
        self.assertIn(
            response.json()["reason"], ("cross_group", "ambiguous", "unstable")
        )
        self.assertTrue(Staff.objects.filter(pk=staff.pk).exists())

    def test_deleting_admin_removes_the_template(self):
        self._create_admin("adm10", 48)
        self.assertTrue(FaceTemplate.objects.filter(code="adm10").exists())
        token = create_access_token(
            {"code": "root", "role": "developer", "displayName": "Dev"}
        )["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = self.client.delete("/api/access-codes/adm10/")
        self.assertEqual(response.status_code, 204, response.content)
        self.assertFalse(FaceTemplate.objects.filter(code="adm10").exists())

    def test_access_code_list_has_no_photo_but_has_flags(self):
        self._create_admin("adm11", 49, "Bobur")
        token = create_access_token(
            {"code": "root", "role": "developer", "displayName": "Dev"}
        )["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = self.client.get("/api/access-codes/?role=admin")
        self.assertEqual(response.status_code, 200, response.content)
        row = next(r for r in response.json()["results"] if r["code"] == "adm11")
        self.assertNotIn("photo", row)        # surat ro'yxatga TUSHMAYDI
        self.assertNotIn("faceSamples", row)  # biometrik ma'lumot ham
        self.assertTrue(row["hasPhoto"])
        self.assertTrue(row["hasFace"])
        detail = self.client.get("/api/access-codes/adm11/photo/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["photo"], TINY_JPEG)

    def test_restricted_admin_cannot_touch_admin_codes(self):
        """Bo'limi cheklangan admin yangi admin yarata olmaydi (Face ID bilan ham)."""
        self._create_admin("adm12", 50, "Cheklangan", allowedSections=["hisobotlar"])
        token = create_access_token(
            {"code": "adm12", "role": "admin", "displayName": "Cheklangan"}
        )["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = self.client.post(
            "/api/access-codes/",
            self._admin_data("adm13", 51, "Yangi"),
            format="json",
        )
        self.assertEqual(response.status_code, 403, response.content)
        self.assertFalse(AccessCode.objects.filter(pk="adm13").exists())
