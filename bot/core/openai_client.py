"""OpenAI-совместимый клиент для LLM-классификации."""

from typing import Type, Optional

from openai import OpenAI
from pydantic import BaseModel

from bot.utils.app_logger import get_logger

logger = get_logger(__name__)


class OpenAIClient:
    """Клиент для OpenAI-совместимых API с поддержкой structured outputs."""

    def __init__(self, base_url: str, api_key: str, model: str, temperature: float = 0.0):
        """Инициализирует клиент.

        Args:
            base_url: URL API (например, 'http://192.168.1.100:8000/v1')
            api_key: API ключ (может быть пустым для локальных сервисов)
            model: Имя модели (например, 'qwen')
            temperature: Температура генерации (0.0 — детерминировано, по умолчанию 0)
        """
        self._model = model
        self._default_temperature = temperature
        self._client = OpenAI(
            base_url=base_url,
            api_key=api_key if api_key else 'empty'
        )

    def classify_intent(
        self,
        messages: list[dict[str, str]],
        response_format: Type[BaseModel]
    ) -> BaseModel:
        """Вызывает LLM с structured outputs и валидацией ответа.

        Args:
            messages: Список сообщений в формате {'role': ..., 'content': ...}
            response_format: Pydantic модель для валидации ответа

        Returns:
            Валидированный Pydantic объект
        """
        logger.debug(f'LLM вызов: model={self._model}, format={response_format.__name__}')

        response = self._client.chat.completions.parse(
            model=self._model,
            messages=messages,
            temperature=self._default_temperature,
            response_format=response_format
        )

        content = response.choices[0].message.content.strip()
        logger.debug(f'LLM ответ: {content}')

        return response_format.model_validate_json(content)

    def generate_text(
        self,
        messages: list[dict[str, str]],
        temperature: Optional[float] = None,
        response_format: Optional[Type[BaseModel]] = None
    ) -> str:
        """Генерирует текстовый ответ от LLM.

        Args:
            messages: Список сообщений в формате {'role': ..., 'content': ...}
            temperature: Температура генерации (использует дефолтную если не указана)
            response_format: Pydantic модель для валидации ответа

        Returns:
            Текст ответа из валидированного объекта
        """
        temp = temperature if temperature is not None else self._default_temperature
        logger.debug(f'LLM генерация: model={self._model}, temperature={temp}')

        response = self._client.chat.completions.parse(
            model=self._model,
            messages=messages,
            temperature=temp,
            response_format=response_format
        )

        content = response.choices[0].message.content.strip()
        logger.debug(f'LLM ответ: {content}')

        if response_format:
            parsed = response_format.model_validate_json(content)
            return parsed.reply
        return content
