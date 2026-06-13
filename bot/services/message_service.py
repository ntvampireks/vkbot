import time
from typing import Optional

from bot.core.vk_client import VKClient
from bot.domains.message import Message
from bot.utils.logger import setup_logger
from bot.services.rate_limiter import RateLimiter

logger = setup_logger(__name__)


class MessageService:
    def __init__(self, vk_client: VKClient, rate_limiter: RateLimiter | None = None, max_retries: int = 3):
        self.vk_client = vk_client
        self.rate_limiter = rate_limiter or RateLimiter()
        self.max_retries = max_retries

    def send(self, peer_id: int, text: str, reply_to: int | None = None) -> bool:
        """Отправить сообщение с retry.

        Args:
            peer_id: ID получателя
            text: Текст сообщения
            reply_to: ID сообщения, на которое ответить

        Returns:
            True если успешно отправлено, False если все попытки исчерпаны
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                time.sleep(0.5)
                self.rate_limiter.wait_if_needed()
                self.vk_client.send_message(peer_id, text, reply_to=reply_to)
                return True
            except Exception as e:
                last_error = e
                logger.warning(f'Ошибка отправки (попытка {attempt + 1}/{self.max_retries}): {e}')

                if attempt < self.max_retries - 1:
                    time.sleep(1)

        logger.error(f'Не удалось отправить сообщение после {self.max_retries} попыток: {last_error}')
        return False

    def parse(self, event_data: dict) -> Message:
        return Message.from_vk_event(event_data)
