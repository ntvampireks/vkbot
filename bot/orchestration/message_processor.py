"""Обработка сообщений."""

import time
import traceback
import logging
from typing import Any

from bot.domains.message import Message
from bot.domains.dialog import Dialog
from bot.utils.message_validator import sanitize_text
from bot.services.dialog_service import DialogService
from bot.services.message_service import MessageService
from bot.services.intent_classifier import IntentClassifier
from bot.utils.inject import get_default_logger


class MessageProcessor:
    """Оркестратор обработки сообщений.

    Координирует этапы обработки:
    1. Подготовка контекста диалога
    2. Классификация и обработка
    3. Отправка ответа
    4. Сохранение истории
    """

    def __init__(
        self,
        dialog_service: DialogService,
        message_service: MessageService,
        router: dict[str, Any],
        classifier: IntentClassifier,
        metrics: Any,
        settings: Any,
        logger: logging.Logger | None = None,
    ):
        """Инициализирует процессор сообщений.

        Args:
            dialog_service: Сервис управления диалогами
            message_service: Сервис отправки сообщений
            router: Роутер с зарегистрированными обработчиками
            classifier: Классификатор намерений
            metrics: Сборщик метрик
            settings: Конфигурация бота
            logger: Логгер (опционально)
        """
        self.dialog_service = dialog_service
        self.message_service = message_service
        self.router = router
        self.classifier = classifier
        self.metrics = metrics
        self._settings = settings
        self._logger = logger or get_default_logger(__name__)

    async def process(self, message: Message) -> None:
        """Обработать входящее сообщение и отправить ответ (асинхронно).

        Args:
            message: Входящее сообщение
        """
        self.metrics.record_message_received()

        start_time = time.time()
        try:
            dialog = await self._prepare_dialog_context(message)
            response = await self._handle_message(message, dialog)

            if self._send_response(message, response):
                self.metrics.inc_counter('messages_sent_total')

            await self._finalize_message(message, response)
            self.metrics.record_processing_time(time.time() - start_time)
        except Exception:
            self._logger.error(f'Ошибка обработки сообщения:\n{traceback.format_exc()}')
            self.metrics.record_message_error()
            raise

    async def _prepare_dialog_context(self, message: Message) -> Dialog:
        """Получить или создать диалог для пользователя."""
        dialog = await self.dialog_service.get_dialog_async(message.user_id)

        if dialog is None:
            dialog = Dialog(
                user_id=message.user_id,
                last_active=message.timestamp,
                max_history_messages=self.dialog_service.max_history_messages
            )
            self.dialog_service.register_dialog(dialog)

        return dialog

    async def _handle_message(self, message: Message, dialog: Dialog) -> str:
        """Определить intent, вызвать обработчик и вернуть ответ (асинхронно)."""
        intent = await self.classifier.classify_async(message)
        handler = self.router.get(intent, self.router.get('unknown'))

        try:
            return await handler.handle_async(message, dialog)
        except Exception:
            self._logger.exception(f'Ошибка в обработчике {intent}:')
            return 'Извините, произошла ошибка при обработке запроса.'

    def _send_response(self, message: Message, response: str) -> bool:
        """Отправить ответ бота пользователю."""
        self._logger.debug(f'Отправка ответа: peer_id={message.peer_id}, reply_to={message.id}')
        return self.message_service.send(message.peer_id or message.user_id, response, reply_to=message.id)

    async def _finalize_message(self, message: Message, response: str) -> None:
        """Сохранить историю сообщений и состояние диалога."""
        safe_text = sanitize_text(message.text, settings=self._settings)
        await self.dialog_service.add_message_async(message.user_id, 'user', safe_text)
        await self.dialog_service.add_message_async(message.user_id, 'bot', response)
