"""Глобальный логгер для приложения.

Обеспечивает единый экземпляр логгера, переиспользуемый всеми модулями.
Предотвращает дублирование логов и избыточное создание handlers.
"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

from bot.config import Settings

LOG_LEVEL_MAP = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL,
}

# Глобальный экземпляр логгера
_logger: logging.Logger | None = None


def get_logger(name: str = 'bot', settings: Settings | None = None) -> logging.Logger:
    """Получить логгер для модуля.

    Создаёт корневой логгер один раз при первом вызове,
    затем возвращает дочерние логгеры для конкретных модулей.

    Args:
        name: Имя логгера (обычно __name__)
        settings: Экземпляр Settings для конфигурации логгера.
            При первом вызове должен быть передан для настройки root logger.

    Returns:
        Настроенный логгер
    """
    global _logger
    if _logger is None:
        if settings is not None:
            _logger = _setup_root_logger(settings)
        else:
            # Fallback: базовая конфигурация без settings
            _logger = logging.getLogger('bot')
            _logger.setLevel(logging.DEBUG)
            if not _logger.handlers:
                handler = logging.StreamHandler(sys.stdout)
                handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
                _logger.addHandler(handler)

    return logging.getLogger(name)


def _setup_root_logger(settings: Settings) -> logging.Logger:
    """Настраивает корневой логгер с записью в консоль и файлы.

    Создаётся один раз при старте приложения.

    Args:
        settings: Экземпляр Settings с конфигурацией логгера
    """
    level = LOG_LEVEL_MAP.get(settings.log_level.upper(), logging.DEBUG)

    # Создаём корневой логгер
    root_logger = logging.getLogger('bot')
    root_logger.setLevel(level)

    # Предотвращаем дублирование: проверяем, нет ли уже handlers
    if root_logger.handlers:
        return root_logger

    # Детальный формат для файлов
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - '
        '[%(filename)s:%(lineno)d] - %(message)s'
    )
    # Краткий формат для консоли
    console_formatter = logging.Formatter('%(levelname)s - %(message)s')

    # Консольный handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)

    # Создаем директорию для логов
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(exist_ok=True)

    # Все логи
    all_logs_handler = RotatingFileHandler(
        log_dir / 'all.log',
        maxBytes=50 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    all_logs_handler.setFormatter(file_formatter)
    all_logs_handler.setLevel(logging.DEBUG)
    root_logger.addHandler(all_logs_handler)

    # Только ошибки
    error_handler = RotatingFileHandler(
        log_dir / 'errors.log',
        maxBytes=50 * 1024 * 1024,
        backupCount=10,
        encoding='utf-8'
    )
    error_handler.setFormatter(file_formatter)
    error_handler.setLevel(logging.ERROR)
    root_logger.addHandler(error_handler)

    return root_logger
