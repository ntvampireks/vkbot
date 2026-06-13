from abc import ABC, abstractmethod

from bot.domains.message import Message
from bot.domains.dialog import Dialog


class BaseHandler(ABC):
    """Базовый класс для обработчиков диалогов.

    Все обработчики должны наследоваться от этого класса и реализовывать:
    - intent: уникальный идентификатор типа диалога
    - handle: логика обработки сообщения
    """

    @property
    @abstractmethod
    def intent(self) -> str:
        """Уникальный идентификатор типа диалога (например, 'greeting', 'help')."""
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
