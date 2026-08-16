"""
Auth / sessiya / xavfsizlik modellari.

Firestore kolleksiyalari bilan moslik:
  access_codes      -> AccessCode   (PK = code)
  staff             -> Staff
  blocked_codes     -> BlockedCode  (PK = code)
  active_sessions   -> ActiveSession (PK = uid)  — onlayn presence uchun
  security_events   -> SecurityEvent
  device_locks      -> DeviceLock   (PK = deviceId)

Maydon nomlari frontend TS interfeyslari bilan AYNAN bir xil (camelCase),
shuning uchun API javoblari Firestore hujjatlari bilan mos keladi.
"""

from django.db import models

from common.timeutil import now_ms

ROLE_CHOICES = [
    ("worker", "worker"),
    ("admin", "admin"),
    ("developer", "developer"),
]


class AccessCode(models.Model):
    """`access_codes/{code}` — admin/developer kirish kodlari."""

    code = models.CharField(max_length=64, primary_key=True)
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default="admin")
    displayName = models.CharField(max_length=200, blank=True, default="")
    nodeId = models.CharField(max_length=64, null=True, blank=True)
    stationId = models.CharField(max_length=64, null=True, blank=True)
    codeType = models.CharField(
        max_length=16,
        choices=[("admin", "admin"), ("developer", "developer")],
        default="admin",
    )
    isActive = models.BooleanField(default=True)
    # Admin kira oladigan bo'limlar ro'yxati, masalan ["statistika", "limit"].
    # BO'SH yoki NULL = CHEKLOV YO'Q (hamma bo'lim ochiq) — shu sababli mavjud
    # kodlar uchun hech narsa o'zgarmaydi. Ruxsat etilgan qiymatlar:
    # accounts/sections.py :: ASSIGNABLE_SECTIONS.
    allowedSections = models.JSONField(null=True, blank=True, default=None)
    # Admin surati — `Staff.photo` bilan AYNAN bir xil qoida: `data:image/...`
    # ko'rinishidagi kichik (~256px) JPEG. Face ID shabloni bu yerda EMAS,
    # `FaceTemplate` da (kalit — shu kod) turadi. Surat RO'YXAT javobiga
    # QO'SHILMAYDI: u faqat `GET /api/access-codes/{code}/photo/` orqali
    # olinadi, shuning uchun mavjud `/access-codes/` so'rovlari og'irlashmaydi.
    photo = models.TextField(blank=True, default="")
    photoUpdatedAt = models.BigIntegerField(null=True, blank=True)
    createdAt = models.BigIntegerField(default=now_ms)
    updatedAt = models.BigIntegerField(default=now_ms)

    class Meta:
        db_table = "access_codes"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} ({self.role})"


class Staff(models.Model):
    """`staff` — tabel raqam bo'yicha worker login (StaffVaultRecord)."""

    erju = models.CharField(max_length=120, blank=True, default="")
    zapravka = models.CharField(max_length=120, blank=True, default="")
    tabelNumber = models.CharField(max_length=64, db_index=True)
    fullName = models.CharField(max_length=200, blank=True, default="")
    role = models.CharField(
        max_length=16,
        null=True,
        blank=True,
        choices=[("worker", "worker"), ("operator", "operator")],
    )
    stationId = models.CharField(max_length=64, null=True, blank=True)
    # Xodim surati — `data:image/jpeg;base64,...` ko'rinishida (kichik, ~256px).
    # ATAYLAB alohida fayl-xotira (MEDIA_ROOT) ishlatilmadi: statik eksport
    # qilinadigan frontend uchun qo'shimcha fayl serveri/nginx sozlamasi kerak
    # bo'lardi va deploy murakkablashardi. Surat RO'YXAT javobiga QO'SHILMAYDI —
    # u faqat `GET /api/staff/{id}/photo/` orqali alohida olinadi, shuning uchun
    # mavjud `/staff/` so'rovlarining hajmi o'zgarmaydi.
    photo = models.TextField(blank=True, default="")
    photoUpdatedAt = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = "staff"
        ordering = ["tabelNumber"]

    def __str__(self):
        return f"{self.tabelNumber} — {self.fullName}"


