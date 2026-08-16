"""
Face ID biometrik yadrosi — TASHQI KUTUBXONASIZ (faqat Python stdlib).

NEGA SHUNDAY QILINGAN
─────────────────────
1. Serverga birorta yangi paket o'rnatilmaydi (numpy / opencv / dlib / Pillow YO'Q).
   Shu sababli deploy paytida "wheel topilmadi", "kompilyator kerak", "libGL yo'q"
   kabi muammolar BO'LISHI MUMKIN EMAS — `requirements.txt` o'zgarishsiz qoladi.
2. Brauzer serverga faqat NORMALLASHTIRILGAN kulrang piksellarni (96x96 = 9216
   bayt) yuboradi. Biometrik shablonni (template) va taqqoslashni HAR DOIM server
   hisoblaydi. Ya'ni klient tomonda "tayyor shablon"ni soxtalashtirib yuborish
   bilan tizimga kirib bo'lmaydi — bu Face ID ni frontendda hisoblaydigan
   yechimlardan tubdan xavfsizroq.

ALGORITM
────────
Uniform LBP (Local Binary Patterns) + blokli gistogramma. Bu — OpenCV dagi
klassik `LBPHFaceRecognizer` ning aynan o'zi:
  * LBP faqat qo'shni piksellarni bir-biriga solishtiradi, shuning uchun
    yorug'lik kuchayishi/pasayishi natijani o'zgartirmaydi (monoton
    o'zgarishlarga invariant);
  * rasm 8x8 blokka bo'linadi va har bir blok uchun alohida gistogramma
    olinadi — bu yuzning geometriyasini (ko'z/burun/og'iz joylashuvini) saqlaydi.

QAROR QABUL QILISH (eng muhim qism)
───────────────────────────────────
Faqat "masofa < chegara" tekshiruvi ishonchsiz: chegara yorug'likka, kameraga,
odamlar soniga bog'liq. Shuning uchun uchta shart BIRGA talab qilinadi:
  1. absolyut chegara      — d_best <= ABS_MAX (xavfsizlik "shifti");
  2. Lowe nisbat testi     — d_best <= RATIO * d_second (eng yaqin ikkinchi
                             nomzoddan sezilarli darajada yaxshiroq bo'lsin);
  3. z-ball (statistik)    — d_best qolgan hamma nomzodlar taqsimotidan
                             kamida MIN_Z standart og'ish uzoqlikda bo'lsin.
Ro'yxatdan o'tganlar soni 4 tadan kam bo'lsa (2 va 3 statistik ma'noga ega
emas) — qattiqroq absolyut chegara (STRICT_ABS) ishlatiladi.

Bundan tashqari login paytida bitta emas, bir nechta kadr yuboriladi va G'OLIB
kadrlarning ko'pchiligida bir xil odam bo'lishi shart.

CHEKLOV (ochiq aytilishi kerak)
───────────────────────────────
Bu — kamera orqali yuz taqqoslash, Apple Face ID kabi 3D chuqurlik sensori emas.
Chop etilgan surat bilan aldash nazariy jihatdan mumkin. Shu sababli Face ID
FAQAT qulaylik uchun birinchi qadam bo'lib turadi; parol bilan kirish, qurilma
bloklash va bloklangan kod tekshiruvlari avvalgidek to'liq kuchda qoladi.
"""

from __future__ import annotations

import base64
import binascii
import math
from typing import Iterable, Sequence

# ── O'lchamlar (klient bilan KELISHILGAN — lib/face/face-sample.ts) ──────────
FACE_SIZE = 96                      # klient yuboradigan kulrang rasm tomoni
SAMPLE_LEN = FACE_SIZE * FACE_SIZE  # 9216 bayt
GRID = 8                            # 8x8 blok
BLOCK = FACE_SIZE // GRID           # 12 piksel
BINS = 59                           # uniform LBP: 58 naqsh + 1 "boshqa"
HIST_LEN = GRID * GRID * BINS       # 3776
COARSE_GRID = 12                    # tez saralash uchun 12x12 "eskiz"
COARSE_LEN = COARSE_GRID * COARSE_GRID  # 144
TEMPLATE_LEN = COARSE_LEN + HIST_LEN    # 3920 bayt
TEMPLATE_VERSION = 1

# chi-kvadrat masofasining nazariy maksimumi (0..1 oralig'iga keltirish uchun)
_CHI2_MAX = float(GRID * GRID * 2 * 255)

