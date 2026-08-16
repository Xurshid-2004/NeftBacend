"""
Face ID uchun Django tomonidagi xizmat qatlami (validatsiya + saqlash + o'qish).

`face.py` — sof matematika (Django'ni bilmaydi), bu fayl esa uni model va
sozlamalar bilan bog'laydi. Barcha yozuv/o'qish shu yerdan o'tadi, shuning uchun
qoidalar (rasm hajmi, kadrlar soni, chegaralar) bitta joyda turadi.
"""

from __future__ import annotations

import base64
import binascii
import re

from django.conf import settings

from common.timeutil import now_ms

from . import face
from .models import FaceTemplate

# Surat uchun cheklovlar. Klient rasmni ~256px ga kichraytirib yuboradi
# (~20-40 KB), shuning uchun 400 KB — juda ehtiyotkor "shift".
MAX_PHOTO_BYTES = 400 * 1024
_PHOTO_PREFIX = re.compile(r"^data:image/(jpeg|jpg|png|webp);base64,", re.IGNORECASE)

# Bitta xodim uchun saqlanadigan maksimal shablon soni.
DEFAULT_MAX_SAMPLES = 5
# Login paytida qabul qilinadigan maksimal kadr soni.
MAX_LOGIN_FRAMES = 5
# Ikki xodimga bitta surat qo'yilganini aniqlash chegarasi (juda qattiq).
DUPLICATE_DISTANCE = 0.05


class FaceError(ValueError):
    """Foydalanuvchiga ko'rsatiladigan (o'zbekcha) xato."""


def config() -> dict:
    return getattr(settings, "FACE_ID", {}) or {}


def is_enabled() -> bool:
    return bool(config().get("ENABLED", True))


def thresholds() -> face.FaceThresholds:
    return face.FaceThresholds(config())


def max_samples() -> int:
    try:
        return max(1, min(10, int(config().get("MAX_SAMPLES", DEFAULT_MAX_SAMPLES))))
    except (TypeError, ValueError):
        return DEFAULT_MAX_SAMPLES


# ── Surat ───────────────────────────────────────────────────────────────────
def validate_photo(value: object) -> str:
    """`data:image/...;base64,...` ni tekshiradi va normallashtiradi."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise FaceError("Surat formati noto'g'ri.")
    raw = value.strip()
    if not raw:
        return ""
    match = _PHOTO_PREFIX.match(raw)
    if not match:
        raise FaceError("Surat formati noto'g'ri (JPEG/PNG/WEBP bo'lishi kerak).")
    payload = raw[match.end() :]
    try:
        decoded = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        raise FaceError("Suratni o'qib bo'lmadi.") from None
    if not decoded:
        raise FaceError("Surat bo'sh.")
    if len(decoded) > MAX_PHOTO_BYTES:
        raise FaceError("Surat hajmi juda katta (400 KB dan oshmasin).")
    return raw


# ── Kadrlar ─────────────────────────────────────────────────────────────────
def parse_samples(value: object, limit: int) -> list[bytes]:
    """Klientdan kelgan kadrlar ro'yxatini bytes ga aylantiradi."""
    if value in (None, ""):
        return []
    if not isinstance(value, (list, tuple)):
        raise FaceError("Yuz kadrlari noto'g'ri yuborildi.")
    if len(value) > limit:
        value = list(value)[:limit]
    out: list[bytes] = []
    for item in value:
        try:
            out.append(face.decode_sample(item))
        except face.FaceSampleError as exc:
            raise FaceError(str(exc)) from None
    return out


# ── Saqlash ─────────────────────────────────────────────────────────────────
def find_duplicate(code: str, samples: list[bytes]) -> str | None:
    """Xuddi shu surat boshqa xodimga biriktirilganmi?

    Chegara ATAYLAB juda qattiq (deyarli bir xil rasm) — "o'xshash odam" emas,
    "aynan o'sha faylni qayta yuklash" holatini tutadi. Shu sababli noto'g'ri
    ogohlantirish berish ehtimoli yo'q darajada.
    """
    if not samples:
        return None
    key = (code or "").strip()
    new_templates = [face.build_template(sample) for sample in samples]
    for existing_code, templates in load_enrolled():
        if existing_code == key:
            continue
        for a in new_templates:
            for b in templates:
                if face.hist_distance(a, b) <= DUPLICATE_DISTANCE:
                    return existing_code
    return None


