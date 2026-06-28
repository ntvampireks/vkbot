"""Роутинг обработчиков сообщений."""

import importlib
from pathlib import Path
from typing import Any

from bot.utils.app_logger import get_logger
from bot.handlers.base_handler import BaseHandler

logger = get_logger(__name__)


def create_router() -> dict[str, Any]:
    """Автоматически находит и регистрирует все обработчики."""
    router: dict[str, Any] = {}
    handlers_dir = Path(__file__).parent.parent / 'handlers'

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
        try:
            from bot.handlers import DefaultHandler
            router['unknown'] = DefaultHandler()
            logger.info('Зарегистрирован DefaultHandler для неизвестных intent')
        except ImportError as e:
            logger.error(f'Критическая ошибка: DefaultHandler не найден: {e}')
            raise RuntimeError(
                'DefaultHandler обязателен для работы бота. '
                'Проверьте наличие bot/handlers/default_handler.py'
            ) from e

    return router