# SHOVQINGA CHIDAMLILIK — eng muhim koeffitsiyent.
# Oddiy LBP qo'shni pikselni markaz bilan "katta/kichik" deb solishtiradi. Yonoq
# yoki peshona kabi TEKIS joylarda qo'shnilar deyarli teng bo'ladi va kameraning
# ±5 birlik shovqini natijani tasodifiy o'zgartirib yuboradi — o'sha odamning
# o'zi ham tanilmay qoladi. Shu sababli piksel qo'shnidan kamida shuncha
# yorqinroq bo'lsagina bit qo'yiladi (Tan & Triggs g'oyasi). Bu qiymat
# o'zgartirilsa BARCHA shablonlar qayta qurilishi kerak (TEMPLATE_VERSION!).
LBP_TOLERANCE = 5

# Nomzodlar ko'payib ketsa: avval yengil "eskiz" bo'yicha saralash, keyin to'liq
# taqqoslash. Kichik korxonada (bir necha o'nlab xodim) saralash umuman
# ishlamaydi — hamma nomzod to'liq tekshiriladi.
PREFILTER_AFTER = 50   # nechta KOD dan keyin saralash yoqiladi
PREFILTER_KEEP = 30    # to'liq tekshiriladigan eng yaqin nomzodlar soni


class FaceSampleError(ValueError):
    """Klient yuborgan kadr noto'g'ri (o'lcham / base64)."""


# ── Uniform LBP jadvali ─────────────────────────────────────────────────────
def _build_uniform_table() -> list[int]:
    """0..255 -> 0..58. 2 tadan ko'p 0/1 o'tishi bo'lgan naqshlar bitta binga."""
    table = [BINS - 1] * 256
    index = 0
    for value in range(256):
        transitions = 0
        prev = (value >> 7) & 1
        for bit in range(8):
            cur = (value >> bit) & 1
            if cur != prev:
                transitions += 1
            prev = cur
        if transitions <= 2:
            table[value] = index
            index += 1
    return table


_UNIFORM = _build_uniform_table()


# ── Klient kadrini o'qish ───────────────────────────────────────────────────
def decode_sample(value: object) -> bytes:
    """base64 (96x96 kulrang) -> bytes. Noto'g'ri bo'lsa FaceSampleError."""
    if not isinstance(value, str):
        raise FaceSampleError("Kadr formati noto'g'ri.")
    raw = value.strip()
    if "," in raw[:64]:  # ehtimoliy "data:...;base64," prefiksi
        raw = raw.split(",", 1)[1]
    try:
        data = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        raise FaceSampleError("Kadrni o'qib bo'lmadi.") from None
    if len(data) != SAMPLE_LEN:
        raise FaceSampleError("Kadr o'lchami noto'g'ri.")
    return data


# ── Tasvirni tayyorlash ─────────────────────────────────────────────────────
def _box_blur(src: Sequence[int]) -> list[int]:
    """3x3 o'rtacha filtr (ajratilgan) — kamera "shovqin"ini so'ndiradi."""
    n = FACE_SIZE
    tmp = [0] * (n * n)
    for y in range(n):
        row = y * n
        for x in range(n):
            x0 = x - 1 if x > 0 else 0
            x1 = x + 1 if x < n - 1 else n - 1
            tmp[row + x] = (src[row + x0] + src[row + x] + src[row + x1]) // 3
    out = [0] * (n * n)
    for y in range(n):
        row = y * n
        up = (y - 1 if y > 0 else 0) * n
        dn = (y + 1 if y < n - 1 else n - 1) * n
        for x in range(n):
            out[row + x] = (tmp[up + x] + tmp[row + x] + tmp[dn + x]) // 3
    return out


def _coarse_vector(px: Sequence[int]) -> bytearray:
    """12x12 o'rtacha yorug'lik eskizi, z-normallashtirilgan (0..255 bayt)."""
    cell = FACE_SIZE // COARSE_GRID  # 8
    means: list[float] = []
    for gy in range(COARSE_GRID):
        for gx in range(COARSE_GRID):
            total = 0
            for y in range(gy * cell, (gy + 1) * cell):
                row = y * FACE_SIZE
                total += sum(px[row + gx * cell : row + (gx + 1) * cell])
            means.append(total / (cell * cell))
    avg = sum(means) / len(means)
    var = sum((m - avg) ** 2 for m in means) / len(means)
    std = math.sqrt(var) or 1.0
    out = bytearray(COARSE_LEN)
    for i, m in enumerate(means):
        z = (m - avg) / std
        out[i] = max(0, min(255, int(round(128 + 40 * z))))
    return out


