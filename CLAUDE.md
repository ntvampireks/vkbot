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
from bot.utils.metrics import MetricsCollector
from bot.core.vk_client import VKClient
from bot.core.event_handler import EventHandler
from bot.services.rate_limiter import RateLimiter
from bot.utils.per_user_limiter import PerUserRateLimiter
from bot.services.dialog_service import DialogService
from bot.services.message_service import MessageService
from bot.core.openai_client import OpenAIClient
from bot.services.intent_classifier import IntentClassifier
from bot.orchestration.router import create_router
from bot.orchestration.message_processor import MessageProcessor
import logging

# 1. Создаём базовые компоненты
settings = Settings()
logger = logging.getLogger('bot')
metrics = MetricsCollector()

# 2. Инициализируем клиенты и сервисы
vk_client = VKClient(settings, logger)
rate_limiter = RateLimiter()
per_user_limiter = PerUserRateLimiter()
dialog_service = DialogService(settings, logger)
message_service = MessageService(vk_client, rate_limiter, settings, logger)

# 3. Инициализация LLM клиента и классификатора
llm_client = OpenAIClient(
    base_url=settings.llm_base_url,
    api_key=settings.llm_api_key,
    model=settings.llm_model_name,
    timeout=settings.llm_timeout
)
router = create_router(llm_client=llm_client)
classifier = IntentClassifier(router=router, llm_client=llm_client)

# 4. Создаём processor
processor = MessageProcessor(
    dialog_service=dialog_service,
    message_service=message_service,
    router=router,
    classifier=classifier,
    metrics=metrics,
    settings=settings,
    logger=logger
)

# 5. Запускаем бота
vk_client.run_forever(processor.process)
```

#### Зависимости по компонентам

| Компонент | Зависимости | Зачем |
|-----------|-------------|-------|
| `VKClient` | `Settings`, `Logger` | Конфигурация токена, логирование |
| `EventHandler` | `MessageDeduplicator`, `PerUserRateLimiter`, `on_message` callback | Дедупликация, лимиты, колбэк |
| `DialogService` | `Settings`, `Logger` | Конфигурация кэша, логирование |
| `MessageService` | `VKClient`, `RateLimiter`, `Settings`, `Logger` | Отправка через VK, rate limiting |
| `MessageProcessor` | `DialogService`, `MessageService`, `Router`, `Metrics`, `Settings`, `Logger` | Оркестрация всего потока |
| `IntentClassifier` | — | Не имеет зависимостей (stateless) |

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

## Поведенческие руководства (из AGENTS.md)

Руководства по поведению для снижения распространённых ошибок LLM при написании кода.

**Компромисс:** Эти руководства склоняются к осторожности, а не к скорости. Для тривиальных задач используйте суждение.

### 1. Думайте перед кодированием

**Не предполагайте. Не скрывайте путаницу. Выявляйте компромиссы.**

Перед реализацией:
- Явно сформулируйте свои предположения. Если не уверены — спросите.
- Если существует несколько интерпретаций — представьте их, не выбирайте молча.
- Если существует более простой подход — скажите об этом. Возразите, когда это оправдано.
- Если что-то непонятно — остановитесь. Назовите, что именно непонятно. Спросите.

### 2. Простота прежде всего

**Минимальный код, решающий проблему. Ничего спекулятивного.**

- Никаких функций beyond того, что было запрошено.
- Никаких абстракций для однократного использования кода.
- Никакой «гибкости» или «настраиваемости», которая не была запрошена.
- Никакой обработки ошибок для невозможных сценариев.
- Если вы пишете 200 строк, а могло быть 50 — переписывайте.

Спросите себя: «Сказал бы старший инженер, что это излишне усложнено?» Если да — упрощайте.

### 3. Хирургические изменения

**Касайтесь только того, что необходимо. Чистите только свой собственный беспорядок.**

При редактировании существующего кода:
- Не «улучшайте» соседний код, комментарии или форматирование.
- Не рефакторьте вещи, которые не сломаны.
- Соответствуйте существующему стилю, даже если вы сделали бы это иначе.
- Если вы заметили несоответствующий мёртвый код — упомяните его, не удаляйте.

Когда ваши изменения создают «сирот»:
- Удаляйте импорты/переменные/функции, которые ВЫ сделали неиспользуемыми.
- Не удаляйте существующий мёртвый код, если не просили.

Тест: Каждая изменённая строка должна напрямую восходить к запросу пользователя.

### 4. Исполнение, ориентированное на цель

**Определяйте критерии успеха. Циклируйте до проверки.**

Преобразуйте задачи в проверяемые цели:
- «Добавить валидацию» → «Написать тесты для невалидных входов, затем заставить их пройти»
- «Исправить баг» → «Написать тест, воспроизводящий его, затем заставить его пройти»
- «Рефакторить X» → «Убедиться, что тесты проходят до и после»

Для многошаговых задач сформулируйте краткий план:
```
1. [Шаг] → проверить: [контроль]
2. [Шаг] → проверить: [контроль]
3. [Шаг] → проверить: [контроль]
```

Сильные критерии успеха позволяют вам циклировать независимо. Слабые критерии («сделать работающим») требуют постоянной обратной связи.

---

**Эти руководства работают, если:** меньше ненужных изменений в диффах, меньше переписываний из-за излишнего усложнения, и уточняющие вопросы приходят до реализации, а не после ошибок.

**ВСЕГДА ВЕДИ ДИАЛОГ НА РУССКОМ**
