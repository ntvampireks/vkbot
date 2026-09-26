from collections import OrderedDict
from threading import Lock
from bot.utils.app_logger import get_logger
import time

logger = get_logger(__name__)


class MessageDeduplicator:
    """Кэш для предотвращения обработки дубликатов сообщений."""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        """Инициализирует дедупликатор сообщений.

        Args:
            max_size: Максимальный размер кэша
            ttl_seconds: TTL записей в секундах
        """
        # Ключ — пара (peer_id, message_id), значение — время обработки
        self._cache: OrderedDict[tuple[int, int], float] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._lock = Lock()

    def is_duplicate(self, peer_id: int, message_id: int) -> bool:
        """Проверяет, было ли уже обработано это сообщение.

        message_id уникален только в пределах диалога, поэтому ключом кэша
        выступает пара (peer_id, message_id).

        Args:
            peer_id: ID диалога
            message_id: ID сообщения внутри диалога

        Returns:
            True если сообщение уже обрабатывалось
        """
        key = (peer_id, message_id)
        with self._lock:
            now = time.time()

            # Удаляем устаревшие записи
            while self._cache:
                oldest_key, oldest_time = next(iter(self._cache.items()))
                if oldest_time < now - self._ttl:
                    self._cache.popitem(last=False)
                else:
                    break

            # Удаляем старые записи, если кэш превышает max_size
            while len(self._cache) >= self._max_size:
                oldest_key, _ = next(iter(self._cache.items()))
                self._cache.pop(oldest_key)
                logger.debug(f'Кэш полон, удаляем oldest_key={oldest_key}')

            # Проверяем, есть ли сообщение в кэше
            if key in self._cache:
                logger.debug(f'Дубликат сообщения, пропускаем: peer_id={peer_id} id={message_id}')
                return True

            # Добавляем в кэш
            self._cache[key] = now
            return False
