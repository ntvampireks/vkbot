"""Обработка сообщений."""

import time
from typing import Any

from bot.domains.message import Message
from bot.domains.dialog import Dialog
from bot.utils.app_logger import get_logger
from bot.utils.metrics import get_metrics
from bot.services.dialog_service import DialogService
from bot.services.message_service import MessageService
from bot.services.intent_classifier import IntentClassifier

logger = get_logger(__name__)


def process_message(
    message: Message,
    dialog_service: DialogService,
    message_service: MessageService,
    router: dict[str, Any],
    classifier: IntentClassifier,
    settings: Any
) -> None:
    """Обработать входящее сообщение и отправить ответ."""
    metrics = get_metrics()
    metrics.record_message_received()

    start_time = time.time()
    try:
        dialog = dialog_service.get_dialog(message.user_id)

        if dialog is None:
            dialog = Dialog(
                user_id=message.user_id,
                last_active=message.timestamp,
                max_history_messages=settings.max_history_messages
            )

        dialog.add_message('user', message.text)
        dialog_service.save_dialog(dialog)

        intent = classifier.classify(message)
        handler = router.get(intent, router.get('unknown'))

        response = handler.handle(message, dialog)

        logger.debug(f'Отправка ответа: peer_id={message.peer_id}, reply_to={message.id}')
        sent = message_service.send(message.peer_id or message.user_id, response, reply_to=message.id)
        if sent:
            metrics.inc_counter('messages_sent_total')

        dialog.add_message('bot', response)
        dialog_service.save_dialog(dialog)

        duration = time.time() - start_time
        metrics.record_processing_time(duration)
    except Exception as e:
        logger.error(f'Ошибка обработки сообщения: {e}')
        metrics.record_message_error()
        raise
