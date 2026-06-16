"""Сервис отправки сообщений с фоновой очередью."""

import threading
import time
from queue import Queue, Empty
from typing import Optional

from bot.core.vk_client import VKClient
from bot.utils.app_logger import get_logger
from bot.services.rate_limiter import RateLimiter
from bot.config import get_settings

logger = get_logger(__name__)


class MessageService:
    """Сервис отправки сообщений через фоновую очередь."""

    def __init__(self, vk_client: VKClient, rate_limiter: RateLimiter | None = None, max_retries: int = 3):
        self.vk_client = vk_client
        self.rate_limiter = rate_limiter or RateLimiter()
        self.max_retries = max_retries
        self._queue: Queue = Queue()
        self._worker_thread: threading.Thread | None = None
        self._running = False
        settings = get_settings()
        self.send_delay = settings.message_send_delay
        self.retry_delay = settings.message_retry_delay
        self._start_worker()

    def _start_worker(self) -> None:
        """Запускает фоновый поток для отправки сообщений."""
        self._running = True
        self._worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self._worker_thread.start()
        logger.debug('Фоновый поток отправки сообщений запущен')

    def _process_queue(self) -> None:
        """Обработка очереди сообщений в фоновом потоке."""
        while self._running:
            try:
                peer_id, text, reply_to = self._queue.get(timeout=1.0)
                self._send_with_retry(peer_id, text, reply_to)
                self._queue.task_done()
            except Empty:
                continue
            except Exception as e:
                logger.error(f'Ошибка в рабочем потоке: {e}')

    def _send_with_retry(self, peer_id: int, text: str, reply_to: int | None) -> None:
        """Фактическая отправка с retry в фоновом потоке."""
        for attempt in range(self.max_retries):
            try:
                time.sleep(self.send_delay)
                self.rate_limiter.wait_if_needed()
                self.vk_client.send_message(peer_id, text, reply_to=reply_to)
                logger.info(f'Сообщение отправлено: peer_id={peer_id}')
                return
            except Exception as e:
                if attempt < self.max_retries - 1:
                    logger.warning(f'Ошибка отправки (попытка {attempt + 1}/{self.max_retries}): {e}')
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f'Не удалось отправить сообщение после {self.max_retries} попыток: {e}')

    def send(self, peer_id: int, text: str, reply_to: int | None = None) -> bool:
        """Поместить сообщение в очередь для отправки.

        Args:
            peer_id: ID получателя
            text: Текст сообщения
            reply_to: ID сообщения, на которое ответить

        Returns:
            True если сообщение помещено в очередь, False если сервис не запущен
        """
        if not self._running:
            logger.warning('MessageService не запущен')
            return False
        self._queue.put((peer_id, text, reply_to))
        return True

    def stop(self, timeout: float = 5.0) -> None:
        """Остановить фоновый поток и дождаться обработки очереди.

        Args:
            timeout: Максимальное время ожидания в секундах
        """
        logger.info('Остановка MessageService...')
        self._running = False

        # Ждём завершения обработки очереди
        if not self._queue.empty():
            logger.info(f'Ожидание обработки {self._queue.qsize()} сообщений в очереди...')

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=timeout)

        if self._worker_thread and self._worker_thread.is_alive():
            logger.warning('Таймаут ожидания остановки MessageService')
        else:
            logger.info('MessageService остановлен')
