"""Модули оркестрации — роутинг и обработка сообщений."""

from bot.orchestration.router import create_router
from bot.orchestration.message_processor import process_message

__all__ = ['create_router', 'process_message']
