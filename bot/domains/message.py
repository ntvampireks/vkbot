from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class Message:
    id: int
    user_id: int  # ключ диалога: всегда peer_id (в личных сообщениях он же id автора)
    text: str
    timestamp: datetime
    peer_id: int | None = None
    author_id: int | None = None  # автор сообщения; в беседе VK отдаёт его не всегда
    attachments: list[dict[str, Any]] | None = None
    out: int = 0

    @classmethod
    def from_vk_event(cls, event_data: dict) -> 'Message':
        if not event_data or not isinstance(event_data, dict):
            raise ValueError(f"Invalid event data: expected dict, got {type(event_data).__name__}")

        # message_id обязан быть положительным — ключ дедупликации (peer_id, message_id)
        message_id = event_data.get('message_id')
        if not isinstance(message_id, int) or message_id <= 0:
            raise ValueError(f"Invalid message_id: {message_id!r}")

        # Ключ диалога — user_id (= peer_id, см. комментарий у поля Message.user_id).
        # Если VK не прислал user_id — fallback на peer_id; иначе отклоняем.
        user_id = event_data.get('user_id')
        if not isinstance(user_id, int) or user_id <= 0:
            user_id = event_data.get('peer_id')
            if not isinstance(user_id, int) or user_id <= 0:
                raise ValueError(f"Invalid user_id/peer_id: {user_id!r}")

        # timestamp: datetime или положительный Unix-ts; отсутствие/0 -> эпоха — недопустимо
        ts = event_data.get('timestamp')
        if isinstance(ts, datetime):
            timestamp = ts
        else:
            if not isinstance(ts, (int, float)) or ts <= 0:
                raise ValueError(f"Invalid timestamp: {ts!r}")
            timestamp = datetime.fromtimestamp(ts)

        return cls(
            id=message_id,
            user_id=user_id,
            text=event_data.get('text', ''),
            timestamp=timestamp,
            peer_id=event_data.get('peer_id'),
            author_id=event_data.get('author_id'),
            attachments=event_data.get('attachments', []),
            out=event_data.get('out', 0)
        )
