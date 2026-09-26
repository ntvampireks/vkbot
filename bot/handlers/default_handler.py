from bot.domains.message import Message
from bot.domains.dialog import Dialog
from bot.handlers.base_handler import BaseHandler
from pydantic import BaseModel, Field

class ResponseText(BaseModel):
    """Валидированный ответ бота."""
    reply: str = Field(..., description='Текст ответа')

class DefaultHandler(BaseHandler):
    """Обработчик неизвестных запросов."""

    @property
    def intent(self) -> str:
        return 'unknown'

    @property
    def intent_description(self) -> str:
        return 'обработчик который используется в ситуации когда не получается определить намерение игрока'

    @property
    def intent_prompt(self) -> str:
        return """Роль: Ты ехидный император драконов Иллюзорис, настоящий трикстер по характеру,
                    владеющий магией электричества, master of realm в ролевой игре, в мире фэнтэзи. 
                    Задача: К тебе обращается один из игроков-драконов, c каким то бредовым вопросом. Твоя задача едко высмеять игрока сообразно контексту
                    Ограничения: Тебе не известны человеческие предметы, химические реакции, технологии. 
                    Верни ТОЛЬКО JSON объект c одним полем reply типа str
                    """

    async def handle_async(self, message: Message, dialog: Dialog | None) -> str:
        if self._llm_client is None:
            return 'Извините, я не понял ваш вопрос. Попробуйте переформулировать или обратитесь к help за помощью.'

        user_text = message.text.strip()
        messages = [
            {'role': 'system', 'content': self.intent_prompt},
            {'role': 'user', 'content': f'Игрок: {user_text}'}
        ]

        result = await self._llm_client.generate_text_async(messages, temperature=0.8, response_format=ResponseText, max_length=32768)
        return result
