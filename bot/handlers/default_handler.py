from bot.domains.message import Message
from bot.domains.dialog import Dialog
from bot.handlers.base_handler import BaseHandler


class DefaultHandler(BaseHandler):
    @property
    def intent(self) -> str:
        return 'unknown'

    def handle(self, message: Message, dialog: Dialog | None) -> str:
        return 'Извините, я пока не понял ваш вопрос. Попробуйте переформулировать или напишите /help для списка возможностей.'
