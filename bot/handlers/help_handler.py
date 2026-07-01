from bot.domains.message import Message
from bot.domains.dialog import Dialog
from bot.handlers.base_handler import BaseHandler


class HelpHandler(BaseHandler):
    """Обработчик запросов помощи."""

    @property
    def intent(self) -> str:
        return 'help'

    @property
    def intent_description(self) -> str:
        return 'обработчик команды помощи'

    @property
    def intent_prompt(self) -> str:
        return 'Обработка запросов помощи, справок и вопросов о возможностях'

    async def handle_async(self, message: Message, dialog: Dialog | None) -> str:
        return '''Я могу:
- Отвечать на вопросы о сообществе
- Помогать с информацией о мероприятиях
- Принимать обращения

Напишите ваш вопрос или используйте /help для этой справки.'''
