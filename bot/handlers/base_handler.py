from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

from bot.domains.message import Message
from bot.domains.dialog import Dialog

if TYPE_CHECKING:
    from bot.core.openai_client import OpenAIClient


class BaseHandler(ABC):
    """Базовый класс для обработчиков диалогов.

    Все обработчики должны наследоваться от этого класса и реализовывать:
    - intent: уникальный идентификатор типа диалога
    - intent_prompt: промпт для обработки с помощью llm
    - handle: логика обработки сообщения
    """

    def __init__(self, llm_client: Optional['OpenAIClient'] = None):
        """Инициализирует обработчик.

        Args:
            llm_client: Клиент LLM для генерации ответов (опционально)
        """
        self._llm_client = llm_client

    @property
    @abstractmethod
    def intent(self) -> str:
        """Уникальный идентификатор типа диалога (например, 'greeting', 'help')."""
        pass

    @property
    @abstractmethod
    def intent_prompt(self) -> str:
        """Описание интента для классификатора LLM.

        Возвращает текст описания что делает этот обработчик и когда применяется.
        """
        pass

    @abstractmethod
    def handle(self, message: Message, dialog: Dialog | None) -> str:
        """Обработать сообщение и вернуть ответ.

        Args:
            message: входящее сообщение
            dialog: текущий диалог (может быть None для новых диалогов)

        Returns:
            Текст ответа для пользователя
        """
        pass
