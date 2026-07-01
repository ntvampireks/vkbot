"""IntentClassifier с LLM-классификацией и Pydantic валидацией."""

from typing import Any, Literal

from pydantic import BaseModel, Field, create_model
from bot.domains.message import Message
from bot.utils.app_logger import get_logger
from bot.core.openai_client import OpenAIClient

logger = get_logger(__name__)


class MessageText(BaseModel):
    """Валидированный текст сообщения."""

    text: str = Field(..., min_length=1, description='Текст сообщения')


class IntentClassifier:
    """Классификатор намерений через OpenAI-совместимый LLM с schema-guided reasoning."""

    def __init__(self, router: dict[str, Any], llm_client: OpenAIClient):
        """Инициализирует классификатор.

        Args:
            router: Роутер с зарегистрированными обработчиками
            llm_client: Клиент LLM для классификации
        """
        self._router = router
        self._client = llm_client
        self._intent_result_model = self._create_intent_model()

    def _create_intent_model(self) -> type[BaseModel]:
        """Создаёт динамическую Pydantic модель с Literal из router интентов."""
        intents = list(self._router.keys())
        IntentResult = create_model(
            'IntentResult',
            intent=(Literal[tuple(intents)], ...),
            __doc__='Результат классификации намерения с валидацией против доступных интентов'
        )
        return IntentResult

    def _get_text(self, message: Message) -> str:
        """Получает и валидирует текст сообщения."""
        if message.text is None:
            return ''
        text = str(message.text).strip()
        try:
            validated = MessageText(text=text)
            return validated.text
        except Exception as e:
            logger.debug(f'Failed to validate message text: {e}')
            return ''

    def _get_intents(self) -> list[str]:
        """Получает список интентов из router."""
        return list(self._router.keys())

    def _build_prompt(self, available_intents: list[str], user_text: str) -> list[dict[str, str]]:
        """Формирует промпт для LLM с JSON mode инструкцией."""
        # Формируем список обработчиков с описанием
        handlers_info = []
        for intent in available_intents:
            handler = self._router.get(intent)
            if handler and hasattr(handler, 'intent_description'):
                handlers_info.append(f"- {intent}: {handler.intent_description}")
            else:
                handlers_info.append(f"- {intent}")

        intents_list = '\n'.join(handlers_info)

        system_prompt = f'''Ты классификатор намерений. Определи какой обработчик должен обработать сообщение.

Доступные обработчики:
{intents_list}

Верни ТОЛЬКО JSON объект с полем "intent".'''

        user_prompt = f'Сообщение: "{user_text}"'

        return [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt}
        ]

    async def classify_async(self, message: Message) -> str:
        """Классифицирует сообщение через LLM с JSON mode валидацией (асинхронно).

        Args:
            message: Сообщение от пользователя

        Returns:
            Строка с названием intent
        """
        text = self._get_text(message)

        if not text:
            logger.debug('Пустое сообщение, возвращаю unknown')
            return 'unknown'

        intents = self._get_intents()
        logger.debug(f'Доступные интенты: {intents}')

        try:
            messages = self._build_prompt(intents, text)
            result = await self._client.classify_intent_async(messages, response_format=self._intent_result_model)
            logger.debug(f'Определён intent: {result.intent}')
            return result.intent
        except Exception as e:
            logger.error(f'Ошибка классификации LLM: {e}')
            return 'unknown'
