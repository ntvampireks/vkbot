"""Тесты для RollDiceHandler — обычный бросок игрового кубика."""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from bot.domains.message import Message
from bot.handlers.roll_dice_handler import RollDiceHandler


def make_message(text: str) -> Message:
    return Message(id=1, user_id=123, text=text, timestamp=datetime.now())


def llm_returning(die: int, narration: str = 'Император усмехается.') -> Mock:
    """Мок LLM: разбор кубика через classify_intent_async, текст через generate_text_async."""
    client = Mock()
    client.classify_intent_async = AsyncMock(return_value=SimpleNamespace(die=die))
    client.generate_text_async = AsyncMock(return_value=narration)
    return client


class TestRollDiceIntent:
    def test_intent_property(self):
        assert RollDiceHandler().intent == 'roll_dice'

    def test_intent_description_distinguishes_from_throw_dice(self):
        """Описание должно разделять «просто бросить кубик» и проверку успеха (throw_dice)."""
        desc = RollDiceHandler().intent_description.lower()
        assert 'куби' in desc
        assert 'throw_dice' in desc


class TestRollWithLlm:
    @pytest.mark.asyncio
    async def test_parsed_die_drives_the_roll(self):
        """Разобранный LLM кубик задаёт верхнюю грань реального броска."""
        handler = RollDiceHandler(llm_client=llm_returning(die=20))
        with patch('random.randint', return_value=14) as roll:
            result = await handler.handle_async(make_message('кинь двадцатигранник'), None)
        roll.assert_called_once_with(1, 20)
        assert 'D20' in result
        assert '14' in result

    @pytest.mark.asyncio
    async def test_narration_appended_after_roll(self):
        """Художественный текст идёт строкой после результата броска."""
        handler = RollDiceHandler(llm_client=llm_returning(die=6, narration='Жалкий бросок, дитя.'))
        with patch('random.randint', return_value=4):
            result = await handler.handle_async(make_message('бросок кубика D6'), None)
        assert 'D6 → 4' in result
        assert 'Жалкий бросок, дитя.' in result


class TestFallbackWithoutLlm:
    """Без LLM кубик достаётся из текста регуляркой."""

    @pytest.mark.asyncio
    async def test_detects_die_from_text(self):
        handler = RollDiceHandler()
        with patch('random.randint', return_value=7) as roll:
            result = await handler.handle_async(make_message('@Бот, бросок кубика D20'), None)
        roll.assert_called_once_with(1, 20)
        assert 'D20 → 7' in result

    @pytest.mark.asyncio
    async def test_defaults_to_d6_when_die_unrecognized(self):
        handler = RollDiceHandler()
        with patch('random.randint', return_value=2) as roll:
            result = await handler.handle_async(make_message('ну кинь кубик'), None)
        roll.assert_called_once_with(1, 6)
        assert 'D6 → 2' in result
