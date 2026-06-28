"""Dependency Injection контейнер для приложения."""

import logging
from typing import Protocol, runtime_checkable

from bot.utils.metrics import MetricsCollector, get_metrics as _get_metrics


@runtime_checkable
class Logger(Protocol):
    """Интерфейс для логгера."""

    def debug(self, msg: str, *args, **kwargs) -> None:
        """Логировать на уровне DEBUG."""
        ...

    def info(self, msg: str, *args, **kwargs) -> None:
        """Логировать на уровне INFO."""
        ...

    def warning(self, msg: str, *args, **kwargs) -> None:
        """Логировать на уровне WARNING."""
        ...

    def error(self, msg: str, *args, **kwargs) -> None:
        """Логировать на уровне ERROR."""
        ...

    def critical(self, msg: str, *args, **kwargs) -> None:
        """Логировать на уровне CRITICAL."""
        ...


def get_default_logger(name: str = 'bot') -> logging.Logger:
    """Получить стандартный логгер Python.

    Args:
        name: Имя логгера (обычно __name__)

    Returns:
        Настроенный логгер
    """
    return logging.getLogger(name)


def get_metrics() -> MetricsCollector:
    """Получить глобальный экземпляр метрик.

    Примечание: метрики создаются один раз в main.py и передаются явно через DI.
    """
    return _get_metrics()