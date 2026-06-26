"""
WebSocket JWT autentifikatsiyasi.

Brauzer WebSocket'da sarlavha qo'shib bo'lmaydi, shuning uchun token so'rov
satrida yuboriladi:  ws://host/ws/updates/?token=<JWT>
`scope["principal"]` ga Principal (yoki None) qo'yiladi.
"""

from urllib.parse import parse_qs


class JWTAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        scope["principal"] = None
        query = parse_qs(scope.get("query_string", b"").decode())
        token = (query.get("token") or [None])[0]
        if token:
            try:
                from accounts.authentication import Principal, decode_token

                scope["principal"] = Principal(decode_token(token))
            except Exception:
                scope["principal"] = None
        return await self.app(scope, receive, send)
