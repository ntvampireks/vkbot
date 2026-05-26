from bot.domains.message import Message
from bot.domains.dialog import Dialog
from bot.handlers.base_handler import BaseHandler


class GreetingHandler(BaseHandler):
    @property
    def intent(self) -> str:
        return 'greeting'

    def handle(self, message: Message, dialog: Dialog | None) -> str:
        return 'Здравствуйте! Я бот сообщества VK. Чем могу помочь?'
