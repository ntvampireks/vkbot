from collections import OrderedDict
from threading import Lock
from bot.utils.logger import setup_logger
import time

logger = setup_logger(__name__)


class MessageDeduplicator:
    """Кэш для предотвращения обработки дубликатов сообщений."""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        self._cache = OrderedDict()
        self._ttl = ttl_seconds
        self._lock = Lock()

    def is_duplicate(self, message_id: int) -> bool:
        """Проверяет, был ли уже обработан этот message_id."""
        with self._lock:
            now = time.time()

            # Удаляем устаревшие записи
            while self._cache:
                oldest_id, oldest_time = next(iter(self._cache.items()))
                if oldest_time < now - self._ttl:
                    self._cache.popitem(last=False)
                else:
                    break

            # Проверяем, есть ли message_id в кэше
            if message_id in self._cache:
                logger.debug(f'Дубликат сообщения, пропускаем: id={message_id}')
                return True

            # Добавляем в кэш
            self._cache[message_id] = now
            return False
