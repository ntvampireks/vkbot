import re

from bot.domains.message import Message
from bot.utils.logger import setup_logger

logger = setup_logger(__name__)


class IntentClassifier:
    def __init__(self):
        self.intents = {
            'greeting': ['привет', 'здравствуйте', 'доброго времени', 'здравствуй', 'hello', 'hi'],
            'help': ['помощь', 'help', 'что умеешь', 'подскажи', 'помогите'],
        }

    def has_mention(self, message: Message, bot_name: str | None = None) -> bool:
        """Проверка, упомянут ли бот в сообщении."""
        if not bot_name:
            return False
        text = message.text.lower()
        bot_name_lower = bot_name.lower()
        # Ищем упоминание в формате @имя или @имя(123456)
        pattern = rf'@{re.escape(bot_name_lower)}(\d+)?'
        return bool(re.search(pattern, text))

    def classify(self, message: Message) -> str:
        text = message.text.lower().strip()

        for intent, keywords in self.intents.items():
            for keyword in keywords:
                if keyword in text:
                    logger.debug(f'Определён intent: {intent}')
                    return intent

        return 'unknown'
