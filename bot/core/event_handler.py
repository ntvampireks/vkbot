from vk_api.longpoll import VkEventType
import time

from bot.domains.message import Message
from bot.utils.deduplication import MessageDeduplicator
from bot.utils.logger import setup_logger

logger = setup_logger(__name__, level="DEBUG")


class EventHandler:
    def __init__(self, on_message_callback, bot_user_id: int | None = None):
        self.on_message = on_message_callback
        self.deduplicator = MessageDeduplicator()
        self.bot_user_id = bot_user_id

    def handle_event(self, event):
        if event.get("type") != VkEventType.MESSAGE_NEW:
            return

        message_id = event.get("message_id", 0)
        user_id = event.get("user_id", 0)

        # Пропускаем сообщения от бота (по user_id)
        logger.debug(f'Проверка бота: bot_user_id={self.bot_user_id}, user_id={user_id}')
        if self.bot_user_id and user_id == self.bot_user_id:
            logger.info(f'Сообщение от бота {message_id}, пропускаем')
            return

        if self.deduplicator.is_duplicate(message_id):
            logger.debug(f'Дубликат события, пропускаем: message_id={message_id}')
            return

        try:
            message = Message.from_vk_event(event)

            # Дополнительная проверка: исходящие сообщения
            if message.out == 1:
                logger.debug(f'Исходящее сообщение {message_id}, пропускаем')
                return

            logger.info(f'Получено сообщение {message_id} от user_id={message.user_id}: {message.text[:50]}')
            self.on_message(message)
        except Exception as e:
            logger.error(f'Ошибка обработки события: {e}')
