import signal
import sys
import importlib
from pathlib import Path

import storage.db as db

from bot.config import Config
from bot.utils.logger import setup_logger
from bot.core.vk_client import VKClient
from bot.domains.message import Message
from bot.domains.dialog import Dialog
from bot.services.message_service import MessageService
from bot.services.dialog_service import DialogService
from bot.services.intent_classifier import IntentClassifier
from bot.services import RateLimiter
from bot.core import EventHandler


logger = setup_logger(__name__)


def create_router():
    """Автоматически находит и регистрирует все обработчики."""
    router = {}
    handlers_dir = Path(__file__).parent / 'handlers'

    for handler_file in handlers_dir.glob('*_handler.py'):
        if handler_file.name.startswith('base_'):
            continue

        module_name = f'bot.handlers.{handler_file.stem}'
        module = importlib.import_module(module_name)

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type) and
                attr.__module__ == module_name and
                attr.__name__ != 'BaseHandler'):
                try:
                    handler = attr()
                    router[handler.intent] = handler
                except Exception as e:
                    logger.error(f'Ошибка регистрации {attr_name}: {e}')

    if 'unknown' not in router:
        from bot.handlers import DefaultHandler
        router['unknown'] = DefaultHandler()

    return router


def process_message(message: Message, dialog_service: DialogService, message_service: MessageService, router: dict):
    try:
        dialog = dialog_service.get_dialog(message.user_id)

        if dialog is None:
            dialog = Dialog(
                user_id=message.user_id,
                last_active=message.timestamp
            )

        dialog.add_message('user', message.text)
        dialog_service.save_dialog(dialog)

        intent = IntentClassifier().classify(message)
        handler = router.get(intent, router.get('unknown'))

        response = handler.handle(message, dialog)

        message_service.send(message.peer_id or message.user_id, response)

        dialog.add_message('bot', response)
        dialog_service.save_dialog(dialog)
    except Exception as e:
        logger.error(f'Ошибка обработки сообщения: {e}')
        raise


def main():
    Config.validate()
    db.init_db()

    vk_client = VKClient()
    rate_limiter = RateLimiter()
    message_service = MessageService(vk_client, rate_limiter)
    dialog_service = DialogService()
    classifier = IntentClassifier()
    router = create_router()

    # Название бота для проверки упоминания (можно настроить через .env)
    BOT_NAME = Config.VK_BOT_NAME or 'Бот'

    logger.info('Бот запущен...')

    def on_message(message: Message):
        # Проверяем, упомянут ли бот
        if not classifier.has_mention(message, BOT_NAME):
            logger.debug('Бот не упомянут, пропускаем')
            return

        # Проверяем вложения
        if message.attachments:
            message_service.send(message.peer_id or message.user_id,
                'Извините, я пока не умею обрабатывать вложения (фото, видео, файлы). Напишите текстовое сообщение.')
            return

        process_message(message, dialog_service, message_service, router)

    # Обработка Ctrl+C
    def signal_handler(sig, frame):
        logger.info('Завершение работы...')
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # ID бота для фильтрации собственных сообщений (отрицательный ID сообщества)
    bot_user_id = -int(Config.VK_GROUP_ID) if Config.VK_GROUP_ID else None

    event_handler = EventHandler(on_message, bot_user_id=bot_user_id)
    vk_client.run_forever(event_handler.handle_event)


if __name__ == '__main__':
    main()