def _lbp_histograms(px: Sequence[int]) -> bytearray:
    """Blok-bo'yicha uniform LBP gistogrammasi (har blok alohida normallanadi)."""
    n = FACE_SIZE
    counts = [[0] * BINS for _ in range(GRID * GRID)]
    for y in range(1, n - 1):
        row = y * n
        up = row - n
        dn = row + n
        block_row = (y // BLOCK) * GRID
        for x in range(1, n - 1):
            c = px[row + x] + LBP_TOLERANCE
            code = 0
            if px[up + x - 1] >= c:
                code |= 1
            if px[up + x] >= c:
                code |= 2
            if px[up + x + 1] >= c:
                code |= 4
            if px[row + x + 1] >= c:
                code |= 8
            if px[dn + x + 1] >= c:
                code |= 16
            if px[dn + x] >= c:
                code |= 32
            if px[dn + x - 1] >= c:
                code |= 64
            if px[row + x - 1] >= c:
                code |= 128
            counts[block_row + (x // BLOCK)][_UNIFORM[code]] += 1

    hist = bytearray(HIST_LEN)
    for b, block in enumerate(counts):
        total = sum(block)
        if not total:
            continue
        base = b * BINS
        scale = 255.0 / total
        for i, value in enumerate(block):
            if value:
                hist[base + i] = min(255, int(round(value * scale)))
    return hist


def build_template(sample: bytes) -> bytes:
    """96x96 kulrang kadr -> biometrik shablon (3920 bayt)."""
    px = _box_blur(sample)
    return bytes(_coarse_vector(px) + _lbp_histograms(px))


def encode_template(template: bytes) -> str:
    return base64.b64encode(template).decode("ascii")


def decode_template(value: str) -> bytes | None:
    try:
        data = base64.b64decode(value.strip(), validate=True)
    except (binascii.Error, ValueError):
        return None
    return data if len(data) == TEMPLATE_LEN else None


# ── Masofalar ───────────────────────────────────────────────────────────────
def hist_distance(a: bytes, b: bytes) -> float:
    """Chi-kvadrat masofa (0 = aynan bir xil ... 1 = mutlaqo boshqa)."""
    total = 0.0
    for x, y in zip(a[COARSE_LEN:], b[COARSE_LEN:]):
        s = x + y
        if s:
            d = x - y
            total += (d * d) / s
    return total / _CHI2_MAX


def coarse_distance(a: bytes, b: bytes) -> float:
    """Yengil "eskiz" masofasi — faqat nomzodlarni oldindan saralash uchun."""
    num = na = nb = 0
    for x, y in zip(a[:COARSE_LEN], b[:COARSE_LEN]):
        u = x - 128
        v = y - 128
        num += u * v
        na += u * u
        nb += v * v
    if na <= 0 or nb <= 0:
        return 1.0
    cos = num / math.sqrt(na * nb)
    return max(0.0, min(1.0, (1.0 - cos) / 2.0))


def samples_are_replay(samples: Sequence[bytes]) -> bool:
    """Bir xil baytlar qayta-qayta yuborilganini aniqlaydi.

    Haqiqiy kameradan olingan ikki kadr hech qachon bayt-ma-bayt bir xil
    bo'lmaydi (sensor shovqini bor). Bir xil bo'lsa — bu yozib olingan
    (replay) so'rov, rad etiladi.
    """
    if len(samples) < 2:
        return False
    for i in range(1, len(samples)):
        prev = samples[i - 1]
        cur = samples[i]
        if prev == cur:
            return True
        # o'rtacha absolyut farq juda kichik bo'lsa ham shubhali (nusxa + 1 piksel)
        diff = sum(abs(p - c) for p, c in zip(prev[::7], cur[::7]))
        if diff / (SAMPLE_LEN / 7) < 0.15:
            return True
    return False


# ── Identifikatsiya ─────────────────────────────────────────────────────────
class FaceThresholds:
    """`settings.FACE_ID` dan o'qiladigan chegaralar."""

    def __init__(self, config: dict | None = None):
        cfg = config or {}
        self.abs_max = float(cfg.get("ABS_MAX", 0.45))
        self.strict_abs = float(cfg.get("STRICT_ABS", 0.28))
        self.ratio = float(cfg.get("RATIO", 0.82))
        self.min_z = float(cfg.get("MIN_Z", 2.4))
        self.min_cohort = int(cfg.get("MIN_COHORT", 4))


def _frame_distances(
    template: bytes,
    enrolled: Sequence[tuple[str, list[bytes]]],
) -> dict[str, float]:
    """Bitta kadr uchun: har bir kod -> eng yaqin shabloni bilan masofa."""
    candidates = enrolled
    if len(enrolled) > PREFILTER_AFTER:
        coarse = [
            (min(coarse_distance(template, item) for item in items), code, items)
            for code, items in enrolled
            if items
        ]
        coarse.sort(key=lambda row: row[0])
        candidates = [(code, items) for _, code, items in coarse[:PREFILTER_KEEP]]

    out: dict[str, float] = {}
    for code, items in candidates:
        if not items:
            continue
        out[code] = min(hist_distance(template, item) for item in items)
    return out


def identify(
    samples: Sequence[bytes],
    enrolled: Sequence[tuple[str, list[bytes]]],
    thresholds: FaceThresholds,
) -> dict:
    """Kadrlar to'plamini ro'yxatdagi shablonlar bilan solishtiradi.

    Natija: {"code": str|None, "reason": str, "distance": float, "second":
    float, "z": float, "votes": int, "frames": int, "cohort": int}
    """
    result = {
        "code": None,
        "reason": "no_match",
        "distance": 1.0,
        "second": 1.0,
        "z": 0.0,
        "votes": 0,
        "frames": len(samples),
        "cohort": len(enrolled),
    }
    if not samples or not enrolled:
        result["reason"] = "not_enrolled"
        return result

    per_frame: list[dict[str, float]] = []
    votes: dict[str, int] = {}
    for sample in samples:
        template = build_template(sample)
        distances = _frame_distances(template, enrolled)
        if not distances:
            continue
        per_frame.append(distances)
        winner = min(distances, key=distances.get)
        votes[winner] = votes.get(winner, 0) + 1

    if not per_frame:
        result["reason"] = "not_enrolled"
        return result

    # Kadrlar bo'yicha o'rtacha masofa. Biror kadrda baholanmagan kod o'sha
    # kadrning eng yomon masofasini oladi (ya'ni jazolanadi, mukofotlanmaydi).
    codes = set()
    for distances in per_frame:
        codes.update(distances)
    aggregated: dict[str, float] = {}
    for code in codes:
        total = 0.0
        for distances in per_frame:
            total += distances.get(code, max(distances.values()))
        aggregated[code] = total / len(per_frame)

    ordered = sorted(aggregated.items(), key=lambda row: row[1])
    best_code, best_distance = ordered[0]
    second_distance = ordered[1][1] if len(ordered) > 1 else 1.0

    values = list(aggregated.values())
    mean = sum(values) / len(values)
    if len(values) > 1:
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std = math.sqrt(variance)
    else:
        std = 0.0
    z = (mean - best_distance) / std if std > 1e-9 else 0.0

    result.update(
        {
            "distance": round(best_distance, 4),
            "second": round(second_distance, 4),
            "z": round(z, 2),
            "votes": votes.get(best_code, 0),
        }
    )

    # Nechta nomzod bor — qaysi testlar MA'NOGA EGA ekanini shu belgilaydi.
    cohort = len(aggregated)
    small_cohort = cohort < thresholds.min_cohort
    # z-ballning matematik maksimumi: (n-1)/sqrt(n). Masalan 5 ta nomzodda u
    # atigi 1.79 — ya'ni min_z=2.4 ni TALAB QILISH mantiqsiz bo'lardi (hech kim
    # hech qachon kira olmasdi). Shuning uchun z faqat erishish mumkin bo'lgan
    # holatda ishlatiladi, aks holda uning o'rniga qattiq absolyut chegara.
    z_ceiling = (cohort - 1) / math.sqrt(cohort) if cohort > 1 else 0.0
    z_usable = z_ceiling >= thresholds.min_z * 1.15

    # 1) Kadrlar bir-birini tasdiqlashi shart. Statistik testlar ishlamaydigan
    #    holatda (kichik jamoa) BARCHA kadrlar bir xil odamni ko'rsatishi kerak.
    needed_votes = len(per_frame) if small_cohort else (len(per_frame) + 1) // 2
    if votes.get(best_code, 0) < needed_votes:
        result["reason"] = "unstable"
        return result

    # 2) Absolyut "shift" — bundan uzoq masofa hech qachon qabul qilinmaydi.
    if best_distance > thresholds.abs_max:
        result["reason"] = "too_far"
        return result

    if small_cohort or not z_usable:
        # 3) Statistikaga tayanib bo'lmaydi -> faqat qattiq absolyut chegara,
        #    va (nomzod bittadan ko'p bo'lsa) nisbat testi.
        if best_distance > thresholds.strict_abs:
            result["reason"] = "too_far"
            return result
        if cohort > 1 and best_distance > thresholds.ratio * second_distance:
            result["reason"] = "ambiguous"
            return result
    else:
        # 4) Nisbat testi: ikkinchi nomzoddan sezilarli yaxshiroq bo'lsin.
        if second_distance <= 0 or best_distance > thresholds.ratio * second_distance:
            result["reason"] = "ambiguous"
            return result
        # 5) Statistik ajralish: taqsimotdan aniq chetda tursin.
        if z < thresholds.min_z:
            result["reason"] = "ambiguous"
            return result

    result["code"] = best_code
    result["reason"] = "ok"
    return result


def build_templates(samples: Iterable[bytes], limit: int) -> list[str]:
    """Ro'yxatdan o'tkazish: kadrlardan base64 shablonlar ro'yxati."""
    out: list[str] = []
    for sample in samples:
        if len(out) >= limit:
            break
        out.append(encode_template(build_template(sample)))
    return out
