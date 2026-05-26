from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Dialog:
    user_id: int
    last_active: datetime
    state: str | None = None
    context: dict = field(default_factory=dict)
    history: list = field(default_factory=list)

    def is_active(self, timeout_hours: int) -> bool:
        """Проверка, активна ли сессия диалога."""
        delta = datetime.now() - self.last_active
        return delta.total_seconds() < timeout_hours * 3600

    def add_message(self, role: str, text: str):
        """Добавить сообщение в историю."""
        self.history.append({
            'role': role,
            'text': text,
            'timestamp': datetime.now().isoformat()
        })
        # Ограничиваем историю последними 10 сообщениями
        if len(self.history) > 10:
            self.history = self.history[-10:]
