"""Обработчик обычного броска игрового кубика (D4…D100)."""

import random
import re
from typing import Literal

from pydantic import BaseModel, Field

from bot.domains.message import Message
from bot.domains.dialog import Dialog
from bot.handlers.base_handler import BaseHandler

# Разрешённые грани кубика и разбор обозначения (d20 / D20 / д20)
ALLOWED_DICE = (4, 6, 8, 10, 12, 16, 20, 30, 100)
_DIE_RE = re.compile(r'[dд]\s*(\d+)', re.IGNORECASE)


class RollRequest(BaseModel):
    """Разбор запроса игрока: какой кубик бросить."""

    die: Literal[4, 6, 8, 10, 12, 16, 20, 30, 100] = Field(
        6, description='Количество граней кубика'
    )


class RollReply(BaseModel):
    """Художественное описание результата броска."""

    reply: str = Field(..., description='Описание броска в образе Императора')


class RollDiceHandler(BaseHandler):
    """Бросок одного игрового кубика (d4…d100) по запросу в произвольной форме.

    LLM понимает запрос («двадцатигранник», «процентник», «кинь d100») и ведёт
    художественный текст, а само значение даёт random в Python — иначе «бросок»
    был бы выдумкой модели, а не случайностью.
    """

    _PARSE_PROMPT = (
        'Ты определяешь, какой игровой кубик бросает игрок (один кубик).\n'
        'Разрешены кубики: d4, d6, d8, d10, d12, d16, d20, d30, d100.\n'
        'die — число граней (одно из 4, 6, 8, 10, 12, 16, 20, 30, 100), по умолчанию 6.\n'
        'Распознавай «процентник»/«d%» как die 100 и русские названия '
        '(«двадцатигранник» → 20, «кубик» → 6).\n'
        'Верни ТОЛЬКО JSON с полем die.'
    )

    @property
    def intent(self) -> str:
        return 'roll_dice'

    @property
    def intent_description(self) -> str:
        return (
            'Простой бросок одного игрового кубика '
            '(d4/d6/d8/d10/d12/d16/d20/d30/d100) — когда игрок просит просто '
            'кинуть кубик и получить случайное число. НЕ использовать для проверки '
            'успешности действия персонажа — для этого есть throw_dice.'
        )

    @property
    def intent_prompt(self) -> str:
        return (
            'Ты ехидный император драконов Иллюзорис, трикстер, владеющий магией '
            'электричества, master of realm в мире фэнтези. Игрок-дракон бросил '
            'игровой кубик, число уже выпало — не меняй его и не додумывай. '
            'Опиши результат кратко и ехидно в своём образе. '
            'Верни ТОЛЬКО JSON объект с полем reply типа str.'
        )

    async def handle_async(self, message: Message, dialog: Dialog | None) -> str:
        """Бросает один кубик и возвращает результат, дополненный описанием LLM."""
        text = (message.text or '').strip() or 'бросок кубика'
        die = 6

        if self._llm_client is not None:
            req = await self._llm_client.classify_intent_async(
                [
                    {'role': 'system', 'content': self._PARSE_PROMPT},
                    {'role': 'user', 'content': text},
                ],
                response_format=RollRequest,
            )
            die = req.die
        else:
            die = self._die_from_text(text)

        value = random.randint(1, die)

        if self._llm_client is None:
            return f'🎲 D{die} → {value}'

        narration = await self._llm_client.generate_text_async(
            [
                {'role': 'system', 'content': self.intent_prompt},
                {'role': 'user', 'content': f'Игрок бросил D{die}: {value}. Опиши бросок.'},
            ],
            temperature=0.8,
            response_format=RollReply,
            max_length=8192,
        )
        return f'🎲 D{die} → {value}\r\n{narration}'

    @staticmethod
    def _die_from_text(text: str) -> int:
        """Достаёт грани кубика из текста (запасной путь без LLM)."""
        match = _DIE_RE.search(text)
        if match:
            die = int(match.group(1))
            if die in ALLOWED_DICE:
                return die
        return 6
