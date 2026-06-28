"""Точка входа для VK бота."""

import logging
import sys

from pydantic import ValidationError

from bot.config import Settings
from bot.core.vk_client import VKClient
from bot.core.event_handler import EventHandler
from bot.domains.message import Message
from bot.services.message_service import MessageService
from bot.services.dialog_service import DialogService
from bot.services.intent_classifier import IntentClassifier
from bot.services.rate_limiter import RateLimiter
from bot.core.openai_client import OpenAIClient
from bot.orchestration import create_router
from bot.orchestration.message_processor import MessageProcessor
from bot.lifecycle import register_signal_handlers, start_health_server
from bot.utils.inject import get_default_logger, get_metrics
from bot.utils.message_validator import has_mention
from storage.db import init_db

logger = get_default_logger(__name__)


def main() -> None:
    """Запуск VK бота."""
    try:
        settings = Settings()
    except ValidationError as e:
        logger.error(f'Ошибка конфигурации: {e}')
        logger.error('Проверьте .env файл и убедитесь, что все обязательные переменные установлены:')
        logger.error('  - VK_GROUP_TOKEN: токен VK сообщества')
        logger.error('  - VK_GROUP_ID: ID VK сообщества')
        logger.error('  - VK_BOT_NAME: имя бота для упоминаний')
        sys.exit(1)

    init_db()
    start_health_server(settings)

    # Явная инициализация зависимостей
    logger = get_default_logger('bot')
    metrics = get_metrics()

    vk_client = VKClient(settings, logger)
    rate_limiter = RateLimiter()
    message_service = MessageService(vk_client, rate_limiter, settings, logger)
    message_service.start_processing()

    register_signal_handlers(vk_client, message_service)
    dialog_service = DialogService(settings, logger)

    # Инициализация LLM клиента и классификатора
    llm_client = OpenAIClient(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model_name
    )
    router = create_router(llm_client=llm_client)
    classifier = IntentClassifier(router=router, llm_client=llm_client)

    processor = MessageProcessor(dialog_service, message_service, router, classifier, metrics, settings, logger)

    logger.info('Бот запущен...')

    def on_message(message: Message):
        if not has_mention(message, settings.vk_bot_name):
            logger.debug('Бот не упомянут, пропускаем')
            return

        if message.attachments:
            message_service.send(message.peer_id or message.user_id,
                'Извините, я пока не умею обрабатывать вложения (фото, видео, файлы). Напишите текстовое сообщение.',
                reply_to=message.id)
            return

        processor.process(message)

    bot_user_id = -int(settings.vk_group_id_int) if settings.vk_group_id else None
    event_handler = EventHandler(on_message, bot_user_id=bot_user_id, settings=settings, logger=logger)
    vk_client.run_forever(event_handler.handle_event)


if __name__ == '__main__':
    main()