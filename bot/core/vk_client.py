import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from typing import Callable
import random
from bot.config import Config
from bot.utils.logger import setup_logger

logger = setup_logger(__name__)


class VKClient:
    def __init__(self):
        self.vk_session = vk_api.VkApi(
            token=Config.VK_GROUP_TOKEN
        )
        self.vk = self.vk_session.get_api()
        self.longpoll = VkLongPoll(self.vk_session)

    def send_message(self, peer_id: int, text: str):
        if len(text) > 4096:
            text = text[:4093] + '...'
        try:
            self.vk.messages.send(
                peer_id=peer_id,
                message=text,
                random_id=random.randint(0, 2**31 - 1)
            )
            logger.info(f'Сообщение отправлено в peer_id={peer_id}')
        except Exception as e:
            logger.error(f'Ошибка отправки сообщения: {e}')
            raise

    def run_forever(self, on_message: Callable):
        while True:
            try:
                for event in self.longpoll.check():
                    # event может быть объектом или dict — определяем тип
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
            except Exception as e:
                logger.error(f'Ошибка LongPoll: {e}')
                continue
