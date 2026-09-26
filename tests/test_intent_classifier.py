"""Тесты для IntentClassifier."""
from datetime import datetime
from unittest.mock import Mock, AsyncMock
import pytest

from bot.services.intent_classifier import IntentClassifier
from bot.domains.message import Message
from bot.utils.message_validator import has_mention


@pytest.fixture
def mock_llm_client():
    """Mock для LLM клиента."""
    mock = Mock()
    mock.classify_intent_async = AsyncMock()
    return mock


@pytest.fixture
def router():
    """Фикстура router с интентами."""
    return {
        'greeting': Mock(),
        'help': Mock(),
        'unknown': Mock()
    }


@pytest.fixture
def classifier(router, mock_llm_client):
    """Фикстура классификатора."""
    return IntentClassifier(router=router, llm_client=mock_llm_client)


class TestIntentClassifier:
    """Тесты для классификации намерений."""

    def create_message(self, text: str, user_id: int = 123) -> Message:
        """Хелпер для создания сообщения."""
        return Message(
            id=1,
            user_id=user_id,
            text=text,
            timestamp=datetime.now()
        )

    # --- Тесты для classify_async() ---

    @pytest.mark.asyncio
    async def test_classify_greeting_ru(self, classifier, mock_llm_client):
        """Русские приветствия."""
        mock_llm_client.classify_intent_async.return_value = Mock(intent='greeting')
        message = self.create_message("привет!")
        result = await classifier.classify_async(message)
        assert result == 'greeting'

    @pytest.mark.asyncio
    async def test_classify_greeting_formal(self, classifier, mock_llm_client):
        """Формальное приветствие."""
        mock_llm_client.classify_intent_async.return_value = Mock(intent='greeting')
        message = self.create_message("здравствуйте")
        result = await classifier.classify_async(message)
        assert result == 'greeting'

    @pytest.mark.asyncio
    async def test_classify_greeting_dobrogo_vremeni(self, classifier, mock_llm_client):
        """Приветствие с добрым временем."""
        mock_llm_client.classify_intent_async.return_value = Mock(intent='greeting')
        message = self.create_message("доброго времени суток")
        result = await classifier.classify_async(message)
        assert result == 'greeting'

    @pytest.mark.asyncio
    async def test_classify_greeting_english(self, classifier, mock_llm_client):
        """Английские приветствия."""
        mock_llm_client.classify_intent_async.return_value = Mock(intent='greeting')
        message = self.create_message("hello")
        result = await classifier.classify_async(message)
        assert result == 'greeting'

    @pytest.mark.asyncio
    async def test_classify_help(self, classifier, mock_llm_client):
        """Запрос помощи."""
        mock_llm_client.classify_intent_async.return_value = Mock(intent='help')
        message = self.create_message("help")
        result = await classifier.classify_async(message)
        assert result == 'help'

    @pytest.mark.asyncio
    async def test_classify_help_russian(self, classifier, mock_llm_client):
        """Запрос помощи на русском."""
        mock_llm_client.classify_intent_async.return_value = Mock(intent='help')
        message = self.create_message("помощь")
        result = await classifier.classify_async(message)
        assert result == 'help'

    @pytest.mark.asyncio
    async def test_classify_unknown(self, classifier, mock_llm_client):
        """Неизвестный intent."""
        mock_llm_client.classify_intent_async.return_value = Mock(intent='unknown')
        message = self.create_message("случайный текст который не подходит")
        result = await classifier.classify_async(message)
        assert result == 'unknown'

    @pytest.mark.asyncio
    async def test_classify_empty_text(self, classifier):
        """Пустой текст."""
        message = self.create_message("")
        result = await classifier.classify_async(message)
        assert result == 'unknown'

    @pytest.mark.asyncio
    async def test_classify_case_insensitive(self, classifier, mock_llm_client):
        """Регистронезависимость."""
        mock_llm_client.classify_intent_async.return_value = Mock(intent='greeting')
        message = self.create_message("ПРИВЕТ")
        result = await classifier.classify_async(message)
        assert result == 'greeting'

    @pytest.mark.asyncio
    async def test_classify_with_extra_spaces(self, classifier, mock_llm_client):
        """Дополнительные пробелы."""
        mock_llm_client.classify_intent_async.return_value = Mock(intent='greeting')
        message = self.create_message("  привет  ")
        result = await classifier.classify_async(message)
        assert result == 'greeting'

    @pytest.mark.asyncio
    async def test_classify_llm_error_returns_unknown(self, classifier, mock_llm_client):
        """При ошибке LLM возвращается unknown."""
        mock_llm_client.classify_intent_async.side_effect = Exception("LLM error")
        message = self.create_message("привет")
        result = await classifier.classify_async(message)
        assert result == 'unknown'

    def test_intent_model_created_from_router(self, router, mock_llm_client):
        """Pydantic модель создаётся из ключей router."""
        classifier = IntentClassifier(router=router, llm_client=mock_llm_client)
        assert classifier._intent_result_model is not None
        # Проверяем что модель имеет поле intent
        fields = classifier._intent_result_model.model_fields
        assert 'intent' in fields

    # --- Тесты для has_mention() ---

    @staticmethod
    def mention_settings(bot_name: str = 'vkbot', group_id: str = '123456') -> Mock:
        """Конфигурация с заданным именем и ID сообщества."""
        settings = Mock()
        settings.vk_bot_name = bot_name
        settings.vk_group_id = group_id
        return settings

    def test_has_mention_simple(self):
        """Простое упоминание @имя."""
        message = self.create_message("@vkbot привет")
        assert has_mention(message, self.mention_settings()) is True

    def test_has_mention_with_id(self):
        """Упоминание с ID @имя(123456)."""
        message = self.create_message("@vkbot(123456) привет")
        assert has_mention(message, self.mention_settings()) is True

    def test_has_mention_case_insensitive(self):
        """Регистронезависимость упоминания."""
        message = self.create_message("@VKBOT привет")
        assert has_mention(message, self.mention_settings()) is True

    def test_has_mention_not_mentioned(self):
        """Без упоминания."""
        message = self.create_message("привет всем")
        assert has_mention(message, self.mention_settings()) is False

    def test_has_mention_with_numbers_in_name(self):
        """Упоминание с цифрами в имени бота."""
        message = self.create_message("@vkbot123 привет")
        assert has_mention(message, self.mention_settings(bot_name='vkbot123')) is True

    def test_has_mention_other_bot_name(self):
        """Упоминание с другим именем — не про нас."""
        message = self.create_message("@bot привет")
        assert has_mention(message, self.mention_settings()) is False
