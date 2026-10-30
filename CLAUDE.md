# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VK Bot — диалоговый бот для сообщества VK, использующий LongPoll API для получения сообщений в реальном времени.

## Commands

**Запуск бота:**
```bash
python -m bot.main
```

**Тестирование:**
```bash
python -m pytest tests/
```

**Установка зависимостей:**
```bash
pip install -r requirements.txt
```

## Архитектура

```
┌─────────────────────────────────────────────────────────────────────┐
│                        VK LongPoll API                              │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    EventHandler.handle_event()                      │
│  • Фильтрация типа события (MESSAGE_NEW)                            │
│  • Фильтрация сообщений от бота                                     │
│  • MessageDeduplicator (проверка дубликатов)                        │
│  • PerUserRateLimiter (ограничение частоты)                         │
│  • Валидация и санитизация текста                                   │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   on_message() callback (main.py)                   │
│  • Проверка упоминания бота (@имя)                                  │
│  • Проверка вложений (отклонение с ответом)                         │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   MessageProcessor.process()                        │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ _prepare_dialog_context()                                   │   │
│  │   → DialogService.get_dialog() → SQLite                     │   │
│  └─────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ _handle_message()                                           │   │
│  │   → IntentClassifier.classify() → Router.get(intent)       │   │
│  │   → Handler.handle(message, dialog)                         │   │
│  └─────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ _send_response()                                            │   │
│  │   → MessageService.send() → MessageQueue                    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ _finalize_message()                                         │   │
│  │   → DialogService.add_message() → SQLite                    │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    MessageSender (фоновый поток)                    │
│  • Получение из MessageQueue                                        │
│  • RateLimiter (глобальный ~3 msg/sec)                              │
│  • Экспоненциальный backoff при ошибках                             │
│  → VKClient.send_message() → VK API                                 │
└─────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
                      ┌──────────────┐
                      │   SQLite DB  │
                      │  dialogs +   │
                      │  messages    │
                      └──────────────┘
```

### Ключевые компоненты

| Компонент | Путь | Описание |
|-----------|------|----------|
| VKClient | `bot/core/vk_client.py` | Клиент VK API с LongPoll, отправляет сообщения |
| EventHandler | `bot/core/event_handler.py` | Обработка событий VK, дедупликация, per-user rate limiting |
| MessageDeduplicator | `bot/utils/deduplication.py` | Предотвращение обработки дубликатов сообщений |
| PerUserRateLimiter | `bot/utils/per_user_limiter.py` | Ограничение частоты запросов по пользователю |
| DialogService | `bot/services/dialog_service.py` | Управление контекстом диалогов, SQLite хранение |
| IntentClassifier | `bot/services/intent_classifier.py` | LLM-классификация намерений с schema-guided валидацией |
| MessageService | `bot/services/message_service.py` | Координация отправки сообщений |
| MessageQueue | `bot/services/message_queue.py` | Очередь сообщений для асинхронной отправки |
| MessageSender | `bot/services/message_sender.py` | Фоновая отправка с ретраями |
| MetricsCollector | `bot/utils/metrics.py` | Сбор метрик (Prometheus формат) |
| Health API | `bot/api.py` | Endpoints /health, /ready, /metrics |
| Handlers | `bot/handlers/` | Обработчики для разных типов диалогов |

### Система обработки сообщений

1. **VKClient.run_forever()** — слушает LongPoll API
2. **EventHandler.handle_event()** — преобразует VK события в Message объекты:
   - Фильтрация по типу события (только MESSAGE_NEW)
   - Фильтрация сообщений от бота
   - Проверка дубликатов (MessageDeduplicator)
   - Проверка per-user лимитов (PerUserRateLimiter)
   - Валидация и санитизация текста
3. **on_message() callback** — проверка упоминания бота и вложений
4. **MessageProcessor.process()** — оркестрация обработки:
   - `_prepare_dialog_context()` — получение/создание диалога через DialogService
   - `_handle_message()` — классификация через IntentClassifier, роутинг, вызов Handler
   - `_send_response()` — отправка через MessageService → MessageQueue
   - `_finalize_message()` — сохранение истории через DialogService
5. **MessageSender** — фоновый поток отправки с ретраями и rate limiting
6. **MetricsCollector** — сбор метрик на ключевых этапах

### Добавление нового обработчика

1. Создайте файл `bot/handlers/<name>_handler.py`:

