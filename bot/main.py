"""Точка входа для VK бота."""

import sys

from pydantic import ValidationError

from bot.config import get_settings
from bot.core.vk_client import VKClient
from bot.core.event_handler import EventHandler
from bot.domains.message import Message
from bot.services.message_service import MessageService
from bot.services.dialog_service import DialogService
from bot.services.intent_classifier import IntentClassifier
from bot.services import RateLimiter
from bot.orchestration import create_router, process_message
from bot.lifecycle import register_signal_handlers, start_health_server
from bot.utils.app_logger import get_logger
from storage.db import init_db

logger = get_logger(__name__)

def main() -> None:
    """Запуск VK бота."""
    try:
        settings = get_settings()
    except ValidationError as e:
        logger.error(f'Ошибка конфигурации: {e}')
        logger.error('Проверьте .env файл и убедитесь, что все обязательные переменные установлены:')
        logger.error('  - VK_GROUP_TOKEN: токен VK сообщества')
        logger.error('  - VK_GROUP_ID: ID VK сообщества')
        logger.error('  - VK_BOT_NAME: имя бота для упоминаний')
        sys.exit(1)

    init_db()
    start_health_server()

    vk_client = VKClient()

    rate_limiter = RateLimiter()
    message_service = MessageService(vk_client, rate_limiter)
    register_signal_handlers(vk_client, message_service)
    dialog_service = DialogService()
    classifier = IntentClassifier()
    router = create_router()

    logger.info('Бот запущен...')

    def on_message(message: Message):
        if not classifier.has_mention(message, settings.vk_bot_name):
            logger.debug('Бот не упомянут, пропускаем')
            return

        if message.attachments:
            message_service.send(message.peer_id or message.user_id,
                'Извините, я пока не умею обрабатывать вложения (фото, видео, файлы). Напишите текстовое сообщение.',
                reply_to=message.id)
            return

        process_message(message, dialog_service, message_service, router, classifier, settings)

    bot_user_id = -int(settings.vk_group_id_int) if settings.vk_group_id else None
    event_handler = EventHandler(on_message, bot_user_id=bot_user_id)
    vk_client.run_forever(event_handler.handle_event)


if __name__ == '__main__':
    main()
