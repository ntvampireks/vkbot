"""Тесты для DialogService."""

import logging
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from bot.config import Settings
from bot.domains.dialog import Dialog
from bot.services.dialog_service import DialogService


def _create_service() -> DialogService:
    """Создаёт DialogService с mock Settings."""
    settings = Mock(spec=Settings)
    settings.dialog_timeout_hours = 24
    settings.max_history_messages = 10
    settings.max_dialogs_cache = 100
    return DialogService(settings, logging.getLogger('test'))


@pytest.fixture
def service() -> DialogService:
    """DialogService с зарегистрированным диалогом пользователя 1."""
    service = _create_service()
    service.register_dialog(Dialog(user_id=1, last_active=datetime.now()))
    return service


class TestAddMessageAsync:
    """Тесты добавления сообщений в диалог."""

    @pytest.mark.asyncio
    async def test_empty_text_is_skipped(self, service):
        """Пустой текст не должен бросать ValueError (сообщение «@Бот» без текста)."""
        with patch('bot.services.dialog_service.db') as db:
            db.add_message = AsyncMock()
            await service.add_message_async(1, 'user', '')

        db.add_message.assert_not_called()
        assert service._dialogs[1][0].history == []

    @pytest.mark.asyncio
    async def test_whitespace_text_is_skipped(self, service):
        """Текст из пробелов также пропускается."""
        with patch('bot.services.dialog_service.db') as db:
            db.add_message = AsyncMock()
            await service.add_message_async(1, 'bot', '   ')

        db.add_message.assert_not_called()
        assert service._dialogs[1][0].history == []

    @pytest.mark.asyncio
    async def test_none_text_is_skipped(self, service):
        """None вместо текста не вызывает TypeError."""
        with patch('bot.services.dialog_service.db') as db:
            db.add_message = AsyncMock()
            await service.add_message_async(1, 'bot', None)

        db.add_message.assert_not_called()
        assert service._dialogs[1][0].history == []

    @pytest.mark.asyncio
    async def test_non_empty_text_is_saved(self, service):
        """Непустой текст пишется в БД и в кэш."""
        with patch('bot.services.dialog_service.db') as db:
            db.add_message = AsyncMock()
            await service.add_message_async(1, 'user', 'привет')

        db.add_message.assert_awaited_once_with(1, 'user', 'привет', 10)
        assert service._dialogs[1][0].history[0]['text'] == 'привет'
