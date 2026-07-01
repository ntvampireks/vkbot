from vk_api.longpoll import VkEventType
from typing import Callable, Any
import logging
import time

from bot.domains.message import Message
from bot.utils.deduplication import MessageDeduplicator
from bot.utils.per_user_limiter import PerUserRateLimiter
from bot.utils.message_validator import sanitize_text
from bot.config import Settings


class EventHandler:
    """Обработчик событий VK LongPoll.

    Преобразует сырые события VK в Message объекты, выполняет фильтрацию
    (дубликаты, per-user rate limiting, исходящие сообщения) и передаёт
    валидированные сообщения в callback.
    """

    def __init__(
        self,
        on_message_callback: Callable[[Message], None],
        bot_user_id: int | None = None,
        settings: Settings = None,
        logger: logging.Logger = None
    ):
        """Инициализирует обработчик событий.

        Args:
            on_message_callback: Функция-колбэк для обработки валидированных сообщений
            bot_user_id: ID бота для фильтрации собственных сообщений
            settings: Конфигурация бота
            logger: Логгер (опционально)
        """
        self.on_message: Callable[[Message], None] = on_message_callback
        self.bot_user_id: int | None = bot_user_id
        self._settings = settings
        self._logger = logger
        self.deduplicator = MessageDeduplicator(
            max_size=self._settings.dedup_max_size,
            ttl_seconds=self._settings.dedup_ttl_seconds
        )
        self.per_user_limiter = PerUserRateLimiter(
            max_requests=self._settings.per_user_max_requests,
            window_seconds=self._settings.per_user_window_seconds
        )

    def handle_event(self, event: dict[str, Any]) -> None:
        """Обрабатывает событие от VK LongPoll.

        Выполняет фильтрацию событий:
        - Пропускает не MESSAGE_NEW события
        - Пропускает сообщения от бота
        - Пропускает дубликаты (по message_id)
        - Пропускает сообщения от пользователей превысивших лимит
        - Валидирует и санитизирует текст

        Args:
            event: Сырое событие от VK LongPoll
        """
        # Приводим тип к int для корректного сравнения (VK может вернуть строку '4')
        event_type = event.get("type")
        if isinstance(event_type, str):
            event_type = int(event_type)
        if event_type != VkEventType.MESSAGE_NEW:
            return

        message_id = event.get("message_id", 0)
        user_id = event.get("user_id", 0)

        # Пропускаем сообщения от бота (по user_id)
        self._logger.debug(f'Проверка бота: bot_user_id={self.bot_user_id}, user_id={user_id}')
        if self.bot_user_id and user_id == self.bot_user_id:
            self._logger.info(f'Сообщение от бота {message_id}, пропускаем')
            return

        if self.deduplicator.is_duplicate(message_id):
            self._logger.debug(f'Дубликат события, пропускаем: message_id={message_id}')
            return

        # Проверка per-user rate limiter (атомарная операция)
        if not self.per_user_limiter.try_acquire(user_id):
            wait_time = self.per_user_limiter.get_wait_time(user_id)
            self._logger.warning(f'Пользователь {user_id} превысил лимит сообщений. Ожидание: {wait_time:.1f}с')
            return

        try:
            message = Message.from_vk_event(event)

            # Дополнительная проверка: исходящие сообщения
            if message.out == 1:
                self._logger.debug(f'Исходящее сообщение {message_id}, пропускаем')
                return

            # Валидация и санитизация текста
            try:
                message.text = sanitize_text(message.text, settings=self._settings)
            except ValueError as e:
                self._logger.warning(f'Ошибка валидации сообщения {message_id}: {e}')
                return

            self._logger.info(f'Получено сообщение {message_id} от user_id={message.user_id}: {message.text[:50]}')
            self.on_message(message)
        except Exception as e:
            self._logger.error(f'Ошибка обработки события: {e}', exc_info=True)