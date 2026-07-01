"""Тесты для router.py."""
import pytest
from bot.orchestration.router import create_router
from bot.domains.message import Message


class TestCreateRouterIntegration:
    """Интеграционные тесты для create_router."""

    def test_router_returns_dict(self):
        """Тестирует что create_router возвращает dict."""
        router = create_router()
        assert isinstance(router, dict)

    def test_router_always_has_unknown_handler(self):
        """Тестирует что router всегда содержит unknown handler."""
        router = create_router()
        assert 'unknown' in router

    @pytest.mark.asyncio
    async def test_router_unknown_handler_can_handle_messages(self):
        """Тестирует что unknown handler может обрабатывать сообщения."""
        router = create_router()
        unknown_handler = router['unknown']

        # Создаём тестовое сообщение
        message = Message(
            text='тестовое сообщение',
            user_id=123,
            peer_id=456,
            id=789,
            timestamp=1234567890,
            attachments=[],
            out=0
        )

        # Проверяем что обработчик может обработать сообщение
        response = await unknown_handler.handle_async(message, None)
        assert isinstance(response, str)
        assert len(response) > 0

    @pytest.mark.asyncio
    async def test_router_unknown_handler_response_content(self):
        """Тестирует содержимое ответа от unknown handler."""
        router = create_router()
        unknown_handler = router['unknown']

        message = Message(
            text='любой вопрос',
            user_id=123,
            peer_id=456,
            id=789,
            timestamp=1234567890,
            attachments=[],
            out=0
        )

        response = await unknown_handler.handle_async(message, None)

        # Проверяем что ответ содержит подсказку
        assert 'хоть' in response.lower() or 'help' in response.lower() or 'переформулировать' in response.lower()

    def test_router_handlers_have_valid_intent_property(self):
        """Тестирует что все обработчики имеют валидное свойство intent."""
        router = create_router()

        for intent, handler in router.items():
            assert hasattr(handler, 'intent')
            assert handler.intent == intent
            assert isinstance(intent, str)
            assert len(intent) > 0

    def test_router_handlers_have_handle_async_method(self):
        """Тестирует что все обработчики имеют метод handle_async."""
        router = create_router()

        for intent, handler in router.items():
            assert hasattr(handler, 'handle_async')
            assert callable(handler.handle_async)

    @pytest.mark.asyncio
    async def test_router_greeting_handler_exists_if_registered(self):
        """Тестирует что если есть greeting handler, он работает корректно."""
        router = create_router()

        # Если greeting handler зарегистрирован (есть файлы handlers)
        if 'greeting' in router:
            handler = router['greeting']
            message = Message(
                text='привет',
                user_id=123,
                peer_id=456,
                id=789,
                timestamp=1234567890,
                attachments=[],
                out=0
            )
            response = await handler.handle_async(message, None)
            assert isinstance(response, str)

    @pytest.mark.asyncio
    async def test_router_help_handler_exists_if_registered(self):
        """Тестирует что если есть help handler, он работает корректно."""
        router = create_router()

        # Если help handler зарегистрирован (есть файлы handlers)
        if 'help' in router:
            handler = router['help']
            message = Message(
                text='помощь',
                user_id=123,
                peer_id=456,
                id=789,
                timestamp=1234567890,
                attachments=[],
                out=0
            )
            response = await handler.handle_async(message, None)
            assert isinstance(response, str)

    def test_router_handler_intent_matches_key(self):
        """Тестирует что intent обработчика совпадает с ключом в router."""
        router = create_router()

        for key, handler in router.items():
            assert handler.intent == key, f"Handler intent '{handler.intent}' не совпадает с ключом '{key}'"

    def test_router_allows_retrieving_handler_by_intent(self):
        """Тестирует что обработчики можно получить по intent."""
        router = create_router()

        # Проверяем что все ключи можно использовать для получения обработчиков
        for intent in router.keys():
            handler = router[intent]
            assert handler is not None
            assert handler.intent == intent