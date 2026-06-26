"""
WebSocket consumer — barcha autentifikatsiyalangan klientlar "updates" guruhiga
qo'shiladi. Submission o'zgarganda backend shu guruhga xabar yuboradi va admin/
worker jadvallar darhol yangilanadi.
"""

from channels.generic.websocket import AsyncJsonWebsocketConsumer

GROUP = "updates"


class UpdatesConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        principal = self.scope.get("principal")
        if principal is None:
            # 4401 — autentifikatsiya yo'q (klient token bilan qayta ulanadi)
            await self.close(code=4401)
            return
        self.principal = principal
        await self.channel_layer.group_add(GROUP, self.channel_name)
        await self.accept()
        await self.send_json({"event": "connected", "role": getattr(principal, "role", "")})

    async def disconnect(self, code):
        try:
            await self.channel_layer.group_discard(GROUP, self.channel_name)
        except Exception:
            pass

    async def receive_json(self, content, **kwargs):
        # Heartbeat/ping
        if isinstance(content, dict) and content.get("type") == "ping":
            await self.send_json({"type": "pong"})

    # group_send type="broadcast.message" -> shu metod chaqiriladi
    async def broadcast_message(self, event):
        await self.send_json(event["data"])
