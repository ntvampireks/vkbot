"""Отправка сообщений через VK API с фоновым потоком."""

import logging
import threading
import time
from typing import Callable

from bot.config import Settings
from bot.core.vk_client import VKClient
from bot.services.message_queue import MessageQueue, QueuedMessage
from bot.services.rate_limiter import RateLimiter


class MessageSender:
    """Отправка сообщений через VK API с фоновым потоком и повторными попытками.

    Управляет очередью сообщений и их отправкой через VK API.
    """

    def __init__(
        self,
        vk_client: VKClient,
        rate_limiter: RateLimiter,
        queue: MessageQueue,
        settings: Settings,
        max_retries: int = 3,
        logger: logging.Logger | None = None
    ):
        """Инициализация отправителя.

        Args:
            vk_client: VK API клиент
            rate_limiter: Ограничитель частоты отправки
            queue: Очередь сообщений
            settings: Конфигурация бота
            max_retries: Максимальное количество попыток отправки
            logger: Логгер (опционально)
        """
        self.vk_client = vk_client
        self.rate_limiter = rate_limiter
        self.queue = queue
        self.max_retries = max_retries
        self.send_delay = settings.message_send_delay
        self.retry_delay = settings.message_retry_delay
        self.api_timeout = settings.message_api_timeout
        self._logger = logger or logging.getLogger(__name__)

        self._running = False
        self._worker_thread: threading.Thread | None = None

    def start(self) -> None:
        """Запустить фоновый поток отправки."""
        self._running = True
        self._worker_thread = threading.Thread(target=self._process, daemon=True)
        self._worker_thread.start()
        self._logger.debug('MessageSender запущен')

    def stop(self, timeout: float = 5.0) -> None:
        """Остановить фоновый поток отправки.

        Args:
            timeout: Максимальное время ожидания в секундах
        """
        self._logger.info('Остановка MessageSender...')
        self._running = False

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=timeout)

        if self._worker_thread and self._worker_thread.is_alive():
            self._logger.warning('Таймаут ожидания остановки MessageSender')
        else:
            self._logger.info('MessageSender остановлен')

    def _process(self) -> None:
        """Цикл обработки очереди отправки."""
        while self._running:
            message = self.queue.get(timeout=1.0)
            if message is None:
                continue

            try:
                self._send_with_retry(message)
            except Exception as e:
                self._logger.error(f'Не удалось отправить сообщение для peer_id={message.peer_id} после {self.max_retries} попыток: {e}')
            finally:
                self.queue.mark_done(message)

    def _send_with_retry(self, message: QueuedMessage) -> None:
        """Отправить сообщение с повторными попытками.

        Args:
            message: Сообщение для отправки
        """
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                time.sleep(self.send_delay)
                self.rate_limiter.wait_if_needed()
                self.vk_client.send_message(
                    message.peer_id, message.text,
                    reply_to=message.reply_to,
                    timeout=self.api_timeout
                )
                self._logger.info(f'Сообщение отправлено: peer_id={message.peer_id}')
                return
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    self._logger.warning(
                        f'Ошибка отправки (попытка {attempt + 1}/{self.max_retries}): {e}'
                    )
                    time.sleep(self.retry_delay)
                else:
                    self._logger.error(f'Не удалось отправить сообщение после {self.max_retries} попыток: {e}')

        if last_error:
            raise last_error

    @property
    def is_running(self) -> bool:
        """Проверить запущен ли отправитель."""
        return self._running