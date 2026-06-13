import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

from bot.config import get_settings


def setup_logger(name: str = 'bot', level: int = logging.DEBUG) -> logging.Logger:
    """Настраивает логгер с записью в консоль и файлы с ротацией.

    Создает два файла:
    - logs/all.log — все логи (DEBUG и выше)
    - logs/errors.log — только ошибки (ERROR и выше)

    Args:
        name: Имя логгера
        level: Уровень логирования (по умолчанию DEBUG)

    Returns:
        Настроенный логгер
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
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
        logger.addHandler(console_handler)

        # Создаем директорию для логов
        settings = get_settings()
        log_dir = Path(settings.log_dir)
        log_dir.mkdir(exist_ok=True)

        # Все логи
        all_logs_handler = RotatingFileHandler(
            log_dir / 'all.log',
            maxBytes=50 * 1024 * 1024,  # 50 МБ
            backupCount=5,
            encoding='utf-8'
        )
        all_logs_handler.setFormatter(file_formatter)
        all_logs_handler.setLevel(logging.DEBUG)
        logger.addHandler(all_logs_handler)

        # Только ошибки
        error_handler = RotatingFileHandler(
            log_dir / 'errors.log',
            maxBytes=50 * 1024 * 1024,
            backupCount=10,
            encoding='utf-8'
        )
        error_handler.setFormatter(file_formatter)
        error_handler.setLevel(logging.ERROR)
        logger.addHandler(error_handler)

    return logger