def enroll(code: str, samples: list[bytes], created_by: str = "") -> int:
    """Kod uchun shablonlarni yozadi (mavjudi butunlay almashtiriladi)."""
    key = (code or "").strip()
    if not key:
        raise FaceError("Kod bo'sh — Face ID yozib bo'lmadi.")
    if not samples:
        raise FaceError("Yuz kadri yuborilmadi.")

    limit = max_samples()
    samples = samples[:limit]
    vectors = face.build_templates(samples, limit)
    if not vectors:
        raise FaceError("Yuz shabloni yaratilmadi.")
    raw = "\n".join(base64.b64encode(sample).decode("ascii") for sample in samples)

    ts = now_ms()
    record = FaceTemplate.objects.filter(pk=key).first()
    if record is None:
        FaceTemplate.objects.create(
            code=key,
            vectors="\n".join(vectors),
            samples=raw,
            sampleCount=len(vectors),
            version=face.TEMPLATE_VERSION,
            createdAt=ts,
            updatedAt=ts,
            createdByDisplayName=(created_by or "")[:200],
        )
    else:
        record.vectors = "\n".join(vectors)
        record.samples = raw
        record.sampleCount = len(vectors)
        record.version = face.TEMPLATE_VERSION
        record.updatedAt = ts
        if created_by:
            record.createdByDisplayName = created_by[:200]
        record.save(
            update_fields=[
                "vectors",
                "samples",
                "sampleCount",
                "version",
                "updatedAt",
                "createdByDisplayName",
            ]
        )
    return len(vectors)


def move(old_code: str, new_code: str) -> None:
    """Kirish kodi (tabel) o'zgarganda shablonni yangi kodga ko'chiradi."""
    old = (old_code or "").strip()
    new = (new_code or "").strip()
    if not old or not new or old == new:
        return
    record = FaceTemplate.objects.filter(pk=old).first()
    if not record:
        return
    FaceTemplate.objects.filter(pk=new).delete()
    FaceTemplate.objects.create(
        code=new,
        vectors=record.vectors,
        sampleCount=record.sampleCount,
        version=record.version,
        createdAt=record.createdAt,
        updatedAt=now_ms(),
        createdByDisplayName=record.createdByDisplayName,
        lastMatchedAt=record.lastMatchedAt,
    )
    record.delete()


def remove(code: str) -> None:
    key = (code or "").strip()
    if key:
        FaceTemplate.objects.filter(pk=key).delete()


def has_template(code: str) -> bool:
    key = (code or "").strip()
    return bool(key) and FaceTemplate.objects.filter(pk=key).exists()


# ── O'qish (identifikatsiya uchun) ──────────────────────────────────────────
def load_enrolled() -> list[tuple[str, list[bytes]]]:
    """Barcha shablonlar: [(code, [bytes, ...]), ...]. Buzuq yozuvlar tashlanadi.

    Faqat JORIY algoritm versiyasidagi shablonlar olinadi — eski versiyadagilar
    e'tiborsiz qoladi (noto'g'ri taqqoslashdan ko'ra parolga tushib qolgani
    xavfsizroq). Ularni tiklash: `python manage.py rebuild_face_templates`.
    """
    out: list[tuple[str, list[bytes]]] = []
    query = FaceTemplate.objects.filter(version=face.TEMPLATE_VERSION).only(
        "code", "vectors"
    )
    for record in query:
        items: list[bytes] = []
        for line in record.vector_list():
            decoded = face.decode_template(line)
            if decoded:
                items.append(decoded)
        if items:
            out.append((record.code, items))
    return out


def mark_matched(code: str) -> None:
    FaceTemplate.objects.filter(pk=code).update(lastMatchedAt=now_ms())
