"""Per-user rate limiter для защиты от флуда."""

import threading
from collections import defaultdict
from typing import Optional
import time

class PerUserRateLimiter:
    """Ограничитель частоты сообщений по пользователям.

    Позволяет настроить максимальное количество сообщений от одного пользователя
    за заданный временной интервал.

    Example:
        limiter = PerUserRateLimiter(max_requests=10, window_seconds=60)
        if limiter.is_allowed(user_id=123):
            limiter.record_request(user_id=123)
            # Обработать сообщение
        else:
            # Отклонить сообщение (флуд)
    """

    def __init__(
        self,
        max_requests: int = 10,
        window_seconds: int = 60,
        cleanup_interval: int = 300
    ):
        """Инициализация лимитера.

        Args:
            max_requests: Максимальное количество сообщений от пользователя за окно
            window_seconds: Размер временного окна в секундах
            cleanup_interval: Интервал очистки старых записей в секундах
        """
        if max_requests < 1:
            raise ValueError("max_requests должен быть >= 1")
        if window_seconds < 1:
            raise ValueError("window_seconds должен быть >= 1")

        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.cleanup_interval = cleanup_interval

        # user_id -> список временных меток запросов
        self._user_requests: dict[int, list[float]] = defaultdict(list)
        self._lock = threading.Lock()
        self._last_cleanup: float = 0

    def is_allowed(self, user_id: int) -> bool:
        """Проверяет, может ли пользователь отправить сообщение.

        Args:
            user_id: ID пользователя VK

        Returns:
            True если сообщение разрешено, False если пользователь превысил лимит
        """
        with self._lock:
            self._cleanup_user_requests(user_id, time.time())
            return len(self._user_requests[user_id]) < self.max_requests

    def try_acquire(self, user_id: int) -> bool:
        """Проверяет лимит и записывает запрос в одной атомарной операции.

        Args:
            user_id: ID пользователя VK

        Returns:
            True если запрос разрешён и записан, False если лимит превышен
        """
        with self._lock:
            self._cleanup_user_requests(user_id, time.time())

            if len(self._user_requests[user_id]) >= self.max_requests:
                return False

            self._user_requests[user_id].append(time.time())
            return True

    def record_request(self, user_id: int) -> None:
        """Записывает запрос пользователя.

        Deprecated: используйте try_acquire() вместо раздельных is_allowed() + record_request().

        Args:
            user_id: ID пользователя VK
        """
        with self._lock:
            self._user_requests[user_id].append(time.time())

    def get_remaining_requests(self, user_id: int) -> int:
        """Возвращает количество оставшихся запросов для пользователя.

        Args:
            user_id: ID пользователя VK

        Returns:
            Количество оставшихся разрешённых сообщений
        """
        with self._lock:
            self._cleanup_user_requests(user_id, time.time())
            return max(0, self.max_requests - len(self._user_requests[user_id]))

    def get_wait_time(self, user_id: int) -> Optional[float]:
        """Возвращает время ожидания до следующего разрешённого запроса.

        Args:
            user_id: ID пользователя VK

        Returns:
            Время в секундах до разрешения следующего запроса, или None если запрос разрешён
        """
        with self._lock:
            self._cleanup_user_requests(user_id, time.time())

            if len(self._user_requests[user_id]) < self.max_requests:
                return None

            # Найти самое старое запрос в окне и вычислить время до его истечения
            oldest_request = min(self._user_requests[user_id])
            wait_time = (oldest_request + self.window_seconds) - time.time()
            return max(0, wait_time)

    def reset(self, user_id: int) -> None:
        """Сбрасывает счётчик запросов для пользователя.

        Args:
            user_id: ID пользователя VK
        """
        with self._lock:
            self._user_requests[user_id] = []

    def reset_all(self) -> None:
        """Сбрасывает все счётчики."""
        with self._lock:
            self._user_requests.clear()

    def cleanup_old_entries(self) -> int:
        """Очищает старые записи из всех пользователей.

        Returns:
            Количество удалённых записей
        """
        with self._lock:
            now = time.time()
            removed_count = 0

            for user_id in list(self._user_requests.keys()):
                old_count = len(self._user_requests[user_id])
                self._cleanup_user_requests(user_id, now)
                removed_count += old_count - len(self._user_requests[user_id])

                # Удаляем пустые записи
                if not self._user_requests[user_id]:
                    del self._user_requests[user_id]

            self._last_cleanup = now
            return removed_count

    def _cleanup_user_requests(self, user_id: int, now: float) -> None:
        """Вспомогательный метод для очистки старых запросов пользователя.

        Args:
            user_id: ID пользователя
            now: текущая временная метка
        """
        window_start = now - self.window_seconds
        self._user_requests[user_id] = [
            ts for ts in self._user_requests[user_id]
            if ts > window_start
        ]

        # Удаляем запись пользователя, если список стал пустым
        if not self._user_requests[user_id]:
            del self._user_requests[user_id]
        
