"""
Sync kontekstdan (DRF view / service) WebSocket guruhiga xabar yuborish.
Channel layer mavjud bo'lmasa yoki xato bo'lsa — jim o'tadi (asosiy oqimni buzmaydi).
"""

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

GROUP = "updates"


def broadcast(data: dict) -> None:
    layer = get_channel_layer()
    if layer is None:
        return
    try:
        async_to_sync(layer.group_send)(
            GROUP, {"type": "broadcast.message", "data": data}
        )
    except Exception:
        pass


def broadcast_submission(
    action: str,
    *,
    station_id=None,
    category=None,
    submission_id=None,
) -> None:
    """action: create | update | delete"""
    broadcast(
        {
            "topic": "submissions",
            "action": action,
            "stationId": station_id,
            "category": category,
            "id": str(submission_id) if submission_id is not None else None,
        }
    )
