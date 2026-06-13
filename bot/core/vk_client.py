import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from typing import Callable
import random
import time
from bot.config import get_settings
from bot.utils.logger import setup_logger

settings = get_settings()

logger = setup_logger(__name__)


class VKClient:
    def __init__(self):
        self.vk_session = vk_api.VkApi(
            token=settings.vk_group_token
        )
        self.vk = self.vk_session.get_api()
        self.longpoll = VkLongPoll(self.vk_session)
        self._running = False

    def send_message(self, peer_id: int, text: str, reply_to: int | None = None):
        if len(text) > 4096:
            text = text[:4093] + '...'
        try:
            params = {
                'peer_id': peer_id,
                'message': text,
                'random_id': random.randint(0, 2**31 - 1),
            }
            if reply_to is not None:
                params['reply_to'] = reply_to

            self.vk.messages.send(**params)

            logger.info(f'Сообщение отправлено в peer_id={peer_id}, reply_to={reply_to}')
        except Exception as e:
            logger.error(f'Ошибка отправки сообщения: {e}')
            raise

    def run_forever(self, on_message: Callable):
        """Запускает LongPoll с экспоненциальным backoff при ошибках."""
        self._running = True
        max_reconnect_delay = 60  # Максимальная задержка 60 секунд
        base_delay = 1  # Базовая задержка 1 секунда
        reconnect_attempts = 0

        while self._running:
            try:
                for event in self.longpoll.check():
                    event_type = event.type if hasattr(event, 'type') else event.get("type")

                    if event_type == VkEventType.MESSAGE_NEW:
                        message_id = getattr(event, "message_id", -100)
                        user_id = getattr(event, "user_id", -100)
                        text = getattr(event, "text", "")
                        timestamp = getattr(event, "timestamp", 0)
                        peer_id = getattr(event, "peer_id", -100)
                        attachments = getattr(event, "attachments", [])
                        out = getattr(event, "out", 0)

                        message_struct = {
                            "message_id": message_id,
                            "user_id": user_id,
                            "text": text,
                            "timestamp": timestamp,
                            "peer_id": peer_id,
                            "attachments": attachments,
                            "type": event_type,
                            "out": out
                        }
                        on_message(message_struct)

                # Успешная проверка — сбрасываем счетчик попыток
                reconnect_attempts = 0

            except Exception as e:
                logger.error(f'Ошибка LongPoll: {e}')

                # Экспоненциальный backoff
                reconnect_attempts += 1
                delay = min(base_delay * (2 ** (reconnect_attempts - 1)), max_reconnect_delay)
                logger.info(f'Повторная попытка подключения через {delay:.1f}с (попытка {reconnect_attempts})')
                time.sleep(delay)

    def stop(self):
        """Останавливает LongPoll."""
        logger.info('Остановка VK клиента...')
        self._running = False
