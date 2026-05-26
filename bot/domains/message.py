from dataclasses import dataclass
from datetime import datetime


@dataclass
class Message:
    id: int
    user_id: int
    text: str
    timestamp: datetime
    peer_id: int | None = None
    attachments: list = None
    out: int = 0

    @classmethod
    def from_vk_event(cls, event_data: dict) -> 'Message':
        message_data = event_data

        # timestamp может быть int (Unix timestamp) или datetime
        ts = message_data.get('timestamp', 0)
        if isinstance(ts, datetime):
            timestamp = ts
        else:
            timestamp = datetime.fromtimestamp(ts)

        return cls(
            id=message_data.get('message_id', 0),
            user_id=message_data.get('user_id', 0),
            text=message_data.get('text', ''),
            timestamp=timestamp,
            peer_id=message_data.get('peer_id'),
            attachments=message_data.get('attachments', []),
            out=message_data.get('out', 0)
        )
