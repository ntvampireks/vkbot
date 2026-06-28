import re

from pydantic import BaseModel, Field
from bot.domains.message import Message
from bot.utils.app_logger import get_logger

logger = get_logger(__name__)


class MessageText(BaseModel):
    """Валидированный текст сообщения."""
    text: str = Field(..., min_length=1, description='Текст сообщения')


class IntentClassifier:
    """Классификатор намерений сообщений по ключевым словам."""

    def __init__(self):
        """Инициализирует классификатор с предопределёнными интентами."""
        self.intents = {
            'greeting': ['привет', 'здравствуйте', 'доброго времени', 'здравствуй', 'hello', 'hi'],
            'help': ['помощь', 'help', 'что умеешь', 'подскажи', 'помогите'],
        }

    def _get_text(self, message: Message) -> str:
        """Получает и валидирует текст сообщения.

        Args:
            message: Сообщение от пользователя

        Returns:
            Нормализованный текст сообщения (пустая строка если текст отсутствует)
        """
        if message.text is None:
            return ''
        # Нормализация: преобразование в строку, удаление лишних пробелов
        text = str(message.text).strip()
        # Валидация через pydantic
        try:
            validated = MessageText(text=text)
            return validated.text
        except Exception as e:
            logger.debug(f'Failed to validate message text: {e}')
            return ''

    def classify(self, message: Message) -> str:
        """Классифицирует сообщение по намерению.

        Args:
            message: Сообщение от пользователя

        Returns:
            Строка с названием intent ('greeting', 'help' или 'unknown')
        """
        text = self._get_text(message).lower()

        for intent, keywords in self.intents.items():
            for keyword in keywords:
                if keyword in text:
                    logger.debug(f'Определён intent: {intent}')
                    return intent

        return 'unknown'
