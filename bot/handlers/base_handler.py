from abc import ABC, abstractmethod

from bot.domains.message import Message
from bot.domains.dialog import Dialog


class BaseHandler(ABC):
    @property
    @abstractmethod
    def intent(self) -> str:
        pass

    @abstractmethod
    def handle(self, message: Message, dialog: Dialog | None) -> str:
        pass
