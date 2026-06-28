import time
from collections import deque
from threading import Condition
from bot.utils.app_logger import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """Ограничение скорости отправки сообщений.

    VK API имеет лимит ~3 сообщения в секунду.
    """

    def __init__(self, max_requests: int = 3, period: float = 1.0):
        """Ограничение скорости отправки сообщений.

        VK API имеет лимит ~3 сообщения в секунду.

        Args:
            max_requests: Максимум запросов за период
            period: Период в секундах

        Raises:
            ValueError: Если max_requests < 1 или period < 1
        """
        if max_requests < 1:
            raise ValueError("max_requests должен быть >= 1")
        if period <= 0:
            raise ValueError("period должен быть > 0")

        self.max_requests = max_requests
        self.period = period
        self.requests: deque[float] = deque(maxlen=max_requests)
        self.condition = Condition()

    def wait_if_needed(self):
        """Ждёт, если достигнут лимит запросов."""
        with self.condition:
            while True:
                now = time.time()
                while self.requests and now - self.requests[0] >= self.period:
                    self.requests.popleft()

                if len(self.requests) < self.max_requests:
                    self.requests.append(time.time())
                    return

                wait_time = self.period - (now - self.requests[0])
                if wait_time > 0:
                    logger.debug(f'Rate limit reached. Ждём {wait_time:.2f}с')
                    self.condition.wait(timeout=wait_time)
