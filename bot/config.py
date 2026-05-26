import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    VK_GROUP_TOKEN = os.getenv('VK_GROUP_TOKEN')
    VK_GROUP_ID = os.getenv('VK_GROUP_ID', '0')
    VK_BOT_NAME = os.getenv('VK_BOT_NAME')
    BOT_HOST = os.getenv('BOT_HOST', 'localhost')
    BOT_PORT = int(os.getenv('BOT_PORT', 8000))
    DIALOG_TIMEOUT_HOURS = int(os.getenv('DIALOG_TIMEOUT_HOURS', 24))

    @classmethod
    def validate(cls):
        if not cls.VK_GROUP_TOKEN:
            raise ValueError('VK_GROUP_TOKEN required in .env')
