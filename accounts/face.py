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

OVAL NIQOB VA BLOK VAZNLARI (aniqlikni oshiradi)
────────────────────────────────────────────────
Klient KVADRAT qirqim yuboradi, uning burchaklarida esa yuz emas — soch,
yoqa va ORQA FON turadi. Ular ham shablonga tushsa, odam boshqa joyda turib
kirganda "boshqacha" bo'lib ko'rinardi, ya'ni fon shaxsning bir qismiga
aylanib qolardi. Shuning uchun:

  1. Faqat OVAL ichidagi piksellar hisobga olinadi (`_MASK`). Oval chekkasi
     yana 2 pikselga qisqartiriladi (`_CORE`), chunki LBP qo'shnilarni, undan
     oldingi silliqlash esa 3x3 atrofni o'qiydi — shu ikki qadam fonni
     chetdan "tortib kirmasligi" kerak.
  2. Bloklar teng emas: markaziy bloklar (ko'z–burun–og'iz zonasi) masofada
     og'irroq, chekka bloklar yengilroq hisoblanadi (`_BLOCK_WEIGHTS`).
     Vazn blokning oval bilan qoplanish ulushiga ham ko'paytiriladi — aks
     holda ichida atigi bir necha piksel qolgan chekka blok, o'zining ichki
     normallashtirilishi tufayli, to'la blok bilan TENG ta'sir qilardi.

Vaznlar yig'indisi ataylab blok soniga (64) tenglashtiriladi — shunda masofa
shkalasi o'zgarmaydi va sozlangan chegaralar (ABS_MAX, STRICT_ABS ...) o'z
ma'nosini saqlaydi.

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

GURUHLARARO CHALKASHLIKKA QARSHI (admin <-> oddiy xodim)
────────────────────────────────────────────────────────
Eng qimmat xato — xodimni admin deb (yoki aksincha) tanish: u odamga o'zga
huquq berib qo'yardi. Shuning uchun `identify()` ga `groups` berilsa va eng
yaqin ikki nomzod TURLI guruhdan chiqsa, qaror qattiqlashadi: nisbat testi
CROSS_RATIO (0.70) bo'yicha o'tadi va masofa STRICT_ABS dan past bo'lishi
shart. Ikkilanish bo'lsa — kiritilmaydi, odam parolini yozadi.

Ikkinchi (va aslida asosiy) himoya ro'yxatga olishda: `face_service.find_conflict`
yangi yuzni mavjud hammasi bilan solishtiradi va yaqin bo'lsa SAQLAMAYDI —
ya'ni bir-biriga o'xshab ketadigan ikki shablon bazaga umuman tushmaydi.

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
# 2 — oval niqob va blok vaznlari qo'shildi (eski shablonlar mos kelmaydi;
# ular `rebuild_face_templates` bilan saqlangan kadrlardan qayta quriladi).
TEMPLATE_VERSION = 2

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


# ── Oval niqob va blok vaznlari ─────────────────────────────────────────────
# Ovalning yarim o'qlari (rasm tomoniga nisbatan). Yuz qirqimi kvadratning
# deyarli hammasini egallaydi, shuning uchun oval kengroq olingan: maqsad —
# BURCHAKLARNI (fon/soch) kesish, yuzning yonoq-iyagini emas.
MASK_RX = 0.42
MASK_RY = 0.49
# Silliqlash (3x3) va LBP (3x3) chetdan fon tortib kirmasligi uchun qisqartirish.
MASK_ERODE = 2
# Markaziy bloklar qancha og'irroq: 1.0 = chekka, 1.0 + BOOST = eng markaz.
CENTER_BOOST = 0.8
# Oval bilan shundan kam qoplangan blok umuman hisobga olinmaydi.
MIN_BLOCK_COVERAGE = 0.15


def _build_mask() -> list[bool]:
    """Oval niqob: yuz joylashadigan soha."""
    mask = [False] * SAMPLE_LEN
    for y in range(FACE_SIZE):
        dy = (y + 0.5) / FACE_SIZE - 0.5
        for x in range(FACE_SIZE):
            dx = (x + 0.5) / FACE_SIZE - 0.5
            if (dx / MASK_RX) ** 2 + (dy / MASK_RY) ** 2 <= 1.0:
                mask[y * FACE_SIZE + x] = True
    return mask


