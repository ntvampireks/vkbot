import re
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """Конфигурация бота."""

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore'
    )

    vk_group_token: str = Field(..., min_length=1, description='Токен VK сообщества')
    vk_group_id: str = Field(..., min_length=1, description='ID VK сообщества')
    vk_bot_name: str = Field(..., min_length=1, description='Имя бота для упоминаний')

    bot_host: str = Field('localhost', description='Хост для запуска')
    bot_port: int = Field(8000, ge=1, le=65535, description='Порт для запуска')
    dialog_timeout_hours: int = Field(24, ge=1, le=720, description='Таймаут диалога в часах')
    max_history_messages: int = Field(10, ge=1, le=100, description='Максимум сообщений в истории')

    # Настройки MessageDeduplicator
    dedup_max_size: int = Field(1000, ge=1, le=10000, description='Максимальный размер кэша дедупликации')
    dedup_ttl_seconds: int = Field(300, ge=1, le=3600, description='TTL для записей в кэше дедупликации')

    # Путь к каталогу логов
    log_dir: str = Field('logs', description='Путь к каталогу для логов')

    # Уровень логирования
    log_level: str = Field('DEBUG', description='Уровень логирования (DEBUG, INFO, WARNING, ERROR)')

    # Настройки отправки сообщений
    message_send_delay: float = Field(0.5, ge=0, description='Задержка перед отправкой сообщения в секундах')
    message_retry_delay: float = Field(1.0, ge=0, description='Задержка между попытками повторной отправки в секундах')
    message_api_timeout: int = Field(5, ge=1, le=60, description='Таймаут VK API запроса в секундах')

    # Настройки валидации сообщений
    max_message_length: int = Field(10000, ge=1, le=40960, description='Максимальная длина сообщения в символах')
    enable_prompt_injection_protection: bool = Field(True, description='Включить защиту от prompt injection атак')

    # Настройки per-user rate limiter
    per_user_max_requests: int = Field(10, ge=1, le=100, description='Максимум сообщений от пользователя за окно')
    per_user_window_seconds: int = Field(60, ge=1, le=3600, description='Размер окна для per-user лимита в секундах')

    # Настройки кэша диалогов
    max_dialogs_cache: int = Field(1000, ge=100, le=10000, description='Максимальный размер кэша диалогов')

    # Настройки очереди сообщений
    message_queue_maxsize: int = Field(1000, ge=100, le=10000, description='Максимальный размер очереди сообщений')

    # Настройки LLM для IntentClassifier
    llm_base_url: str = Field(..., min_length=1, description='URL OpenAI-совместимого API')
    llm_api_key: str = Field('', description='API ключ для LLM сервиса')
    llm_model_name: str = Field('qwen', description='Имя модели для классификации')
    llm_timeout: float = Field(30.0, ge=1.0, le=300.0, description='Таймаут LLM запросов в секундах')
    
    @field_validator('llm_base_url')
    @classmethod
    def validate_llm_url(cls, v: str) -> str:
        """Валидирует LLM URL.

        Проверяет:
        - URL начинается с http:// или https://
        - Не указывает на приватные/internal сети (защита от SSRF)
        """
        if not v:
            raise ValueError('LLM URL не может быть пустым')

        # Проверка scheme
        if not (v.startswith('http://') or v.startswith('https://')):
            raise ValueError('LLM URL должен начинаться с http:// или https://')

        # Проверка на доступ к внутренним сетям (SSRF защита)
        private_patterns = [
            r'^https?://10\.',                    # Private range 10.0.0.0/8
            r'^https?://172\.(1[6-9]|2[0-9]|3[0-1])\.',  # Private range 172.16.0.0/12
            r'^https?://127\.',                   # Loopback
            r'^https?://169\.254\.',              # Link-local (AWS metadata)
            r'^https?://localhost',               # Localhost
            r'^https?://0\.0\.0\.0',              # All interfaces
        ]

        for pattern in private_patterns:
            if re.match(pattern, v, re.IGNORECASE):
                raise ValueError('Доступ к внутренним сетям запрещён из соображений безопасности')

        return v

    @property
    def vk_group_id_int(self) -> int:
        """Групповой ID как integer."""
        return int(self.vk_group_id)


# Примечание: Settings создаётся в main.py и передаётся явно через Dependency Injection
