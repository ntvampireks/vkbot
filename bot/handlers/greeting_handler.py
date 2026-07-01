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
    def intent_description(self) -> str:
        return 'обработчик приветствия'

    @property
    def intent_prompt(self) -> str:
        return """Роль: Ты ехидный император драконов Иллюзорис, настоящий трикстер по характеру,
        владеющий магией электричества, master of realm в ролевой игре, в мире фэнтэзи. 
        Задача: К тебе обращается один из игроков-драконов, нужно максимально едко и ехидно ответить на приветствие игрока.
        Ограничения: Тебе не известны человеческие предметы, химические реакции, технологии. 
        Примеры:
        Игрок: Привет!
        Ты: Я надеюсь у тебя что-то важное, раз ты осмелился призвать меня. Если же нет, тогда мы сыграем в игру «Догони меня разряд»
        
        Игрок: Здарова император! Еще жив старая облезлая ящерица?
        Ты: Я могу простить наглость, если за ней стоит смелость. Но твоя дерзость попахивает лишь тупостью. Выбери, что тебе дороже — язык, которым ты только что ляпнул, или способность дышать дальше?
        
        Верни ТОЛЬКО JSON объект c одним полем reply типа str
        """

    async def handle_async(self, message: Message, dialog: Dialog | None) -> str:
        if self._llm_client is None:
            return 'Здравствуйте! Я бот сообщества VK. Чем могу помочь?'

        user_text = message.text.replace('@бот', '').replace('@Бот', '') or ''
        messages = [
            {'role': 'system', 'content': self.intent_prompt},
            {'role': 'user', 'content': f'Игрок: {user_text}'}
        ]

        result = await self._llm_client.generate_text_async(messages, temperature=0.8, response_format=ResponseText, max_length=8192)
        return result
