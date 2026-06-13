import signal
import sys
import importlib
import time
from pathlib import Path
import threading

import storage.db as db

from bot.config import get_settings
from pydantic import ValidationError
from bot.utils.logger import setup_logger
from bot.utils.metrics import get_metrics
from bot.core.vk_client import VKClient
from bot.domains.message import Message
from bot.domains.dialog import Dialog
from bot.services.message_service import MessageService
from bot.services.dialog_service import DialogService
from bot.services.intent_classifier import IntentClassifier
from bot.services import RateLimiter
from bot.core import EventHandler

try:
    import uvicorn
    from bot.api import app
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

logger = setup_logger(__name__)

# Глобальные переменные для graceful shutdown
#_vk_client: VKClient | None = None
#_dialog_service: DialogService | None = None


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


def graceful_shutdown(vk_client: VKClient | None):
    """Корректное завершение работы."""
    logger.info('Получен сигнал завершения...')

    if vk_client:
        try:
            vk_client.stop()
        except Exception as e:
            logger.error(f'Ошибка остановки VK клиента: {e}')

    logger.info('Завершение работы...')
    sys.exit(0)


def start_health_server():
    """Запустить health-check сервер в фоновом потоке."""
    if not FASTAPI_AVAILABLE:
        logger.warning('FastAPI не установлен. Health-check недоступен.')
        return None

    settings = get_settings()

    def run_server():
        try:
            uvicorn.run(
                app,
                host=settings.bot_host,
                port=settings.bot_port,
                log_level='warning'
            )
        except Exception as e:
            logger.error(f'Ошибка запуска health-check сервера: {e}')

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    logger.info(f'Health-check сервер запущен на http://{settings.bot_host}:{settings.bot_port}')
    return thread


def process_message(message: Message, dialog_service: DialogService, message_service: MessageService, router: dict, classifier: IntentClassifier, settings):
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

        # Записать время обработки
        duration = time.time() - start_time
        metrics.record_processing_time(duration)
    except Exception as e:
        logger.error(f'Ошибка обработки сообщения: {e}')
        metrics.record_message_error()
        raise


def main():
    global _vk_client, _dialog_service

    try:
        settings = get_settings()
    except ValidationError as e:
        logger.error(f'Ошибка конфигурации: {e}')
        logger.error('Проверьте .env файл и убедитесь, что все обязательные переменные установлены:')
        logger.error('  - VK_GROUP_TOKEN: токен VK сообщества')
        logger.error('  - VK_GROUP_ID: ID VK сообщества')
        logger.error('  - VK_BOT_NAME: имя бота для упоминаний')
        sys.exit(1)

    db.init_db()

    # Запускаем health-check сервер
    start_health_server()

    _vk_client = VKClient()
    rate_limiter = RateLimiter()
    message_service = MessageService(_vk_client, rate_limiter)
    _dialog_service = DialogService()
    classifier = IntentClassifier()
    router = create_router()

    # Название бота для проверки упоминания (можно настроить через .env)
    BOT_NAME = settings.vk_bot_name or 'Бот'

    logger.info('Бот запущен...')

    def on_message(message: Message):
        # Проверяем, упомянут ли бот
        if not classifier.has_mention(message, BOT_NAME):
            logger.debug('Бот не упомянут, пропускаем')
            return

        # Проверяем вложения
        if message.attachments:
            message_service.send(message.peer_id or message.user_id,
                'Извините, я пока не умею обрабатывать вложения (фото, видео, файлы). Напишите текстовое сообщение.',
                reply_to=message.id)
            return

        process_message(message, _dialog_service, message_service, router, classifier, settings)

    # Обработка Ctrl+C и SIGTERM
    signal.signal(signal.SIGINT, lambda *args: graceful_shutdown(_vk_client))
    signal.signal(signal.SIGTERM, lambda *args: graceful_shutdown(_vk_client))

    # ID бота для фильтрации собственных сообщений (отрицательный ID сообщества)
    bot_user_id = -int(settings.vk_group_id_int) if settings.vk_group_id else None

    event_handler = EventHandler(on_message, bot_user_id=bot_user_id)
    _vk_client.run_forever(event_handler.handle_event)


if __name__ == '__main__':
    main()