```python
from bot.domains.message import Message
from bot.domains.dialog import Dialog
from bot.handlers.base_handler import BaseHandler


class <Name>Handler(BaseHandler):
    @property
    def intent(self) -> str:
        return '<name>'

    async def handle_async(self, message: Message, dialog: Dialog | None) -> str:
        return 'Ответ обработчика'

    # Опционально: описание для LLM-классификатора
    intent_description = 'Описание обработчика'
```

2. Система автоматически зарегистрирует его через `create_router()` в [bot/main.py](bot/main.py)

### База данных

SQLite в `storage/dialogs.db`:

- **dialogs** — активные сессии (user_id, last_active, state, context)
- **messages** — история (user_id, role, text, timestamp)

Модуль: [storage/db.py](storage/db.py)

### Dependency Injection (DI)

Проект использует паттерн Dependency Injection для управления зависимостями. Все зависимости передаются явно через конструкторы компонентов.

#### Полная схема инициализации (из [bot/main.py](bot/main.py))

```python
from bot.config import Settings
from bot.core.vk_client import VKClient
from bot.core.event_handler import EventHandler
from bot.services.rate_limiter import RateLimiter
from bot.services.dialog_service import DialogService
from bot.services.message_service import MessageService
from bot.core.openai_client import OpenAIClient
from bot.services.intent_classifier import IntentClassifier
from bot.orchestration import create_router
from bot.orchestration.message_processor import MessageProcessor
from bot.lifecycle import register_signal_handlers, start_health_server
from bot import api
from bot.utils.app_logger import get_logger
from bot.utils.metrics import get_metrics
from bot.utils.message_validator import has_mention, strip_mention
from storage.db import init_db
import asyncio
import threading

# 1. Конфигурация и логирование (до первых логов)
settings = Settings()
logger = get_logger('bot', settings)

# 2. БД, метрики и health-сервер
init_db()
metrics = get_metrics()
api.set_metrics(metrics)
start_health_server(settings)

# 3. Клиент VK, очередь и сервисы
vk_client = VKClient(settings, logger)
rate_limiter = RateLimiter()
message_service = MessageService(vk_client, rate_limiter, settings, logger)
message_service.start_processing()
register_signal_handlers(vk_client, message_service)
dialog_service = DialogService(settings, logger)

# 4. LLM-клиент, роутер и классификатор
llm_client = OpenAIClient(
    base_url=settings.llm_base_url,
    api_key=settings.llm_api_key,
    model=settings.llm_model_name,
    timeout=settings.llm_timeout
)
router = create_router(llm_client=llm_client)
classifier = IntentClassifier(router=router, llm_client=llm_client)

# 5. Оркестратор
processor = MessageProcessor(
    dialog_service=dialog_service,
    message_service=message_service,
    router=router,
    classifier=classifier,
    metrics=metrics,
    settings=settings,
    logger=logger
)

# 6. Отдельный event loop в daemon-потоке для асинхронной обработки
loop = asyncio.new_event_loop()
threading.Thread(target=loop.run_forever, daemon=True).start()

# 7. Колбэк on_message: проверка упоминания/вложений, запуск processor.process
def on_message(message):
    if not has_mention(message, settings):
        return
    message.text = strip_mention(message.text, settings)
    if message.attachments:
        message_service.send(message.peer_id or message.user_id,
            'Извините, я пока не умею обрабатывать вложения...', reply_to=message.id)
        return
    future = asyncio.run_coroutine_threadsafe(processor.process(message), loop)
    future.add_done_callback(_consume_future)  # _consume_future — локальный обработчик, см. main.py

# 8. Обработчик событий
bot_user_id = settings.vk_group_id_int
event_handler = EventHandler(on_message, bot_user_id=bot_user_id, settings=settings, logger=logger)
vk_client.run_forever(event_handler.handle_event)
```

#### Зависимости по компонентам

| Компонент | Зависимости | Зачем |
|-----------|-------------|-------|
| `VKClient` | `Settings`, `Logger` | Конфигурация токена, логирование |
| `EventHandler` | `MessageDeduplicator`, `PerUserRateLimiter`, `on_message` callback | Дедупликация, лимиты, колбэк |
| `DialogService` | `Settings`, `Logger` | Конфигурация кэша, логирование |
| `MessageService` | `VKClient`, `RateLimiter`, `Settings`, `Logger` | Отправка через VK, rate limiting |
| `MessageProcessor` | `DialogService`, `MessageService`, `Router`, `Metrics`, `Settings`, `Logger` | Оркестрация всего потока |
| `IntentClassifier` | `Router`, `OpenAIClient` | Классификация интентов через LLM |
| `OpenAIClient` | — | Клиент для OpenAI-совместимых API (синхронный/асинхронный) |
| `RateLimiter` | `Logger` | Глобальное ограничение частоты отправки |
| `MessageSender` | `VKClient`, `RateLimiter`, `MessageQueue`, `Settings`, `Logger` | Фоновая отправка с ретраями |

