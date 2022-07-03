from .db import Database
from .utils import load_config


class TelegramBot:
    def __init__(self, api_token: str, config=None):
        self.api_token = api_token
        self.config = config if config else load_config()
        self.db = Database()
        self.db_conn = self.db.create_connection()

    def run(self):
        pass
