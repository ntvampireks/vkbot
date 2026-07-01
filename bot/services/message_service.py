"""Сервис отправки сообщений — координатор между очередью и отправкой."""

import logging

from bot.config import Settings
from bot.core.vk_client import VKClient
from bot.services.message_queue import MessageQueue
from bot.services.message_sender import MessageSender
from bot.services.rate_limiter import RateLimiter


class MessageService:
    """Координатор отправки сообщений.

    Интегрирует MessageQueue и MessageSender для отправки сообщений
    через фоновую очередь с повторными попытками.
    """

    def __init__(
        self,
        vk_client: VKClient,
        rate_limiter: RateLimiter,
        settings: Settings,
        logger: logging.Logger | None = None
    ):
        """Инициализация сервиса отправки сообщений.

        Args:
            vk_client: VK API клиент
            rate_limiter: Ограничитель частоты отправки
            settings: Конфигурация бота
            logger: Логгер (опционально)
        """
        self._logger = logger or logging.getLogger(__name__)
        self.queue = MessageQueue(maxsize=settings.message_queue_maxsize)
        self.sender = MessageSender(
            vk_client=vk_client,
            rate_limiter=rate_limiter,
            queue=self.queue,
            settings=settings,
            max_retries=3,
            logger=self._logger
        )

    def start_processing(self) -> None:
        """Запустить фоновый поток обработки очереди."""
        self.sender.start()

    def send(self, peer_id: int, text: str, reply_to: int | None = None) -> bool:
        """Поместить сообщение в очередь для отправки.

        Args:
            peer_id: ID получателя
            text: Текст сообщения
            reply_to: ID сообщения, на которое ответить

        Returns:
            True если сообщение помещено в очередь, False если сервис не запущен
        """
        if not self.sender.is_running:
            self._logger.warning('MessageService не запущен')
            return False
        self.queue.put(peer_id, text, reply_to)
        return True

    def stop(self, timeout: float = 5.0) -> None:
        """Остановить сервис отправки сообщений.

        Args:
            timeout: Максимальное время ожидания в секундах
        """
        self.sender.stop(timeout)