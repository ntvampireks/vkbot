"""Тесты инициализации логгера (замечание №4 код-ревью).

settings должны применяться к логгеру 'bot' даже если модули уже
получили логгеры без settings на этапе импорта.
"""

import logging

import pytest

from bot.config import Settings
from bot.utils import app_logger
from bot.utils.app_logger import get_logger


def make_settings(**overrides) -> Settings:
    """Settings с заглушками обязательных полей, без чтения .env."""
    base = dict(
        vk_group_token='test-token',
        vk_group_id='12345',
        vk_bot_name='testbot',
        llm_base_url='https://llm.example.com/v1',
        _env_file=None,
    )
    base.update(overrides)
    return Settings(**base)


@pytest.fixture
def clean_bot_logger():
    """Чистое глобальное состояние логгера 'bot' до и после теста."""
    root = logging.getLogger('bot')
    saved_level = root.level
    saved_handlers = root.handlers[:]
    saved_state = {
        name: getattr(app_logger, name, None)
        for name in ('_logger', '_configured', '_fallback_handler')
    }

    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()
    app_logger._logger = None
    app_logger._configured = False
    app_logger._fallback_handler = None

    yield root

    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()
    for name, value in saved_state.items():
        setattr(app_logger, name, value)
    root.setLevel(saved_level)
    for handler in saved_handlers:
        root.addHandler(handler)


def test_settings_apply_after_modules_logged_without_them(clean_bot_logger, tmp_path):
    """Как при запуске: модули взяли логгеры при импорте, settings пришли позже."""
    settings = make_settings(log_level='INFO', log_dir=str(tmp_path))

    get_logger('bot.services.example')  # импорт модуля — без settings
    logger = get_logger('bot', settings)  # main() — сразу после загрузки конфигурации

    assert logger.level == logging.INFO, 'LOG_LEVEL должен применяться'

    logger.info('работает')
    logger.debug('детали')
    for handler in logger.handlers:
        handler.flush()

    content = (tmp_path / 'all.log').read_text(encoding='utf-8')
    assert 'работает' in content, 'LOG_DIR: all.log должен писаться'
    assert 'детали' not in content, 'DEBUG ниже LOG_LEVEL=INFO должен отфильтровываться'


def test_console_respects_debug_log_level(clean_bot_logger, tmp_path, capsys):
    """LOG_LEVEL=DEBUG: отладка должна быть видна в консоли, а не только в all.log."""
    settings = make_settings(log_level='DEBUG', log_dir=str(tmp_path))

    logger = get_logger('bot', settings)
    logger.debug('детали')

    assert 'детали' in capsys.readouterr().out


def test_repeated_setup_does_not_duplicate_handlers(clean_bot_logger, tmp_path):
    """Повторные вызовы с settings не плодят вторые копии обработчиков."""
    settings = make_settings(log_level='INFO', log_dir=str(tmp_path))

    root = get_logger('bot', settings)
    handlers_after_first = root.handlers[:]
    get_logger('bot', settings)

    assert root.handlers == handlers_after_first
