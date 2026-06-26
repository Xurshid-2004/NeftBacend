"""
Hisobot generatsiyasi — `lib/firebase/report-service.ts` ning AYNAN nusxasi.

Submissionlardan ZapravkaSummary -> NodeSummary -> ReportData quriladi.
Ustun -> maydon bog'lanishi (PDF jadval qatorlari) o'zgartirilmagan:
  yuk/yolovchi/manyovr/xojalik/ijara <- lokomotiv.qanchaBerildi (harakatTuri bo'yicha)
  tamirlash      <- tamirlash.qanchaBerildi
  korxonaTotal   <- korxona.qancha
  qurulishTotal  <- qurulish.qanchaOlindi
  dizMasla       <- lokomotiv.dizMasla + tamirlash.dizMasla
"""

from __future__ import annotations

from catalog.models import Setting
from catalog.reference import UZELLAR, ZAPRAVKALAR
from common.numbers import parse_pdf_number, round2
from submissions.models import Submission


def _sum_field(rows, field) -> float:
    return sum(parse_pdf_number(r.get(field)) for r in rows)


def _calculate_zapravka_summary(zap: dict, submissions: list[dict]) -> dict:
    lokomotiv = [s for s in submissions if s.get("category") == "lokomotiv"]
    korxona = [s for s in submissions if s.get("category") == "korxona"]
    qurulish = [s for s in submissions if s.get("category") == "qurulish"]
    tamirlash = [s for s in submissions if s.get("category") == "tamirlash"]

    def loko_by_type(t):
        return _sum_field([l for l in lokomotiv if l.get("harakatTuri") == t], "qanchaBerildi")

    def count_by_type(t):
        return len([l for l in lokomotiv if l.get("harakatTuri") == t])

    yuk = loko_by_type("yuk")
    yolovchi = loko_by_type("yolovchi")
    manyovr = loko_by_type("manyovr")
    xojalik = loko_by_type("xojalik")
    ijara = loko_by_type("ijara") + loko_by_type("arenda")

    tamirlash_total = _sum_field(tamirlash, "qanchaBerildi")
    teplovoz_total = yuk + yolovchi + manyovr + xojalik + ijara + tamirlash_total

    korxona_total = _sum_field(korxona, "qancha")
    qurulish_total = _sum_field(qurulish, "qanchaOlindi")

    sutka_total = teplovoz_total + korxona_total + qurulish_total
    diz_masla = _sum_field(lokomotiv, "dizMasla") + _sum_field(tamirlash, "dizMasla")

    return {
        "zapravkaId": zap["id"],
        "zapravkaName": zap["name"],
        "nodeId": zap["uzelId"],
        "sutkaTotal": round2(sutka_total),
        "teplovozTotal": round2(teplovoz_total),
        "yuk": round2(yuk),
        "yolovchi": round2(yolovchi),
        "manyovr": round2(manyovr),
        "xojalik": round2(xojalik),
        "ijara": round2(ijara),
        "tamirlash": round2(tamirlash_total),
        "refSeksiya": 0,
        "korxonaTotal": round2(korxona_total),
        "qurulishTotal": round2(qurulish_total),
        "dizMasla": round2(diz_masla),
        "teplovozCount": {
            "yuk": count_by_type("yuk"),
            "yolovchi": count_by_type("yolovchi"),
            "manyovr": count_by_type("manyovr"),
            "xojalik": count_by_type("xojalik"),
            "ijara": count_by_type("ijara") + count_by_type("arenda"),
            "total": len(lokomotiv),
        },
    }


_TOTAL_KEYS = [
    "sutkaTotal", "teplovozTotal", "yuk", "yolovchi", "manyovr", "xojalik",
    "ijara", "tamirlash", "refSeksiya", "korxonaTotal", "qurulishTotal", "dizMasla",
]


def _calculate_totals(summaries: list[dict]) -> dict:
    acc = {k: 0 for k in _TOTAL_KEYS}
    count = {"yuk": 0, "yolovchi": 0, "manyovr": 0, "xojalik": 0, "ijara": 0, "total": 0}
    for s in summaries:
        for k in _TOTAL_KEYS:
            acc[k] += s.get(k, 0)
        sc = s.get("teplovozCount", {})
        for k in count:
            count[k] += sc.get(k, 0)
    acc["teplovozCount"] = count
    return acc


def _load_manual_fields() -> dict:
    setting = Setting.objects.filter(pk="global").first()
    if not setting:
        return {}
    template = (setting.data or {}).get("manualFieldsTemplate") or []
    return {f["key"]: f.get("defaultValue") for f in template if "key" in f}


def _submission_to_dict(sub: Submission) -> dict:
    out = {
        "category": sub.category,
        "stationId": sub.stationId,
        "harakatTuri": sub.harakatTuri,
        "qanchaBerildi": sub.qanchaBerildi,
        "qancha": sub.qancha,
        "qanchaOlindi": sub.qanchaOlindi,
        "dizMasla": sub.dizMasla,
    }
    return out


def generate_report(filter_: dict) -> dict:
    period = filter_.get("period", {})
    group_type = filter_.get("groupType")
    node_id = filter_.get("nodeId")
    station_id = filter_.get("stationId")

    start = period.get("startDate")
    end = period.get("endDate")

    qs = Submission.objects.filter(timestamp__gte=start, timestamp__lte=end).order_by("timestamp")
    submissions = [_submission_to_dict(s) for s in qs]

    # groupType bo'yicha filtr
    if group_type == "station" and station_id:
        submissions = [s for s in submissions if s["stationId"] == station_id]
    elif group_type == "node" and node_id:
        stations_in_node = {z["id"] for z in ZAPRAVKALAR if z["uzelId"] == node_id}
        submissions = [s for s in submissions if s["stationId"] in stations_in_node]

    nodes = []
    for uzel in UZELLAR:
        if group_type == "node" and node_id != uzel["id"]:
            continue
        zapravkalar = [z for z in ZAPRAVKALAR if z["uzelId"] == uzel["id"]]
        zap_summaries = []
        for zap in zapravkalar:
            if group_type == "station" and station_id != zap["id"]:
                continue
            zap_subs = [s for s in submissions if s["stationId"] == zap["id"]]
            zap_summaries.append(_calculate_zapravka_summary(zap, zap_subs))

        if zap_summaries:
            nodes.append({
                "nodeId": uzel["id"],
                "nodeName": uzel["name"],
                "zapravkalar": zap_summaries,
                "totals": _calculate_totals(zap_summaries),
            })

    republic_totals = _calculate_totals(
        [{**n["totals"], "zapravkaId": "", "zapravkaName": "", "nodeId": ""} for n in nodes]
    )

    from common.timeutil import now_ms

    return {
        "filter": filter_,
        "generatedAt": now_ms(),
        "generatedBy": "admin",
        "nodes": nodes,
        "republicTotals": republic_totals,
        "manualFields": _load_manual_fields(),
    }