#### Преимущества DI в этом проекте

1. **Тестируемость** — легко подменять зависимости на моки:
```python
from unittest.mock import Mock

mock_logger = Mock()
mock_dialog_service = Mock()
mock_message_service = Mock()
mock_router = Mock()
mock_metrics = Mock()
mock_settings = Mock()

processor = MessageProcessor(
    dialog_service=mock_dialog_service,
    message_service=mock_message_service,
    router=mock_router,
    metrics=mock_metrics,
    settings=mock_settings,
    logger=mock_logger
)
```

2. **Явные зависимости** — все зависимости видны в сигнатуре конструктора

3. **Лёгкая замена реализаций** — можно заменить `SQLiteDialogService` на `PostgresDialogService` без изменения кода процессора

4. **Отсутствие скрытого состояния** — кроме логгера (который создаётся один раз), нет глобальных переменных

#### Паттерн создания компонентов

```python
# 1. Создайте новый компонент с явными зависимостями
class MyNewService:
    def __init__(self, dialog_service: DialogService, logger: Logger):
        self._dialog_service = dialog_service
        self._logger = logger

# 2. Инициализируйте в main() вместе с другими компонентами
my_new_service = MyNewService(dialog_service=dialog_service, logger=logger)

# 3. Передайте туда, где нужен
processor = MessageProcessor(..., custom_service=my_new_service)
```

## Тестирование

### Структура тестов

```
tests/
├── test_app_logger.py             # Тесты app_logger (3 теста)
├── test_config.py                 # Тесты Settings / SSRF / валидации (19 тестов)
├── test_db.py                     # Тесты storage.db CRUD (2 теста)
├── test_deduplicator.py           # Тесты MessageDeduplicator (8 тестов)
├── test_dialog.py                 # Тесты Dialog и Message доменов (21 тест)
├── test_dialog_service.py         # Тесты DialogService (4 теста)
├── test_event_handler.py          # Тесты EventHandler / фильтрации событий (5 тестов)
├── test_handlers.py               # Тесты обработчиков (9 тестов)
├── test_intent_classifier.py      # Тесты IntentClassifier (18 тестов)
├── test_lifecycle.py              # Тесты lifecycle/shutdown (4 теста)
├── test_message_processor.py      # Тесты MessageProcessor (3 теста)
├── test_message_queue.py          # Тесты MessageQueue (10 тестов)
├── test_message_sender.py         # Тесты MessageSender (12 тестов)
├── test_message_validator.py      # Тесты валидации / prompt injection (69 тестов)
├── test_metrics.py                # Тесты MetricsCollector (3 теста)
├── test_per_user_limiter.py       # Тесты PerUserRateLimiter (15 тестов)
├── test_rate_limiter.py           # Тесты RateLimiter (5 тестов)
├── test_roll_dice_handler.py      # Тесты roll dice handler (6 тестов)
├── test_router.py                 # Тесты router (10 тестов)
└── test_vk_client.py              # Тесты VKClient (8 тестов)
```

### Покрытие тестами

| Модуль | Статус | Примечание |
|--------|--------|------------|
| `MessageDeduplicator` | ✅ | 8 тестов |
| `PerUserRateLimiter` | ✅ | 15 тестов, включая потокобезопасность |
| `RateLimiter` | ✅ | 5 тестов |
| `Dialog` | ✅ | 21 тест, включая concurrent access |
| `Message` | ✅ | Тесты в `test_dialog.py` |
| `MessageQueue` | ✅ | 10 тестов |
| `MessageSender` | ✅ | 12 тестов |
| `message_validator` | ✅ | 69 тестов, включая prompt injection |
| `IntentClassifier` | ✅ | 18 тестов с моками LLM |
| `Handlers` | ✅ | 9 тестов |
| `router` | ✅ | 10 тестов |
| `VKClient` | ✅ | 8 тестов |
| `EventHandler` | ✅ | 5 тестов |
| `MessageProcessor` | ✅ | 3 теста |
| `DialogService` | ✅ | 4 теста (моки БД) |
| `storage.db` | ✅ | 2 теста CRUD |
| `config` | ✅ | 19 тестов (SSRF/валидация) |
| `app_logger` | ✅ | 3 теста |
| `metrics` | ✅ | 3 теста |
| `lifecycle` | ✅ | 4 теста |
| `roll_dice_handler` | ✅ | 6 тестов (включая fallback без LLM) |
| `OpenAIClient` | ❌ | Нет dedicated-тестов (LLM мокается в `test_intent_classifier`) |

