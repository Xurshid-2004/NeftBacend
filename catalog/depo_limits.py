"""
Депо лимитлари: ҚЎШИМЧА лимитни АСОСИЙ лимитга қўшиш (сервер томонда).

НИМА УЧУН СЕРВЕРДА
------------------
Қўшимча лимит `/admin/overlimit/depo/qoshimcha/` саҳифасидан берилади ва у
асосий лимит жадвалига (`/admin/overlimit/depo/`) қўшилиши керак. Агар бу
ҳисоб фақат браузерда бажарилса, API га тўғридан-тўғри мурожаат қилинганда
жами қиймат нотўғри бўлиб қоларди. Шу сабабли якуний ҳакам — шу модул:
`settings/depoLimits` ёки `settings/depoQoshimchaLimits` ҳужжатига ҳар қандай
ёзувдан кейин ишга тушади ва базадаги `limitKg` ни ЖАМИ қилиб қўяди.

ҚОИДА
-----
Қўшимча лимит қайси ДЕПО · қайси КАТЕГОРИЯ (ҳаракат тури) · қайси ЧОРАК учун
берилган бўлса, асосий лимитнинг айнан ўша катагига қўшилади:
    1-чоракка берилган қўшимча  ->  асосийнинг 1-чораги
    2-чоракка берилган қўшимча  ->  асосийнинг 2-чораги   (ва ҳоказо)
Бошқа чорак, бошқа категория ва бошқа депога ҳеч қачон тегмайди.

МАЪЛУМОТ ХАВФСИЗЛИГИ
--------------------
* Ҳеч қандай майдон номи ўзгартирилмайди ва ўчирилмайди.
* `limitKg` — ЖАМИ (асосий + қўшимча). Эски ўқувчилар шу майдонни ўқийверади.
* `asosiyLimitKg` — қўшимчасиз тоза қиймат (форма шуни таҳрирлайди).
* `qoshimchaLimitKg` — қўшилган қисм.
* Эски ёзувда бу иккита майдон бўлмаса — `asosiyLimitKg = limitKg`,
  `qoshimchaLimitKg = 0` деб қаралади, яъни қиймат ЎЗГАРМАЙДИ.
* Икки марта қўшилиб кетмайди: жами ҳар сафар `asosiy + qoshimcha` дан
  қайтадан ҳисобланади, устига қўшилмайди.
"""

from __future__ import annotations

from typing import Any

from common.timeutil import now_ms

from .models import Setting

MAIN_KEY = "depoLimits"
EXTRA_KEY = "depoQoshimchaLimits"

#: Шу иккита ҳужжатдан бирига ёзилса — қайта ҳисоб керак.
SYNC_KEYS = {MAIN_KEY, EXTRA_KEY}


def _num(value: Any) -> float:
    """Ҳар қандай ахлатни хавфсиз сонга айлантиради (манфий/бўш -> 0.0)."""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return 0.0
    if num != num or num in (float("inf"), float("-inf")) or num <= 0:
        return 0.0
    return num


def _round(value: float) -> float:
    return round(value + 0.0, 3)


def _cell_key(item: dict) -> str | None:
    """Катак калити — депо · категория · чорак (фронтенддаги калит билан бир хил)."""
    depo_id = str(item.get("depoId") or "").strip()
    if not depo_id:
        return None
    category = str(item.get("category") or "")
    period = str(item.get("period") or "")
    return f"{depo_id}__{category}__{period}"


def _items(setting: Setting | None) -> list[dict]:
    if setting is None:
        return []
    raw = (setting.data or {}).get("items")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _asosiy_kg(item: dict) -> float:
    """Ёзувнинг қўшимчасиз (тоза) қиймати."""
    if "asosiyLimitKg" in item:
        return _num(item.get("asosiyLimitKg"))
    # Эски ёзув: `limitKg` нинг ўзи асосий лимит бўлган.
    return max(0.0, _num(item.get("limitKg")) - _num(item.get("qoshimchaLimitKg")))


def sync_depo_limits() -> bool:
    """
    `settings/depoLimits` ичидаги ҳар бир ёзувни қайта ҳисоблайди.

    Қайтаради: ҳужжат ҳақиқатан ўзгарган бўлса `True`. Ўзгармаса ёзилмайди —
    шу сабабли бекорга WebSocket broadcast ҳам юборилмайди.
    """
    main = Setting.objects.filter(pk=MAIN_KEY).first()
    extra = Setting.objects.filter(pk=EXTRA_KEY).first()

    main_items = _items(main)
    extra_items = _items(extra)

    # Катак -> қўшимча килограмм (фақат ФАОЛ қўшимча лимитлар қўшилади).
    extra_kg: dict[str, float] = {}
    extra_src: dict[str, dict] = {}
    for item in extra_items:
        if item.get("isActive") is False:
            continue
        kg = _num(item.get("limitKg"))
        if kg <= 0:
            continue
        key = _cell_key(item)
        if not key:
            continue
        extra_kg[key] = extra_kg.get(key, 0.0) + kg
        extra_src.setdefault(key, item)

    changed = False
    result: list[dict] = []
    seen: set[str] = set()

    for item in main_items:
        key = _cell_key(item)
        if key is None:
            # Депоси йўқ бузуқ ёзув — тегилмайди, борича сақланади.
            result.append(item)
            continue

        seen.add(key)
        asosiy = _asosiy_kg(item)
        qoshimcha = extra_kg.get(key, 0.0)
        total = _round(asosiy + qoshimcha)

        # Асосийси ҳам, қўшимчаси ҳам қолмаган "авто" ёзув — ўчади.
        if item.get("autoFromQoshimcha") is True and asosiy <= 0 and qoshimcha <= 0:
            changed = True
            continue

        updated = dict(item)
        updated["limitKg"] = total
        updated["asosiyLimitKg"] = _round(asosiy)
        updated["qoshimchaLimitKg"] = _round(qoshimcha)
        if asosiy > 0:
            updated["autoFromQoshimcha"] = False

        if updated != item:
            changed = True
        result.append(updated)

    # Асосий лимити йўқ, фақат қўшимчаси бор катаклар — асосий жадвалга
    # "авто" ёзув сифатида тушади, акс ҳолда берилган қўшимча лимит асосий
    # жадвалда ҳам, ундан чиқадиган PDF да ҳам кўринмай қоларди.
    for key, kg in extra_kg.items():
        if key in seen:
            continue
        source = extra_src.get(key) or {}
        now = now_ms()
        result.append(
            {
                "depoId": source.get("depoId"),
                "depoName": source.get("depoName"),
                "depoLabel": source.get("depoLabel"),
                "category": source.get("category"),
                "period": source.get("period"),
                "limitKg": _round(kg),
                "asosiyLimitKg": 0,
                "qoshimchaLimitKg": _round(kg),
                "autoFromQoshimcha": True,
                "buyruqNumber": source.get("buyruqNumber"),
                "buyruqTime": source.get("buyruqTime"),
                "startDate": source.get("startDate"),
                "note": source.get("note"),
                "isActive": True,
                "createdAt": source.get("createdAt") or now,
                "updatedAt": source.get("updatedAt") or now,
                "createdBy": source.get("createdBy"),
            }
        )
        changed = True

    if not changed:
        return False

    if main is None:
        Setting.objects.update_or_create(
            pk=MAIN_KEY,
            defaults={"data": {"items": result}, "updatedAt": now_ms()},
        )
        return True

    data = dict(main.data or {})
    data["items"] = result
    main.data = data
    main.updatedAt = now_ms()
    main.save()
    return True
