"""Тесты MessageProcessor: таймаут диалога (DIALOG_TIMEOUT_HOURS) и touch last_active."""

import logging
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest

from bot.config import Settings
from bot.domains.dialog import Dialog
from bot.domains.message import Message
from bot.orchestration.message_processor import MessageProcessor


def _create_processor() -> MessageProcessor:
    settings = Mock(spec=Settings)
    settings.dialog_timeout_hours = 24
    dialog_service = Mock()
    dialog_service.max_history_messages = 10
    return MessageProcessor(
        dialog_service=dialog_service,
        message_service=Mock(),
        router={},
        classifier=Mock(),
        metrics=Mock(),
        settings=settings,
        logger=logging.getLogger('test'),
    )


def _message() -> Message:
    return Message(id=1, user_id=42, text='привет', timestamp=datetime.now())


class TestPrepareDialogContext:

    @pytest.mark.asyncio
    async def test_new_dialog_created_and_registered(self):
        """Нет диалога в БД — создаётся новый и регистрируется в кэше."""
        processor = _create_processor()
        processor.dialog_service.get_dialog_async = AsyncMock(return_value=None)

        dialog = await processor._prepare_dialog_context(_message())

        assert dialog.user_id == 42
        processor.dialog_service.register_dialog.assert_called_once_with(dialog)

    @pytest.mark.asyncio
    async def test_active_dialog_touched(self):
        """Активный диалог переиспользуется, last_active двигается вперёд."""
        processor = _create_processor()
        old = datetime.now() - timedelta(hours=1)
        dialog = Dialog(user_id=42, last_active=old, state='greeting')
        processor.dialog_service.get_dialog_async = AsyncMock(return_value=dialog)

        result = await processor._prepare_dialog_context(_message())

        assert result is dialog
        assert result.state == 'greeting', 'активный диалог сохраняет state'
        assert result.last_active > old, 'last_active должен обновляться (touch)'

    @pytest.mark.asyncio
    async def test_expired_dialog_reset(self):
        """Истёкший по DIALOG_TIMEOUT_HOURS диалог не переиспользуется."""
        processor = _create_processor()
        expired = Dialog(
            user_id=42,
            last_active=datetime.now() - timedelta(days=30),
            state='awaiting_payment',
            context={'order_id': 555},
        )
        processor.dialog_service.get_dialog_async = AsyncMock(return_value=expired)

        result = await processor._prepare_dialog_context(_message())

        assert result is not expired
        assert result.state is None
        assert result.context == {}
        processor.dialog_service.register_dialog.assert_called_once_with(result)