def _erode(mask: list[bool], radius: int) -> list[bool]:
    """Niqobni chetidan `radius` piksel qisqartiradi."""
    out = [False] * SAMPLE_LEN
    for y in range(radius, FACE_SIZE - radius):
        for x in range(radius, FACE_SIZE - radius):
            ok = True
            for yy in range(y - radius, y + radius + 1):
                row = yy * FACE_SIZE
                for xx in range(x - radius, x + radius + 1):
                    if not mask[row + xx]:
                        ok = False
                        break
                if not ok:
                    break
            out[y * FACE_SIZE + x] = ok
    return out


_MASK = _build_mask()
_CORE = _erode(_MASK, MASK_ERODE)


def _build_block_weights() -> list[float]:
    """Har bir blokning vazni = (oval bilan qoplanish) x (markazga yaqinlik).

    Yig'indi blok soniga tenglashtiriladi, ya'ni masofa shkalasi va u bilan
    birga sozlangan chegaralar (ABS_MAX, STRICT_ABS) o'zgarmaydi.
    """
    weights: list[float] = []
    for by in range(GRID):
        for bx in range(GRID):
            inside = 0
            for y in range(by * BLOCK, (by + 1) * BLOCK):
                row = y * FACE_SIZE
                for x in range(bx * BLOCK, (bx + 1) * BLOCK):
                    if _CORE[row + x]:
                        inside += 1
            coverage = inside / (BLOCK * BLOCK)
            if coverage < MIN_BLOCK_COVERAGE:
                weights.append(0.0)
                continue
            cx = ((bx + 0.5) / GRID - 0.5) * 2.0   # -1 .. 1
            cy = ((by + 0.5) / GRID - 0.5) * 2.0
            bias = 1.0 + CENTER_BOOST * max(0.0, 1.0 - (cx * cx + cy * cy))
            weights.append(coverage * bias)

    total = sum(weights)
    if total <= 0:  # bo'lishi mumkin emas, lekin nol bo'lishga yo'l qo'ymaymiz
        return [1.0] * (GRID * GRID)
    scale = (GRID * GRID) / total
    return [w * scale for w in weights]


