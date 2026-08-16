"""Face ID shablonlarini yangi algoritm (oval niqob + blok vaznlari) bo'yicha
qayta quradi.

NEGA MIGRATSIYADA
─────────────────
`TEMPLATE_VERSION` ko'tarilgani uchun eski shablonlar e'tiborga olinmaydi va
qayta qurilmasa Face ID jimgina ishlamay qo'yardi (odamlar parol bilan
kiraverardi — ya'ni xavfsiz, lekin kutilmagan holat). Buyruqni qo'lda ishga
tushirishni ESDAN CHIQARISH mumkin, shuning uchun `migrate` ning o'zi hamma
ishni tugatadi.

MA'LUMOTGA ZARAR YO'Q: suratlar ham, saqlangan xom kadrlar ham TEGILMAYDI —
faqat ulardan hisoblangan `vectors` qayta yoziladi. Biror yozuv buzuq bo'lsa,
u tashlab ketiladi va deploy to'xtamaydi (odam parol bilan kiraveradi).
"""

from django.db import migrations

from accounts import face
from common.timeutil import now_ms


def rebuild(apps, schema_editor):
    FaceTemplate = apps.get_model("accounts", "FaceTemplate")
    updated = 0
    for record in FaceTemplate.objects.exclude(version=face.TEMPLATE_VERSION):
        lines = [line for line in (record.samples or "").splitlines() if line.strip()]
        if not lines:
            continue
        try:
            vectors = face.templates_from_raw(lines)
        except Exception:  # noqa: BLE001 — deploy hech qanday holatda to'xtamasin
            continue
        if not vectors:
            continue
        record.vectors = "\n".join(vectors)
        record.sampleCount = len(vectors)
        record.version = face.TEMPLATE_VERSION
        record.updatedAt = now_ms()
        record.save(
            update_fields=["vectors", "sampleCount", "version", "updatedAt"]
        )
        updated += 1
    if updated:
        print(f"  Face ID: {updated} ta shablon yangi algoritm bo'yicha qayta qurildi.")


def noop(apps, schema_editor):
    """Orqaga qaytarish: eski kodga qaytilsa, shablonlar o'sha koddagi
    `rebuild_face_templates` bilan tiklanadi (xom kadrlar joyida turibdi)."""


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_accesscode_photo_accesscode_photoupdatedat"),
    ]

    operations = [
        migrations.RunPython(rebuild, noop),
    ]
