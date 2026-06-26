"""
Kod-asosli JWT autentifikatsiya.

Firestore'da auth `active_sessions/{uid}` -> `access_codes/{code}` zanjiri orqali
ishlardi. Bu yerda login paytida kirish kodi tekshiriladi va 12 soatlik JWT
beriladi. Har bir so'rovda `CodeJWTAuthentication` tokenni dekod qilib,
yengil `Principal` (foydalanuvchi o'rnida) quradi — Django User jadvali shart emas.
"""

from __future__ import annotations

import datetime as dt

import jwt
from django.conf import settings
from rest_framework import authentication, exceptions

JWT_CFG = settings.AUTH_JWT


class Principal:
    """request.user o'rnida turadigan yengil obyekt."""

    is_authenticated = True
    is_anonymous = False

    def __init__(self, payload: dict):
        self.payload = payload
        self.code = payload.get("sub", "")
        self.role = payload.get("role", "")
        self.stationId = payload.get("stationId")
        self.nodeId = payload.get("nodeId")
        self.displayName = payload.get("displayName", "")
        self.codeType = payload.get("codeType")
        self.uid = payload.get("uid", "")

    @property
    def is_admin(self) -> bool:
        return self.role in ("admin", "developer")

    @property
    def is_developer(self) -> bool:
        return self.role == "developer"

    @property
    def is_worker(self) -> bool:
        return self.role == "worker"

    def __str__(self):
        return f"{self.code} ({self.role})"


def create_access_token(session: dict) -> dict:
    """Sessiya ma'lumotidan JWT yaratadi. Frontend Session shakliga mos qaytaradi."""
    now = dt.datetime.now(dt.timezone.utc)
    lifetime = dt.timedelta(hours=JWT_CFG["ACCESS_TOKEN_LIFETIME_HOURS"])
    exp = now + lifetime

    payload = {
        "sub": session["code"],
        "role": session["role"],
        "stationId": session.get("stationId"),
        "nodeId": session.get("nodeId"),
        "displayName": session.get("displayName", ""),
        "codeType": session.get("codeType"),
        "uid": session.get("uid", ""),
        "iss": JWT_CFG["ISSUER"],
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    token = jwt.encode(
        payload, JWT_CFG["SIGNING_KEY"], algorithm=JWT_CFG["ALGORITHM"]
    )
    return {
        "token": token,
        "expiresAt": int(exp.timestamp() * 1000),
        "session": {
            "code": session["code"],
            "role": session["role"],
            "nodeId": session.get("nodeId"),
            "stationId": session.get("stationId"),
            "displayName": session.get("displayName", ""),
            "expiresAt": int(exp.timestamp() * 1000),
        },
    }


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            JWT_CFG["SIGNING_KEY"],
            algorithms=[JWT_CFG["ALGORITHM"]],
            issuer=JWT_CFG["ISSUER"],
        )
    except jwt.ExpiredSignatureError:
        raise exceptions.AuthenticationFailed("Token muddati tugagan.")
    except jwt.InvalidTokenError:
        raise exceptions.AuthenticationFailed("Yaroqsiz token.")


class CodeJWTAuthentication(authentication.BaseAuthentication):
    """`Authorization: Bearer <token>` sarlavhasini tekshiradi."""

    keyword = "Bearer"

    def authenticate(self, request):
        auth_header = authentication.get_authorization_header(request).split()
        if not auth_header:
            return None
        if auth_header[0].lower() != self.keyword.lower().encode():
            return None
        if len(auth_header) == 1:
            raise exceptions.AuthenticationFailed("Token berilmagan.")
        if len(auth_header) > 2:
            raise exceptions.AuthenticationFailed("Token formati noto'g'ri.")

        token = auth_header[1].decode()
        payload = decode_token(token)
        return (Principal(payload), token)

    def authenticate_header(self, request):
        return self.keyword
