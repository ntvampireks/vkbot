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

    vk_group_token: str = Field(..., description='Токен VK сообщества')
    vk_group_id: str = Field(..., description='ID VK сообщества')
    vk_bot_name: str = Field(..., description='Имя бота для упоминаний')

    bot_host: str = Field('localhost', description='Хост для запуска')
    bot_port: int = Field(8000, ge=1, le=65535, description='Порт для запуска')
    dialog_timeout_hours: int = Field(24, ge=1, le=720, description='Таймаут диалога в часах')
    max_history_messages: int = Field(10, ge=1, le=100, description='Максимум сообщений в истории')

    # Настройки MessageDeduplicator
    dedup_max_size: int = Field(1000, ge=1, le=10000, description='Максимальный размер кэша дедупликации')
    dedup_ttl_seconds: int = Field(300, ge=1, le=3600, description='TTL для записей в кэше дедупликации')

    # Путь к каталогу логов
    log_dir: str = Field('logs', description='Путь к каталогу для логов')

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
