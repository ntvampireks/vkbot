"""Обработчик броска двух D100 кубиков."""

import random
from bot.domains.message import Message
from bot.domains.dialog import Dialog
from bot.handlers.base_handler import BaseHandler
from pydantic import BaseModel, Field


class DiceResult(BaseModel):
    """Валидированный ответ бота с броском кубиков."""

    reply: str = Field(..., description='Форматированный результат броска')


class ThrowDiceHandler(BaseHandler):
    """Обработчик броска двух D100 кубиков.

    Механика: Бросаются два кубика D100 (0-99).
    Если первый кубик больше второго — проверка пройдена.
    """

    @property
    def intent(self) -> str:
        return 'throw_dice'

    @property
    def intent_description(self) -> str:
        return 'Данный обработчик применяется для отбрасывания кубиков на поиск чего-либо в окружении и только в этом случае'

    @property
    def intent_prompt(self) -> str:
        return """Ты ехидный император драконов Иллюзорис, настоящий трикстер по характеру,
        владеющий магией электричества, master of realm в ролевой игре, в мире фэнтэзи. 
        Задача: Игрок-дракон обращается к тебе с вопросом на проверку действия поиска чего-либо в окружении.
        В зависимости от результатов ты должен ехидно прокомментировать результат проверки.

        Механика: Бросаются два кубика D100 (0-99). Если первый кубик больше второго — проверка пройдена.

        Верни ТОЛЬКО JSON объект с полем reply типа str"""

    async def handle_async(self, message: Message, dialog: Dialog | None) -> str:
        """Бросает два D100 кубика и возвращает результат.

        Args:
            message: Сообщение игрока
            dialog: Текущий диалог (не используется)

        Returns:
            Форматированный результат броска
        """
        # Генерируем два кубика D100 (0-99)
        dice1 = random.randint(0, 99)
        dice2 = random.randint(0, 99)
        success = dice1 > dice2

        # Формируем контекст для LLM
        status = "Успех" if success else "Провал"
        user_text = message.text.replace('@бот', '').strip() or 'бросок кубиков'

        messages = [
            {'role': 'system', 'content': self.intent_prompt},
            {'role': 'user', 'content': f'{user_text}: d1={dice1}, d2={dice2}, результат={status}'}
        ]

        if self._llm_client is None:
            return f'🎲 d1={dice1}, d2={dice2} — {status}'

        result = await self._llm_client.generate_text_async(
            messages,
            temperature=0.7,
            response_format=DiceResult,
            max_length=32768
        )
        return result
