import vk_api
from vk_api.longpoll import VkLongPoll
from vk_api.exceptions import AccessDenied, AuthError, ApiError
from typing import Callable, NoReturn
import secrets
import time
import logging
import requests
import traceback
from bot.config import Settings


# Константы VK API
MAX_PEER_ID = 2**31 - 1  # Максимальное значение signed 32-bit int
MESSAGE_TRUNCATE_SUFFIX = '...'  # Суффикс при обрезке сообщения


class TimeoutSession(requests.Session):
    """Сессия requests с таймаутом по умолчанию.

    vk_api вызывает self.http.post(url, values) без timeout, поэтому запрос
    с зависшим соединением висел бы вечно. VkApi принимает готовую сессию,
    так что таймаут задаётся здесь и действует на все вызовы API.
    """

    def __init__(self, default_timeout: float):
        """Инициализирует сессию.

        Args:
            default_timeout: Таймаут запроса в секундах
        """
        super().__init__()
        self.default_timeout = default_timeout

    def request(self, method, url, **kwargs) -> requests.Response:
        """Выполняет запрос, подставляя default_timeout если он не задан явно."""
        kwargs.setdefault('timeout', self.default_timeout)
        return super().request(method, url, **kwargs)


class VKClient:
    """Клиент VK API с LongPoll поддержкой.

    Предоставляет интерфейс для отправки сообщений и получения событий
    через VK LongPoll API. Включает экспоненциальный backoff при ошибках.
    """

    def __init__(self, settings: Settings, logger: logging.Logger | None = None):
        """Инициализирует VK клиент.

        Args:
            settings: Конфигурация с токеном и ID сообщества
            logger: Логгер (опционально)
        """
        self._settings = settings
        self._logger = logger or logging.getLogger(__name__)
        self.vk_session = vk_api.VkApi(
            token=self._settings.vk_group_token,
            session=TimeoutSession(self._settings.message_api_timeout)
        )
        self.vk = self.vk_session.get_api()
        self.longpoll = VkLongPoll(self.vk_session)
        self._running = False

        # Проверка валидности токена
        try:
            self.vk.groups.getMembers(group_id=self._settings.vk_group_id_int, count=1)
            self._logger.info('VK API токен успешно валидирован')
        except AuthError as e:
            self._handle_auth_error('токена', e)
        except Exception as e:
            self._logger.warning(f'Не удалось валидировать токен: {e}')

    def _handle_auth_error(self, context: str, error: AuthError) -> NoReturn:
        """Обработка ошибки аутентификации VK API."""
        self._logger.critical(f'Ошибка аутентификации {context}: {error}')
        raise

    def _parse_event(self, event) -> dict:
        """Распарсить VK событие в структуру сообщения.

        Ключом диалога (поле user_id) выступает peer_id: VK отдаёт его в MESSAGE_NEW
        всегда, а автора в беседе — только через extra_values['from']. Автор уходит
        в author_id и для ключа диалога не используется, иначе одна беседа давала бы
        то ключ автора, то ключ беседы.
        """
        peer_id = getattr(event, "peer_id", 0)
        author_id = getattr(event, "user_id", 0)
        return {
            "message_id": getattr(event, "message_id", 0),
            "user_id": peer_id,
            "author_id": author_id if isinstance(author_id, int) and author_id > 0 else None,
            "text": getattr(event, "message", getattr(event, "text", "")),
            "timestamp": getattr(event, "timestamp", 0),
            "peer_id": peer_id,
            "attachments": getattr(event, "attachments", []),
            "type": event.type if hasattr(event, "type") else event.get("type"),
            "out": 1 if getattr(event, "from_me", False) else 0
        }

    def _calculate_backoff_delay(self, attempt: int, base_delay: int = 1, max_delay: int = 60) -> float:
        """Вычислить задержку перед повторным подключением (экспоненциальный backoff)."""
        delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
        self._logger.info(f'Повторная попытка подключения через {delay:.1f}с (попытка {attempt})')
        return delay

    def _sleep_interruptible(self, delay: float) -> bool:
        """Sleep с возможностью прерывания."""
        slept = 0.0
        while slept < delay and self._running:
            time.sleep(0.5)
            slept += 0.5
        return self._running

    def send_message(
        self,
        peer_id: int,
        text: str,
        reply_to: int | None = None,
        random_id: int | None = None
    ) -> None:
        """Отправляет сообщение через VK API.

        Таймаут запроса задаётся сессией (TimeoutSession из settings),
        а не этим вызовом: сессия общая с потоком LongPoll.

        Args:
            peer_id: ID получателя (должен быть положительным int)
            text: Текст сообщения
            reply_to: ID сообщения для ответа (опционально)
            random_id: Ключ идемпотентности VK. При повторных попытках передают
                один и тот же, чтобы VK отбросил дубль; None — сгенерировать новый

        Raises:
            ValueError: Если peer_id невалиден
            AuthError: Если ошибка аутентификации
            ApiError: Если ошибка VK API
            ConnectionError: Если сетевая ошибка
        """
        if not isinstance(peer_id, int):
            self._logger.error(f'Невалидный peer_id: ожидался int, получен {type(peer_id).__name__}')
            raise ValueError(f'peer_id должен быть int, получен {type(peer_id).__name__}')
        if peer_id <= 0:
            self._logger.error(f'peer_id должен быть положительным: {peer_id}')
            raise ValueError(f'peer_id должен быть положительным, получен {peer_id}')
        if peer_id > MAX_PEER_ID:
            self._logger.error(f'peer_id превышает максимальное значение: {peer_id}')
            raise ValueError(f'peer_id превышает максимальное значение ({MAX_PEER_ID})')

        if len(text) > self._settings.max_message_length:
            text = text[:self._settings.max_message_length - len(MESSAGE_TRUNCATE_SUFFIX)] + MESSAGE_TRUNCATE_SUFFIX
        try:
            params = {
                'peer_id': peer_id,
                'message': text,
                'random_id': random_id if random_id is not None else secrets.randbelow(2**31),
            }
            if reply_to is not None:
                params['reply_to'] = reply_to

            self.vk.messages.send(**params)

            self._logger.info(f'Сообщение отправлено в peer_id={peer_id}, reply_to={reply_to}')
        except AuthError as e:
            self._handle_auth_error('при отправке', e)
        except requests.exceptions.Timeout as e:
            self._logger.warning(f'Timeout при отправке сообщения: {e}')
            raise
        except requests.exceptions.ConnectionError as e:
            self._logger.warning(f'Сетевая ошибка при отправке: {e}')
            raise
        except ApiError as e:
            self._logger.error(f'Ошибка VK API при отправке: {e}')
            raise
        except AccessDenied as e:
            self._logger.error(f'Доступ запрещён: {e}')
            raise
        except Exception as e:
            self._logger.error(f'Ошибка отправки сообщения: {e}')
            raise

    def run_forever(self, on_message: Callable[[dict], None]) -> None:
        """Запускает LongPoll с экспоненциальным backoff при ошибках."""
        self._running = True
        max_reconnect_delay = 60
        base_delay = 1
        reconnect_attempts = 0

        while self._running:
            try:
                for event in self.longpoll.check():
                    if not self._running:
                        return
                    message_struct = self._parse_event(event)
                    try:
                        on_message(message_struct)
                    except Exception as e:
                        self._logger.error(f'Ошибка в обработчике сообщений:\n{traceback.format_exc()}')

                reconnect_attempts = 0

            except AuthError as e:
                self._running = False
                self._handle_auth_error('VK', e)
            except ApiError as e:
                self._logger.error(f'Ошибка VK API: {e}')
                reconnect_attempts += 1
                delay = self._calculate_backoff_delay(reconnect_attempts, base_delay, max_reconnect_delay)
                if self._sleep_interruptible(delay):
                    continue
            except Exception as e:
                self._logger.error(f'Ошибка LongPoll: {e}')
                reconnect_attempts += 1
                delay = self._calculate_backoff_delay(reconnect_attempts, base_delay, max_reconnect_delay)
                if self._sleep_interruptible(delay):
                    continue

    def stop(self):
        """Останавливает LongPoll."""
        self._logger.info('Остановка VK клиента...')
        self._running = False
        # Прерываем текущий HTTP-запрос longpoll
        if self.longpoll:
            self.longpoll.update_longpoll_server(update_ts=False)