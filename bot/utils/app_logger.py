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

# Состояние конфигурации: боевая конфигурация применяется один раз,
# когда прилетают settings, независимо от порядка предыдущих вызовов
_configured = False
_fallback_handler: logging.StreamHandler | None = None


def get_logger(name: str = 'bot', settings: Settings | None = None) -> logging.Logger:
    """Получить логгер для модуля.

    Настраивает логгер 'bot' один раз при первом вызове с settings:
    консоль + файлы согласно LOG_LEVEL/LOG_DIR. Вызовы без settings
    (импорты модулей до main()) временно вешают консольный handler,
    и эта конфигурация заменяется, когда settings приходят.

    Args:
        name: Имя логгера (обычно __name__)
        settings: Экземпляр Settings для конфигурации логгера.

    Returns:
        Настроенный логгер
    """
    global _configured, _fallback_handler
    if not _configured:
        root = logging.getLogger('bot')
        if settings is not None:
            if _fallback_handler is not None:
                root.removeHandler(_fallback_handler)
                _fallback_handler.close()
                _fallback_handler = None
            _setup_root_logger(settings)
            _configured = True
        elif _fallback_handler is None:
            # Fallback: консольная конфигурация до получения settings
            _fallback_handler = logging.StreamHandler(sys.stdout)
            _fallback_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
            root.setLevel(logging.DEBUG)
            root.addHandler(_fallback_handler)

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

    # Консольный handler: уровень наследуется от логгера, то есть равен LOG_LEVEL
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
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
