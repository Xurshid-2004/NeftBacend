"""
Qog'oz hisobotni (CSV) submissionlarga import qiladi — real odam kiritgandek.

Har qator `create_submission(...)` orqali kiritiladi (report_date_override bilan),
ya'ni submission + kunlik/yillik summary + fuelRecord (Y.PDF) — hammasi bir xil.

Ishlatish (bacend/ ichida):
  python manage.py import_report                    # report_20260601.csv, 2026-06-01
  python manage.py import_report --flush            # shu sanadagi eski yozuvlarni o'chirib, qayta import
  python manage.py import_report --file yo.csv --date 2026-06-01

CSV ustunlari:
  station,staff,time,type,seriya,raqami,poyezd,indeks,vazni,qoldiq,berilgan
    station : stansiya IDsi (toshkent, termez, uchquduq ...)
    type    : gruz|pass|manevr|arenda|prigor (lokomotiv) | stroit (qurulish) | predpr (korxona)
    qoldiq  : 8-ustun (bakdagi qoldiq)      berilgan : 9-ustun (berilgan dizel)
"""

from __future__ import annotations

import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from catalog.models import Zapravka
from common.numbers import parse_pdf_number
from submissions.models import DailySummary, FuelRecord, Submission
from submissions.services import create_submission, delete_submission

# Qog'ozdagi "Yo'nalish turlari" -> (kategoriya, harakatTuri)
TYPE_MAP = {
    "gruz": ("lokomotiv", "yuk"),
    "pass": ("lokomotiv", "yolovchi"),
    "manevr": ("lokomotiv", "manyovr"),
    "arenda": ("lokomotiv", "ijara"),
    "prigor": ("lokomotiv", "prigor"),
    "stroit": ("qurulish", None),
    "predpr": ("korxona", None),
}


def _num(v):
    v = (v or "").strip()
    return parse_pdf_number(v) if v else None


class Command(BaseCommand):
    help = "Qog'oz hisobotni (CSV) submissionlarga import qiladi (report_date_override bilan)."

    def add_arguments(self, parser):
        parser.add_argument("--file", default=str(Path(settings.BASE_DIR) / "report_20260701.csv"))
        parser.add_argument("--date", default="2026-07-01")
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Shu sanadagi mavjud yozuvlarni (submission+fuelRecord+summary) avval o'chiradi.",
        )
        parser.add_argument(
            "--flush-only",
            action="store_true",
            help="Faqat shu sanadagi yozuvlarni o'chiradi, import qilmaydi.",
        )

    def handle(self, *args, **opts):
        date = opts["date"]
        flush_only = opts["flush_only"]

        # Tozalash: submission (delta bilan), fuelRecord va kunlik summaryni ham o'chiradi —
        # shunda qayta import dublikatsiz va toza bo'ladi. Yillik summary delta orqali
        # to'g'rilanadi (delete_submission -1, keyin import +1).
        if opts["flush"] or flush_only:
            old = list(Submission.objects.filter(dateISO=date))
            for s in old:
                delete_submission(s)
            fr = FuelRecord.objects.filter(dateISO=date).delete()[0]
            ds = DailySummary.objects.filter(dateISO=date).delete()[0]
            self.stdout.write(self.style.WARNING(
                f"Flush ({date}): {len(old)} submission, {fr} fuelRecord, {ds} dailySummary o'chirildi."
            ))
            if flush_only:
                self.stdout.write(self.style.SUCCESS("Faqat tozalash bajarildi — import qilinmadi."))
                return

        path = Path(opts["file"])
        if not path.exists():
            raise CommandError(f"CSV topilmadi: {path}")

        zap_node = {z.id: z.uzelId for z in Zapravka.objects.all()}
        if not zap_node:
            raise CommandError("Zapravkalar bo'sh — avval `python manage.py seed` bajaring.")

        rows = []
        with path.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                if (r.get("station") or "").strip():
                    rows.append(r)

        created, skipped = 0, 0
        totals: dict[str, float] = {}

        for i, r in enumerate(rows, 1):
            station = r["station"].strip()
            typ = (r.get("type") or "").strip().lower()
            if station not in zap_node:
                self.stderr.write(f"  #{i} SKIP: stansiya topilmadi '{station}'")
                skipped += 1
                continue
            if typ not in TYPE_MAP:
                self.stderr.write(f"  #{i} SKIP: turi noma'lum '{typ}'")
                skipped += 1
                continue

            category, harakat = TYPE_MAP[typ]
            berilgan = _num(r.get("berilgan"))
            qoldiq = _num(r.get("qoldiq"))
            poyezd = (r.get("poyezd") or "").strip()
            indeks = (r.get("indeks") or "").strip()
            seriya = (r.get("seriya") or "").strip()
            raqami = (r.get("raqami") or "").strip()
            vazni = _num(r.get("vazni"))

            data = {
                "stationId": station,
                "nodeId": zap_node[station],
                "staffCode": (r.get("staffCode") or "").strip(),
                "staffName": (r.get("staff") or "").strip(),
                "enteredTime": (r.get("time") or "").strip(),
            }

            if category == "lokomotiv":
                data.update({
                    "harakatTuri": harakat,
                    "rusumi": seriya,
                    "lokomotivNumber": raqami,
                    "ruxsatIndeksi": indeks,
                    "poyezdVazni": vazni,
                    "qoldiq": qoldiq or 0,
                    "qanchaBerildi": berilgan or 0,
                    "dizMasla": 0,
                })
                if harakat == "manyovr":
                    data["stansiya"] = poyezd
                else:
                    data["poyezdNumber"] = poyezd
            elif category == "qurulish":
                data.update({
                    "seriya": seriya,
                    "raqami": raqami,
                    "poyezdNumber": poyezd,
                    "korxonaNomi": poyezd,
                    "ruxsatIndeksi": indeks,
                    "qoldiq": qoldiq or 0,
                    "qanchaBerildi": berilgan or 0,
                    "qanchaOlindi": berilgan or 0,
                })
            else:  # korxona
                data.update({
                    "korxonaNomi": poyezd,
                    "poyezdNumber": poyezd,
                    "ruxsatIndeksi": indeks,
                    "qancha": berilgan or 0,
                })

            create_submission(category, data, report_date_override=date)
            created += 1
            totals[station] = totals.get(station, 0) + (berilgan or 0)

        self.stdout.write(self.style.SUCCESS(f"\nImport tugadi: {created} yozuv, {skipped} skip ({date})."))
        self.stdout.write("Stansiya bo'yicha 'berilgan' jami (kg):")
        for sid in sorted(totals):
            self.stdout.write(f"  {sid:12} {totals[sid]:>10.0f}")
        self.stdout.write(f"  {'JAMI':12} {sum(totals.values()):>10.0f}")
