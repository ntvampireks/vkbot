"""Модули жизненного цикла — graceful shutdown и health-check."""

from bot.lifecycle.shutdown import graceful_shutdown, register_signal_handlers, start_health_server

__all__ = ['graceful_shutdown', 'register_signal_handlers', 'start_health_server']
