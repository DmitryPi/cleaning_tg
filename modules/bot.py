from .db import Database
from .utils import load_config

from telegram import (
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)


class TelegramBot:
    def __init__(self, api_token: str, config=None):
        self.api_token = api_token
        self.config = config if config else load_config()
        self.db = Database()
        self.db_conn = self.db.create_connection()

    def command_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        pass

    def command_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        '''Помошник для вывода команд'''
        pass

    def command_role(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        '''Изменение роли пользователя'''
        pass

    def run(self):
        '''Запустить бота'''
        print(f'- {__class__.__name__} started')
        # Create the Application and pass it your bot's token.
        application = Application.builder().token(self.api_token).build()
        # on different commands - answer in Telegram
        application.add_handler(CommandHandler('start', self.command_start))
        application.add_handler(CommandHandler('help', self.command_help))
        application.add_handler(CommandHandler('role', self.command_role))
