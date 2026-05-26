import time
from threading import Lock
from bot.utils.logger import setup_logger

logger = setup_logger(__name__)


class RateLimiter:
    """Ограничение скорости отправки сообщений.

    VK API имеет лимит ~3 сообщения в секунду.
    """

    def __init__(self, max_requests: int = 3, period: float = 1.0):
        """
        Args:
            max_requests: Максимум запросов за период
            period: Период в секундах
        """
        self.max_requests = max_requests
        self.period = period
        self.requests: list[float] = []
        self.lock = Lock()

    def wait_if_needed(self):
        """Ждёт, если достигнут лимит запросов."""
        with self.lock:
            now = time.time()
            # Удаляем старые запросы за пределами периода
            self.requests = [t for t in self.requests if now - t < self.period]

            if len(self.requests) >= self.max_requests:
                wait_time = self.period - (now - self.requests[0])
                if wait_time > 0:
                    logger.debug(f'Rate limit reached. Ждём {wait_time:.2f}с')
                    time.sleep(wait_time)
                    # Очищаем после ожидания
                    self.requests = []

            self.requests.append(time.time())
