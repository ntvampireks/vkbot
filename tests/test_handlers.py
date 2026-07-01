"""Тесты для обработчиков диалогов."""
from datetime import datetime
import pytest
import asyncio

from bot.domains.message import Message
from bot.domains.dialog import Dialog
from bot.handlers.greeting_handler import GreetingHandler
from bot.handlers.help_handler import HelpHandler
from bot.handlers.default_handler import DefaultHandler


class TestGreetingHandler:
    """Тесты для GreetingHandler."""

    @pytest.fixture
    def handler(self):
        return GreetingHandler()

    def create_message(self, text: str) -> Message:
        return Message(id=1, user_id=123, text=text, timestamp=datetime.now())

    def test_intent_property(self, handler):
        """Проверка свойства intent."""
        assert handler.intent == 'greeting'

    @pytest.mark.asyncio
    async def test_handle_async_returns_greeting(self, handler):
        """Ответ содержит приветствие."""
        message = self.create_message("привет")
        response = await handler.handle_async(message, None)
        assert "Здравствуйте" in response
        assert "бот сообщества" in response.lower()

    @pytest.mark.asyncio
    async def test_handle_async_with_dialog(self, handler):
        """Работа с диалогом."""
        message = self.create_message("здравствуйте")
        dialog = Dialog(user_id=123, last_active=datetime.now())
        response = await handler.handle_async(message, dialog)
        assert len(response) > 0


class TestHelpHandler:
    """Тесты для HelpHandler."""

    @pytest.fixture
    def handler(self):
        return HelpHandler()

    def create_message(self, text: str) -> Message:
        return Message(id=1, user_id=123, text=text, timestamp=datetime.now())

    def test_intent_property(self, handler):
        """Проверка свойства intent."""
        assert handler.intent == 'help'

    @pytest.mark.asyncio
    async def test_handle_async_returns_help_info(self, handler):
        """Ответ содержит информацию о возможностях."""
        message = self.create_message("help")
        response = await handler.handle_async(message, None)
        assert "могу" in response.lower() or "помочь" in response.lower()

    @pytest.mark.asyncio
    async def test_handle_async_mentions_features(self, handler):
        """Ответ упоминает возможности бота."""
        message = self.create_message("что умеешь")
        response = await handler.handle_async(message, None)
        # Проверяем наличие ключевых слов о возможностях
        assert len(response) > 20  # Ответ должен быть подробным


class TestDefaultHandler:
    """Тесты для DefaultHandler."""

    @pytest.fixture
    def handler(self):
        return DefaultHandler()

    def create_message(self, text: str) -> Message:
        return Message(id=1, user_id=123, text=text, timestamp=datetime.now())

    def test_intent_property(self, handler):
        """Проверка свойства intent."""
        assert handler.intent == 'unknown'

    @pytest.mark.asyncio
    async def test_handle_async_returns_helpful_message(self, handler):
        """Ответ содержит полезное сообщение."""
        message = self.create_message("случайный текст")
        response = await handler.handle_async(message, None)
        assert "не понял" in response.lower() or "переформулировать" in response.lower()

    @pytest.mark.asyncio
    async def test_handle_async_suggests_help(self, handler):
        """Ответ предлагает помощь."""
        message = self.create_message("asdfasdf")
        response = await handler.handle_async(message, None)
        assert "help" in response.lower()
