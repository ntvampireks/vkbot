from bot.domains.message import Message
from bot.domains.dialog import Dialog
from bot.handlers.base_handler import BaseHandler
from pydantic import BaseModel, Field


class ResponseText(BaseModel):
    """Валидированный ответ бота."""
    reply: str = Field(..., description='Текст ответа')


class GreetingHandler(BaseHandler):
    """Обработчик приветствий."""

    @property
    def intent(self) -> str:
        return 'greeting'

    @property
    def intent_prompt(self) -> str:
        return """Роль: Ты ехидный император драконов Иллюзорис, настоящий трикстер по характеру,
        владеющий магией электричества, master of realm в ролевой игре, в мире фэнтэзи.
        Задача: максимально едко и ехидно ответить на приветствие игрока.
        Ограничения: Тебе не известны человеческие предметы, химические реакции, технологии. 
        Примеры:
        Игрок: Привет!
        Ты: Я надеюсь у тебя что-то важное, раз ты осмелился призвать меня. Если же нет, тогда мы сыграем в игру «Догони меня разряд»
        
        Верни ТОЛЬКО JSON объект c одним полем reply типа str
        """

    def handle(self, message: Message, dialog: Dialog | None) -> str:
        if self._llm_client is None:
            return 'Здравствуйте! Я бот сообщества VK. Чем могу помочь?'

        user_text = message.text.replace('@бот', '') or ''
        messages = [
            {'role': 'system', 'content': self.intent_prompt},
            {'role': 'user', 'content': f'Игрок: {user_text}'}
        ]

        result = self._llm_client.generate_text(messages, temperature=0.8, response_format=ResponseText)
        return result
