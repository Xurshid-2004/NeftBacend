"""
Paginatsiya sinflari.

DIQQAT — bu ALOHIDA modul (`common/drf.py` ichida emas). Sabab: DRF
`DEFAULT_PAGINATION_CLASS` ni `rest_framework.generics` moduli o'zi yuklanayotgan
paytda o'qiydi. Agar paginatsiya sinfi `viewsets`/`serializers` import qiladigan
modulda tursa, aylanma import hosil bo'ladi:

    generics -> (sozlama) -> common.drf -> viewsets -> generics (hali tayyor emas)

Shu sababli bu fayl FAQAT `rest_framework.pagination` ni import qiladi.
"""

from __future__ import annotations

from rest_framework.pagination import LimitOffsetPagination


class CappedLimitOffsetPagination(LimitOffsetPagination):
    """
    Standart LimitOffsetPagination + `limit` uchun yuqori chegara.

    Chegarasiz holatda klient `?limit=999999` yuborib butun jadvalni bitta
    javobga tortishi mumkin edi. Backend bitta daphne jarayoni bo'lgani uchun
    bunday so'rov serverni xotira va CPU bo'yicha cho'ktiradi, o'sha paytda
    BOSHQA hamma foydalanuvchi kutib qoladi.

    5000 — hozirgi eng katta chaqiruvdan (fuel-records `limit=4000`) yuqori,
    shuning uchun mavjud so'rovlarning birortasi ham cheklanmaydi.
    `default_limit` ataylab belgilanmagan: u avvalgidek settings dagi
    `PAGE_SIZE` (100) dan olinadi, ya'ni `limit` bermagan chaqiruvlar uchun
    hech narsa o'zgarmaydi.
    """

    max_limit = 5000
