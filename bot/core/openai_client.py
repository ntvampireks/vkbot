"""OpenAI-совместимый клиент для LLM-классификации."""

import time
from typing import Type, Optional

from openai import AsyncOpenAI, OpenAI
from pydantic import BaseModel

from bot.utils.app_logger import get_logger

logger = get_logger(__name__)


class OpenAIClient:
    """Клиент для OpenAI-совместимых API с поддержкой structured outputs."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float = 0.0,
        timeout: float = 30.0
    ):
        """Инициализирует клиент.

        Args:
            base_url: URL API (например, 'http://192.168.1.100:8000/v1')
            api_key: API ключ (может быть пустым для локальных сервисов)
            model: Имя модели (например, 'qwen')
            temperature: Температура генерации (0.0 — детерминировано, по умолчанию 0)
            timeout: Таймаут запросов в секундах (по умолчанию 30)
        """
        self._model = model
        self._default_temperature = temperature
        self._client = OpenAI(
            base_url=base_url,
            api_key=api_key if api_key else 'empty',
            timeout=timeout
        )
        self._async_client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key if api_key else 'empty',
            timeout=timeout
        )

    def classify_intent(
        self,
        messages: list[dict[str, str]],
        response_format: Type[BaseModel]
    ) -> BaseModel:
        """Вызывает LLM с structured outputs и валидацией ответа (синхронно).

        Args:
            messages: Список сообщений в формате {'role': ..., 'content': ...}
            response_format: Pydantic модель для валидации ответа

        Returns:
            Валидированный Pydantic объект
        """
        logger.debug(f'LLM вызов (sync): model={self._model}, format={response_format.__name__}')

        start_time = time.time()
        response = self._client.chat.completions.parse(
            model=self._model,
            messages=messages,
            temperature=self._default_temperature,
            response_format=response_format
        )
        elapsed = time.time() - start_time

        content = response.choices[0].message.content.strip()
        logger.debug(f'LLM ответ: {content}')
        logger.info(f'LLM классификация заняла: {elapsed:.3f}s')

        return response_format.model_validate_json(content)

    async def classify_intent_async(
        self,
        messages: list[dict[str, str]],
        response_format: Type[BaseModel]
    ) -> BaseModel:
        """Вызывает LLM с structured outputs и валидацией ответа (асинхронно).

        Args:
            messages: Список сообщений в формате {'role': ..., 'content': ...}
            response_format: Pydantic модель для валидации ответа

        Returns:
            Валидированный Pydantic объект
        """
        logger.debug(f'LLM вызов (async): model={self._model}, format={response_format.__name__}')

        start_time = time.time()
        response = await self._async_client.chat.completions.parse(
            model=self._model,
            messages=messages,
            temperature=self._default_temperature,
            response_format=response_format
        )
        elapsed = time.time() - start_time

        content = response.choices[0].message.content.strip()
        logger.debug(f'LLM ответ: {content}')
        logger.info(f'LLM классификация заняла: {elapsed:.3f}s')

        return response_format.model_validate_json(content)

    def generate_text(
        self,
        messages: list[dict[str, str]],
        temperature: Optional[float] = None,
        response_format: Optional[Type[BaseModel]] = None
    ) -> str:
        """Генерирует текстовый ответ от LLM (синхронно).

        Args:
            messages: Список сообщений в формате {'role': ..., 'content': ...}
            temperature: Температура генерации (использует дефолтную если не указана)
            response_format: Pydantic модель для валидации ответа

        Returns:
            Текст ответа из валидированного объекта
        """
        temp = temperature if temperature is not None else self._default_temperature
        logger.debug(f'LLM генерация (sync): model={self._model}, temperature={temp}')

        start_time = time.time()
        response = self._client.chat.completions.parse(
            model=self._model,
            messages=messages,
            temperature=temp,
            response_format=response_format
        )
        elapsed = time.time() - start_time

        content = response.choices[0].message.content.strip()
        logger.debug(f'LLM ответ: {content}')
        logger.info(f'LLM генерация заняла: {elapsed:.3f}s')

        if response_format:
            parsed = response_format.model_validate_json(content)
            return parsed.reply
        return content

    async def generate_text_async(
        self,
        messages: list[dict[str, str]],
        temperature: Optional[float] = None,
        response_format: Optional[Type[BaseModel]] = None,
        max_length = 32768,
    ) -> str:
        """Генерирует текстовый ответ от LLM (асинхронно).

        Args:
            messages: Список сообщений в формате {'role': ..., 'content': ...}
            temperature: Температура генерации (использует дефолтную если не указана)
            response_format: Pydantic модель для валидации ответа
            max_length: максимальное количество токенов в ответе
        Returns:
            Текст ответа из валидированного объекта
        """
        temp = temperature if temperature is not None else self._default_temperature
        logger.debug(f'LLM генерация (async): model={self._model}, temperature={temp}')

        start_time = time.time()
        response = await self._async_client.chat.completions.parse(
            model=self._model,
            messages=messages,
            temperature=temp,
            response_format=response_format,
            reasoning_effort=None,
            max_tokens=max_length,

        )
        elapsed = time.time() - start_time

        content = response.choices[0].message.content.strip()
        logger.debug(f'LLM ответ: {content}')
        logger.info(f'LLM генерация заняла: {elapsed:.3f}s')

        if response_format:
            parsed = response_format.model_validate_json(content)
            return parsed.reply
        return content
