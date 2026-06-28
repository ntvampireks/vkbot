import re
from typing import Pattern
from bot.utils.app_logger import get_logger
from bot.config import Settings
from bot.domains.message import Message

logger = get_logger(__name__)


# Паттерны для обнаружения prompt injection атак
PROMPT_INJECTION_PATTERNS = [
    # Попытки переопределения инструкций (английский)
    r'\b(ignore\s+previous\s+instructions|forget\s+everything|reset\s+context)\b',
    r'\b(system\s+override|developer\s+mode|debug\s+mode)\b',
    r'\b(you\s+are\s+now|act\s+as\s+if\s+you\s+were)\b',

    # Попытки переопределения инструкций (русский)
    r'\b(забудь\s+все|забудь\s+всё|забудь\s+инструкцию|забудь\s+прошлую|сбрось\s+контекст)\b',
    r'\b(режим\s+разработчика|режим\s+отладки|включи\s+дебаг)\b',
    r'\b(ты\s+теперь|теперь\s+ты|действуй\s+как)\b',

    # Попытки раскрытия промпта (английский)
    r'\b(what\s+is\s+your\s+instruction|show\s+your\s+prompt|reveal\s+your\s+system)\b',
    r'\b(dump\s+(the\s+)?database|extract\s+(all\s+)?(the\s+)?passwords?|get\s+(the\s+)?api\s+key)\b',

    # Попытки раскрытия промпта (русский)
    r'\b(покажи\s+свою\s+инструкцию|покажи\s+инструкцию|какие\s+у\s+тебя\s+правила|какие\s+у\s+тебя\s+настройки)\b',
    r'\b(выведи\s+базу|получи\s+пароли|находи\s+пароли|найди\s+ключи)\b',

    # Многократные повторы для обхода фильтров
    r'(ignore\s+){3,}',
    r'(forget\s+){3,}',
    r'(забудь\s+){3,}',

    # Специальные символы для инъекции
    r'(<\|end\|>|<\|start\|>|</?system>|</?user>)',
]

# Компилируем паттерны для производительности
_INJECTION_PATTERN: Pattern | None = None


def _get_injection_pattern() -> Pattern:
    """Ленивая компиляция паттернов."""
    global _INJECTION_PATTERN
    if _INJECTION_PATTERN is None:
        combined = '|'.join(PROMPT_INJECTION_PATTERNS)
        _INJECTION_PATTERN = re.compile(combined, re.IGNORECASE)
    return _INJECTION_PATTERN


def is_prompt_injection(text: str) -> bool:
    """Проверяет текст на признаки prompt injection атаки.

    Args:
        text: Текст сообщения для проверки

    Returns:
        True если обнаружена попытка инъекции
    """
    pattern = _get_injection_pattern()
    return bool(pattern.search(text))


def sanitize_text(text: str, settings: Settings) -> str:
    """Очищает и валидирует текст сообщения.

    Args:
        text: Исходный текст
        settings: Экземпляр Settings (обязательный)

    Returns:
        Очищенный текст

    Raises:
        ValueError: Если текст превышает лимит или содержит опасный контент
    """
    max_length = settings.max_message_length

    if not text:
        return ''

    # Проверка длины
    if len(text) > max_length:
        logger.warning(f'Сообщение превышает максимальную длину: {len(text)} > {max_length}')
        raise ValueError(f'Слишком длинное сообщение: максимум {max_length} символов')

    # Проверка на prompt injection
    if settings.enable_prompt_injection_protection and is_prompt_injection(text):
        logger.warning(f'Обнаружена попытка prompt injection: {text[:100]}')
        raise ValueError('Недопустимое содержимое сообщения')

    # Удаление нулевых символов и других управляющих
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)

    # Нормализация Unicode (удаление invisible characters)
    text = re.sub(r'[​‌‍﻿]', '', text)

    return text.strip()


def validate_message(text: str, settings: Settings) -> tuple[bool, str]:
    """Проверяет сообщение на валидность.

    Args:
        text: Текст сообщения
        settings: Экземпляр Settings (обязательный)

    Returns:
        Кортеж (is_valid, error_message)
    """
    max_length = settings.max_message_length

    if not text or not text.strip():
        return False, 'Пустое сообщение'

    if len(text) > max_length:
        return False, f'Превышен лимит длины: {len(text)} > {max_length}'

    if settings.enable_prompt_injection_protection and is_prompt_injection(text):
        return False, 'Обнаружено недопустимое содержимое'

    return True, ''


def has_mention(message: Message, bot_name: str | None = None) -> bool:
    """Проверка, упомянут ли бот в сообщении.

    Args:
        message: Сообщение от пользователя
        bot_name: Имя бота для поиска упоминания

    Returns:
        True если бот упомянут в формате @имя или @имя(123456)
    """
    if not bot_name:
        return False

    text = message.text or ''
    if not text.strip():
        return False

    bot_name_lower = bot_name.lower()
    # Ищем упоминание в формате @имя или @имя(123456), игнорируя регистр
    pattern = rf'@{re.escape(bot_name_lower)}(\d+)?'
    return bool(re.search(pattern, text, re.IGNORECASE))
