from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


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

    # Настройки валидации сообщений
    max_message_length: int = Field(10000, ge=1, le=40960, description='Максимальная длина сообщения в символах')
    enable_prompt_injection_protection: bool = Field(True, description='Включить защиту от prompt injection атак')

    @property
    def vk_group_id_int(self) -> int:
        """Групповой ID как integer."""
        return int(self.vk_group_id)


# Глобальный экземпляр настроек
_settings: Settings | None = None


def get_settings() -> Settings:
    """Получить экземпляр настроек (создаётся при первом вызове)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
