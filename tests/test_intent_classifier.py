"""Тесты для IntentClassifier."""
from datetime import datetime
import pytest

from bot.services.intent_classifier import IntentClassifier
from bot.domains.message import Message


class TestIntentClassifier:
    """Тесты для классификации намерений."""

    @pytest.fixture
    def classifier(self):
        return IntentClassifier()

    def create_message(self, text: str, user_id: int = 123) -> Message:
        """Хелпер для создания сообщения."""
        return Message(
            id=1,
            user_id=user_id,
            text=text,
            timestamp=datetime.now()
        )

    # --- Тесты для classify() ---

    def test_classify_greeting_ru(self, classifier):
        """Русские приветствия."""
        message = self.create_message("привет!")
        assert classifier.classify(message) == 'greeting'

    def test_classify_greeting_formal(self, classifier):
        """Формальное приветствие."""
        message = self.create_message("здравствуйте")
        assert classifier.classify(message) == 'greeting'

    def test_classify_greeting_dobrogo_vremeni(self, classifier):
        """Приветствие с добрым временем."""
        message = self.create_message("доброго времени суток")
        assert classifier.classify(message) == 'greeting'

    def test_classify_greeting_english(self, classifier):
        """Английские приветствия."""
        message = self.create_message("hello")
        assert classifier.classify(message) == 'greeting'

    def test_classify_help(self, classifier):
        """Запрос помощи."""
        message = self.create_message("help")
        assert classifier.classify(message) == 'help'

    def test_classify_help_russian(self, classifier):
        """Запрос помощи на русском."""
        message = self.create_message("помощь")
        assert classifier.classify(message) == 'help'

    def test_classify_unknown(self, classifier):
        """Неизвестный intent."""
        message = self.create_message("случайный текст который не подходит")
        assert classifier.classify(message) == 'unknown'

    def test_classify_empty_text(self, classifier):
        """Пустой текст."""
        message = self.create_message("")
        assert classifier.classify(message) == 'unknown'

    def test_classify_case_insensitive(self, classifier):
        """Регистронезависимость."""
        message = self.create_message("ПРИВЕТ")
        assert classifier.classify(message) == 'greeting'

    def test_classify_with_extra_spaces(self, classifier):
        """Дополнительные пробелы."""
        message = self.create_message("  привет  ")
        assert classifier.classify(message) == 'greeting'

    # --- Тесты для has_mention() ---

    def test_has_mention_simple(self, classifier):
        """Простое упоминание @имя."""
        message = self.create_message("@vkbot привет")
        assert classifier.has_mention(message, "vkbot") is True

    def test_has_mention_with_id(self, classifier):
        """Упоминание с ID @имя(123456)."""
        message = self.create_message("@vkbot(123456) привет")
        assert classifier.has_mention(message, "vkbot") is True

    def test_has_mention_case_insensitive(self, classifier):
        """Регистронезависимость упоминания."""
        message = self.create_message("@VKBOT привет")
        assert classifier.has_mention(message, "vkbot") is True

    def test_has_mention_not_mentioned(self, classifier):
        """Без упоминания."""
        message = self.create_message("привет всем")
        assert classifier.has_mention(message, "vkbot") is False

    def test_has_mention_with_numbers_in_name(self, classifier):
        """Упоминание с цифрами в имени бота."""
        message = self.create_message("@vkbot123 привет")
        # Текущий regex не требует границы слова, поэтому совпадает
        assert classifier.has_mention(message, "vkbot") is True

    def test_has_mention_no_bot_name(self, classifier):
        """Пустое имя бота."""
        message = self.create_message("@bot привет")
        assert classifier.has_mention(message, None) is False
