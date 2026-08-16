"""
Maxsus throttle klasslari.

Standart `ScopedRateThrottle` autentifikatsiyalangan so'rovda `request.user.pk`
ni o'qiydi, bizning yengil `Principal` obyektida esa `pk` yo'q. Shu sababli
kalitni kirish kodi (yoki kod bo'lmasa IP) bo'yicha quradigan alohida klass.
"""

from rest_framework import throttling


class FaceThrottle(throttling.SimpleRateThrottle):
    """Face ID (yuz bo'yicha kirish) uchun tezlik chegarasi.

    Kalit ATAYLAB faqat IP bo'yicha olinadi. `deviceId` ni klient o'zi
    yuboradi — uni har so'rovda o'zgartirib chegarani chetlab o'tish mumkin
    bo'lardi. IP esa klient ixtiyorida emas.

    Tezlik: `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["face"]` (standart 30/min).
    Qurilma darajasidagi qo'shimcha "sovish" (cooldown) `accounts/views.py` da.
    """

    scope = "face"

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class VaultThrottle(throttling.SimpleRateThrottle):
    """"Admin qo'shish" parolini tekshirish uchun tezlik chegarasi.

    Tezlik `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["vault"]` dan olinadi
    (standart 5/min). Hisoblagich server xotirasida — uni brauzerdan
    (localStorage tozalash va h.k.) nolga tushirib bo'lmaydi.
    """

    scope = "vault"

    def get_cache_key(self, request, view):
        ident = getattr(request.user, "code", "") or self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}
