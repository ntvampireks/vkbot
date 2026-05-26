from bot.domains.message import Message
from bot.domains.dialog import Dialog
from bot.handlers.base_handler import BaseHandler


class HelpHandler(BaseHandler):
    @property
    def intent(self) -> str:
        return 'help'

    def handle(self, message: Message, dialog: Dialog | None) -> str:
        return '''Я могу:
- Отвечать на вопросы о сообществе
- Помогать с информацией о мероприятиях
- Принимать обращения

Напишите ваш вопрос или используйте /help для этой справки.'''
