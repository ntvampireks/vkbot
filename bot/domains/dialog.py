import threading
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Dialog:
    user_id: int
    last_active: datetime
    state: str | None = None
    context: dict = field(default_factory=dict)
    history: list = field(default_factory=list)
    max_history_messages: int = 10
    _lock: threading.Lock = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        """Инициализация lock после создания объекта.

        Гарантирует корректную работу при десериализации.
        """
        if not hasattr(self, '_lock') or self._lock is None:
            object.__setattr__(self, '_lock', threading.Lock())

    def is_active(self, timeout_hours: int) -> bool:
        """Проверка, активна ли сессия диалога."""
        delta = datetime.now() - self.last_active
        return delta.total_seconds() < timeout_hours * 3600

    def add_message(self, role: str, text: str) -> None:
        """Добавить сообщение в историю.

        Потокобезопасный метод с использованием блокировки.

        Args:
            role: Роль ('user' или 'bot')
            text: Текст сообщения
        """
        with self._lock:
            self.history.append({
                'role': role,
                'text': text,
                'timestamp': datetime.now().isoformat()
            })
            if len(self.history) > self.max_history_messages:
                self.history = self.history[-self.max_history_messages:]

    def get_history(self) -> list:
        """Получить копию истории сообщений.

        Returns:
            Копия истории сообщений (безопасная для чтения)
        """
        with self._lock:
            return list(self.history)

    def update_context(self, key: str, value: str) -> None:
        """Обновить контекст диалога.

        Args:
            key: Ключ контекста
            value: Значение
        """
        with self._lock:
            self.context[key] = value

    def get_context(self) -> dict:
        """Получить копию контекста.

        Returns:
            Копия контекста (безопасная для чтения)
        """
        with self._lock:
            return dict(self.context)
