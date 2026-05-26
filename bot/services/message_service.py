import time

from bot.core.vk_client import VKClient
from bot.domains.message import Message
from bot.utils.logger import setup_logger
from bot.services.rate_limiter import RateLimiter

logger = setup_logger(__name__)


class MessageService:
    def __init__(self, vk_client: VKClient, rate_limiter: RateLimiter | None = None):
        self.vk_client = vk_client
        self.rate_limiter = rate_limiter or RateLimiter()

    def send(self, peer_id: int, text: str):
        time.sleep(0.5)
        self.rate_limiter.wait_if_needed()
        self.vk_client.send_message(peer_id, text)

    def parse(self, event_data: dict) -> Message:
        return Message.from_vk_event(event_data)