_BLOCK_WEIGHTS = _build_block_weights()
# Masofa hisoblashda bayt-ma-bayt yurish uchun yoyilgan ko'rinishi.
_BYTE_WEIGHTS = [w for w in _BLOCK_WEIGHTS for _ in range(BINS)]


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
    """12x12 o'rtacha yorug'lik eskizi, z-normallashtirilgan (0..255 bayt).

    Oval tashqarisidagi piksellar hisobga olinmaydi; butunlay tashqarida
    qolgan katak "neytral" (z = 0) qiymat oladi.
    """
    cell = FACE_SIZE // COARSE_GRID  # 8
    means: list[float | None] = []
    for gy in range(COARSE_GRID):
        for gx in range(COARSE_GRID):
            total = 0
            count = 0
            for y in range(gy * cell, (gy + 1) * cell):
                row = y * FACE_SIZE
                for x in range(gx * cell, (gx + 1) * cell):
                    if _MASK[row + x]:
                        total += px[row + x]
                        count += 1
            means.append(total / count if count else None)

    known = [m for m in means if m is not None]
    if not known:
        return bytearray([128] * COARSE_LEN)
    avg = sum(known) / len(known)
    var = sum((m - avg) ** 2 for m in known) / len(known)
    std = math.sqrt(var) or 1.0
    out = bytearray(COARSE_LEN)
    for i, m in enumerate(means):
        z = 0.0 if m is None else (m - avg) / std
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
            # Oval tashqarisi (fon/soch) shablonga umuman kirmaydi.
            if not _CORE[row + x]:
                continue
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
    """Chi-kvadrat masofa (0 = aynan bir xil ... 1 = mutlaqo boshqa).

    Har bir blok o'z vazni bilan qo'shiladi (`_BYTE_WEIGHTS`): markaz —
    og'irroq, chekka — yengilroq, oval tashqarisi — umuman hisoblanmaydi.
    """
    total = 0.0
    for x, y, w in zip(a[COARSE_LEN:], b[COARSE_LEN:], _BYTE_WEIGHTS):
        s = x + y
        if s:
            d = x - y
            total += w * (d * d) / s
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
        # Ikkinchi nomzod BOSHQA guruhdan bo'lganda (masalan g'olib — admin,
        # ikkinchi — oddiy xodim) talab qilinadigan qattiqroq nisbat.
        self.cross_ratio = float(cfg.get("CROSS_RATIO", 0.70))
        # Ro'yxatga olishda: yangi yuz boshqa odamnikiga shundan yaqin bo'lsa,
        # u umuman qabul qilinmaydi (kelajakda chalkashtirib yuborardi).
        # DIQQAT: bu qiymat ATAYLAB kichik. Asosiy chalkashlik tekshiruvi
        # `face_service.find_conflict` ichida KIRISH mantiqining o'zi bilan
        # qilinadi (yangi yuz mavjud birov sifatida tanilsa — rad etiladi), bu
        # yerdagi raqam esa faqat "deyarli bir xil surat" uchun qo'shimcha
        # to'siq. Kattalashtirib yuborilsa, bir-biriga uzoqdan o'xshaydigan
        # BEGONA odamlar ham ro'yxatdan o'tolmay qolardi.
        self.enroll_min_distance = float(cfg.get("ENROLL_MIN_DISTANCE", 0.10))


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
    groups: dict[str, str] | None = None,
) -> dict:
    """Kadrlar to'plamini ro'yxatdagi shablonlar bilan solishtiradi.

    `groups` — kod -> guruh nomi ("admin" / "staff"). Berilsa, g'olib bilan
    ikkinchi nomzod BOSHQA guruhdan bo'lgan hollarda qaror QATTIQROQ olinadi
    (pastdagi 3-qadamga qarang). Sababi: oddiy xodim bilan adminni chalkashtirib
    yuborish — eng qimmat xato, chunki u odamga o'zga huquq berib qo'yardi.
    Berilmasa, mantiq avvalgidek qoladi.

    Natija: {"code": str|None, "reason": str, "distance": float, "second":
    float, "secondCode": str|None, "z": float, "votes": int, "frames": int,
    "cohort": int}
    """
    result = {
        "code": None,
        "reason": "no_match",
        "distance": 1.0,
        "second": 1.0,
        "secondCode": None,
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
    second_code, second_distance = ordered[1] if len(ordered) > 1 else (None, 1.0)

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
            "secondCode": second_code,
            "z": round(z, 2),
            "votes": votes.get(best_code, 0),
        }
    )

    # G'olib va ikkinchi nomzod turli guruhda (admin <-> xodim) bo'lsa, nisbat
    # testi qattiqroq oladi va absolyut chegara ham "qattiq"ka tushadi. Ya'ni
    # ikkilanish bo'lgan zahoti tizim KIRITMAYDI — odam parolini yozadi. Bu
    # yo'nalish ataylab tanlangan: noto'g'ri odamni kiritgandan ko'ra, to'g'ri
    # odamni ham kiritmay parolga yuborish ancha arzon xato.
    cross_group = bool(groups) and (
        groups.get(best_code) != groups.get(second_code) if second_code else False
    )
    ratio_limit = thresholds.cross_ratio if cross_group else thresholds.ratio

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

    # 3) Guruhlararo ikkilanish: raqib boshqa guruhdan bo'lsa, masofa "qattiq"
    #    chegaradan ham past bo'lishi shart (yumshoq ABS_MAX yetarli emas).
    if cross_group and best_distance > thresholds.strict_abs:
        result["reason"] = "cross_group"
        return result

    if small_cohort or not z_usable:
        # 4) Statistikaga tayanib bo'lmaydi -> faqat qattiq absolyut chegara,
        #    va (nomzod bittadan ko'p bo'lsa) nisbat testi.
        if best_distance > thresholds.strict_abs:
            result["reason"] = "too_far"
            return result
        if cohort > 1 and best_distance > ratio_limit * second_distance:
            result["reason"] = "cross_group" if cross_group else "ambiguous"
            return result
    else:
        # 5) Nisbat testi: ikkinchi nomzoddan sezilarli yaxshiroq bo'lsin.
        if second_distance <= 0 or best_distance > ratio_limit * second_distance:
            result["reason"] = "cross_group" if cross_group else "ambiguous"
            return result
        # 6) Statistik ajralish: taqsimotdan aniq chetda tursin.
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


def templates_from_raw(lines: Iterable[str]) -> list[str]:
    """Saqlangan XOM kadrlardan (base64) shablonlarni qayta quradi.

    Algoritm yangilanganda (TEMPLATE_VERSION) ishlatiladi — hech kimdan
    qaytadan surat so'ralmaydi. Buzuq satrlar jimgina tashlab ketiladi.
    Buni ham migratsiya, ham `rebuild_face_templates` buyrug'i chaqiradi,
    shuning uchun mantiq bitta joyda turadi.
    """
    out: list[str] = []
    for line in lines:
        try:
            sample = base64.b64decode(line, validate=True)
        except (binascii.Error, ValueError):
            continue
        if len(sample) != SAMPLE_LEN:
            continue
        out.append(encode_template(build_template(sample)))
    return out