### Рекомендации по тестированию

1. **Критические приоритеты** — добавить тесты для:
   - `test_vk_client.py` — VK API клиент с моками
   - `test_event_handler.py` — фильтрация событий
   - `test_message_processor.py` — интеграционные тесты полного потока
   - `tests/test_db.py` — тесты SQLite с временной БД

2. **Интеграционные тесты** — тестировать взаимодействие компонентов:
   - Полный поток от получения сообщения до отправки ответа
   - Взаимодействие с реальной БД

3. **Edge cases** — покрыть тестами:
   - Экстремально длинные сообщения
   - Unicode символы и emoji
   - Параллельные запросы от одного пользователя
   - Ошибки VK API и БД

## Безопасность

### Реализованные защиты

| Защита | Файл | Описание |
|--------|------|----------|
| SSRF защита | [bot/config.py](bot/config.py) | Блокировка доступа к internal networks (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, localhost). Пропускается при `LLM_ALLOW_PRIVATE=true` (легитимный LLM во внутренней сети) |
| Prompt injection | [bot/utils/message_validator.py](bot/utils/message_validator.py) | Паттерны для обнаружения атак на английском и русском |
| Rate limiting | [bot/services/rate_limiter.py](bot/services/rate_limiter.py) + [bot/utils/per_user_limiter.py](bot/utils/per_user_limiter.py) | Глобальный (~3 msg/sec) и per-user лимиты |
| Дедупликация | [bot/utils/deduplication.py](bot/utils/deduplication.py) | Предотвращение обработки дубликатов сообщений |
| Валидация ввода | [bot/utils/message_validator.py](bot/utils/message_validator.py) | Санитизация текста, проверка длины |

### Меры предосторожности

- **SSRF проверка** — перед отправкой запросов к внешним URL проверяется, что адрес не принадлежит внутренним сетям
- **Prompt injection detection** — регулярные выражения для обнаружения попыток переопределения инструкций
- **Input sanitization** — удаление управляющих символов и invisible characters

### Рекомендации

1. Health API endpoints (`/health`, `/ready`, `/metrics`) — защита сетевая: `BOT_HOST` по умолчанию `localhost` (bind только на loopback), аутентификация сознательно не реализована (accepted risk). При `BOT_HOST` вне loopback бот логирует warning; если понадобится внешний мониторинг — добавить `HEALTH_TOKEN` с проверкой заголовка
2. Не логировать полный текст при обнаружении атак — логировать только хэш или обрезанную версию
3. Использовать `secrets` вместо `random` для генерации `random_id`
4. Добавить CORS middleware для FastAPI

## Поводительность

### Ключевые метрики

| Метрика | Описание |
|---------|----------|
| `messages_received_total` | Всего получено сообщений |
| `messages_sent_total` | Всего отправлено сообщений |
| `message_errors_total` | Ошибки при обработке |
| `message_processing_seconds` | Время обработки сообщения |
| `response_send_seconds` | Время отправки ответа |
| `uptime_seconds` | Время работы бота |

### Доступные endpoints

| Endpoint | Описание |
|----------|----------|
| `/health` | Статус здоровья бота с метриками |
| `/ready` | Готовность к работе |
| `/metrics` | Метрики в формате Prometheus |

### Оптимизации

- **LRU-кэширование** — DialogService кэширует активные диалоги в памяти
- **Фоновая отправка** — MessageSender работает в отдельном потоке с экспоненциальным backoff
- **Асинхронная БД** — aiosqlite для неблокирующего доступа

### Известные bottlenecks

1. **SQLite** — нет пула соединений, каждое обращение создаёт новое соединение
2. **LLM классификация** — каждый запрос идёт к LLM (2-10 секунд), нет кэширования
3. **Блокирующий код** — `time.sleep()` в `VKClient._sleep_interruptible()` блокирует event loop

## Поведенческие руководства (из AGENTS.md)

Руководства по поведению (думать перед кодированием, простота, хирургические правки,
цель-ориентированное исполнение) размещены в [AGENTS.md](AGENTS.md) — единый источник
истины. Ниже они не дублируются.
