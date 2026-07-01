"""Управление жизненным циклом — graceful shutdown и health-check сервер."""

import logging
import signal
import sys
import threading
from typing import Any

import uvicorn
from pydantic import ValidationError

from bot.core.vk_client import VKClient
from bot.services.message_service import MessageService
from bot.config import Settings

try:
    from bot.api import app
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

logger = logging.getLogger(__name__)


def graceful_shutdown(vk_client: VKClient | None, message_service: MessageService | None = None) -> None:
    """Корректное завершение работы."""
    logger.info('Получен сигнал завершения...')

    # Остановить отправку сообщений и дождаться очереди
    if message_service:
        try:
            message_service.stop(timeout=5.0)
            logger.info('Очередь сообщений обработана')
        except Exception as e:
            logger.error(f'Ошибка остановки MessageService: {e}')

    # Остановить VK клиент
    if vk_client:
        try:
            vk_client.stop()
            logger.info('VK клиент остановлен')
        except Exception as e:
            logger.error(f'Ошибка остановки VK клиента: {e}')

    logger.info('Завершение работы...')
    sys.exit(0)


def register_signal_handlers(vk_client: VKClient, message_service: MessageService | None = None) -> None:
    """Регистрация обработчиков сигналов для graceful shutdown."""
    signal.signal(signal.SIGINT, lambda *args: graceful_shutdown(vk_client, message_service))
    signal.signal(signal.SIGTERM, lambda *args: graceful_shutdown(vk_client, message_service))


def start_health_server(settings: Settings) -> threading.Thread | None:
    """Запустить health-check сервер в фоновом потоке.

    Args:
        settings: Экземпляр Settings с конфигурацией хоста и порта

    Returns:
        Поток health-check сервера или None если FastAPI недоступен
    """
    if not FASTAPI_AVAILABLE:
        logger.warning('FastAPI не установлен. Health-check недоступен.')
        return None

    cfg = settings

    def run_server() -> None:
        try:
            uvicorn.run(
                app,
                host=cfg.bot_host,
                port=cfg.bot_port,
                log_level='warning'
            )
        except Exception as e:
            logger.error(f'Ошибка запуска health-check сервера: {e}')

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    logger.info(f'Health-check сервер запущен на http://{cfg.bot_host}:{cfg.bot_port}')
    return thread