class FaceTemplate(models.Model):
    """`face_templates/{code}` — Face ID biometrik shabloni.

    ATAYLAB `Staff` ga ForeignKey QILINMAGAN, kalit sifatida KIRISH KODI
    ishlatiladi (worker uchun tabel raqam, admin uchun access code). Sababi:
    Face ID muvaffaqiyatli bo'lganda backend aynan shu kod bilan parol
    orqali kirishdagi BIR XIL sessiya qurish yo'lidan o'tadi
    (`_build_admin_session` / `_build_staff_session`). Ya'ni Face ID hech qanday
    yangi huquq yo'li ochmaydi — u faqat "kodni yozish" qadamini almashtiradi.

    `vectors` — har biri base64 shablon bo'lgan qatorlar ("\\n" bilan ajratilgan).
    Bu maydon API orqali HECH QACHON tashqariga chiqmaydi (serializerda yo'q).
    """

    code = models.CharField(max_length=64, primary_key=True)
    vectors = models.TextField(blank=True, default="")
    # Normallashtirilgan kulrang kadrlar (96x96, base64). Ular saqlanadi, chunki
    # algoritm yangilansa (TEMPLATE_VERSION) shablonlarni SHU kadrlardan qayta
    # qurish mumkin — hech kimdan qaytadan surat so'ralmaydi:
    #   python manage.py rebuild_face_templates
    samples = models.TextField(blank=True, default="")
    sampleCount = models.IntegerField(default=0)
    version = models.IntegerField(default=1)
    createdAt = models.BigIntegerField(default=now_ms)
    updatedAt = models.BigIntegerField(default=now_ms)
    createdByDisplayName = models.CharField(max_length=200, blank=True, default="")
    lastMatchedAt = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = "face_templates"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} ({self.sampleCount} ta shablon)"

    def vector_list(self) -> list[str]:
        return [line for line in (self.vectors or "").splitlines() if line.strip()]

    def sample_list(self) -> list[str]:
        return [line for line in (self.samples or "").splitlines() if line.strip()]


class BlockedCode(models.Model):
    """`blocked_codes/{code}` — bloklangan kirish kodlari."""

    code = models.CharField(max_length=64, primary_key=True)
    note = models.CharField(max_length=300, blank=True, default="")
    blockedAt = models.BigIntegerField(default=now_ms)
    blockedByDisplayName = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        db_table = "blocked_codes"
        ordering = ["-blockedAt"]

    def __str__(self):
        return self.code


class ActiveSession(models.Model):
    """`active_sessions/{uid}` — onlayn presence (heartbeat)."""

    uid = models.CharField(max_length=128, primary_key=True)
    code = models.CharField(max_length=64, blank=True, default="")
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default="worker")
    stationId = models.CharField(max_length=64, null=True, blank=True)
    nodeId = models.CharField(max_length=64, null=True, blank=True)
    displayName = models.CharField(max_length=200, null=True, blank=True)
    staffVaultFullName = models.CharField(max_length=200, null=True, blank=True)
    createdAt = models.BigIntegerField(default=now_ms)
    lastSeen = models.BigIntegerField(default=now_ms)

    class Meta:
        db_table = "active_sessions"
        ordering = ["-lastSeen"]

    def __str__(self):
        return f"{self.uid} — {self.code}"


class SecurityEvent(models.Model):
    """`security_events` — login urinishlari / bloklash hodisalari."""

    TYPE_CHOICES = [
        ("wrong_code", "wrong_code"),
        ("device_locked", "device_locked"),
        ("successful_login", "successful_login"),
    ]
    type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    code = models.CharField(max_length=64, blank=True, default="")
    deviceId = models.CharField(max_length=128, blank=True, default="")
    timestamp = models.BigIntegerField(default=now_ms)
    meta = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "security_events"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.type} — {self.code}"


class DeviceLock(models.Model):
    """`device_locks/{deviceId}` — qurilma bloklash hisobi."""

    deviceId = models.CharField(max_length=128, primary_key=True)
    attempts = models.IntegerField(default=0)
    lockedAt = models.BigIntegerField(default=now_ms)
    lockedCode = models.CharField(max_length=64, blank=True, default="")
    isBlocked = models.BooleanField(default=False)

    class Meta:
        db_table = "device_locks"

    def __str__(self):
        return self.deviceId
