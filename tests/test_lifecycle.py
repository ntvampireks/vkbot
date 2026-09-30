"""Тесты предупреждения о сетевой экспозиции health-сервера."""

import logging

import pytest

from bot.config import Settings
from bot.lifecycle.shutdown import start_health_server


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
def no_uvicorn(monkeypatch):
    """Не запускать реальный uvicorn в тесте."""
    monkeypatch.setattr('bot.lifecycle.shutdown.uvicorn.run', lambda *a, **k: None)


@pytest.mark.parametrize('host', ['0.0.0.0', '192.168.1.50'])
def test_warning_when_health_api_exposed(host, caplog, no_uvicorn):
    with caplog.at_level(logging.WARNING):
        start_health_server(make_settings(bot_host=host, bot_port=13999))
    assert 'без аутентификации' in caplog.text


@pytest.mark.parametrize('host', ['localhost', '127.0.0.1'])
def test_no_warning_when_loopback(host, caplog, no_uvicorn):
    with caplog.at_level(logging.WARNING):
        start_health_server(make_settings(bot_host=host, bot_port=13999))
    assert 'без аутентификации' not in caplog.text
