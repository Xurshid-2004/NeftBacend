"""
ASGI konfiguratsiyasi — HTTP (Django) + WebSocket (Channels).

WebSocket ulanishlari JWT bilan autentifikatsiya qilinadi (so'rov satridagi
?token=...), so'ng `realtime.routing` orqali consumerga yo'naltiriladi.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Django ilovasini WebSocket importlaridan OLDIN yuklash shart
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402

from realtime.auth import JWTAuthMiddleware  # noqa: E402
from realtime.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": JWTAuthMiddleware(URLRouter(websocket_urlpatterns)),
    }
)
