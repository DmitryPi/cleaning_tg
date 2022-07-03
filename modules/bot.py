import re

from .db import Database
from .utils import load_config, load_json

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
        self.users = load_json('assets/users.json')

    async def command_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Инициировать аутентификацию пользователя"""
        msg = [
            'Введите номер телефона',
            'Формат телефона c +7',
        ]
        msg = '\n'.join(msg)
        await update.message.reply_text(msg)
        return 1

    async def verif_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Принять и проверить номер телефона пользователя"""
        phone = ''.join(re.findall(r'\d+', update.message.text))
        phone_len = len(phone)
        num_limit = 11
        # Проверка длины номера / поиск в пользователях
        if phone_len == num_limit:
            try:
                user_tg = update.effective_user
                user = [user for user in self.users if user['phone_num'] == int(phone)][0]
                msg = [
                    f'Здравствуйте, {user["full_name"]}',
                ]
                msg = '\n'.join(msg)
                await update.message.reply_text(msg)
                return ConversationHandler.END
            except IndexError:
                msg = f'Ваш номер [{phone}] не найден в базе данных'
        elif phone_len > num_limit:
            msg = 'Номер слишком длинный.'
        elif phone_len < num_limit:
            msg = 'Номер слишком короткий.'
        await update.message.reply_text(msg)
        return 1

    async def command_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Помошник для вывода команд"""
        pass

    async def command_role(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Изменение роли пользователя"""
        pass

    async def conv_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancels and ends the conversation."""
        msg = 'Операция прервана'
        await update.message.reply_text(msg, reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    def run(self):
        """Запустить бота"""
        print(f'- {__class__.__name__} started')
        # Create the Application and pass it your bot's token.
        application = Application.builder().token(self.api_token).build()
        # start conversation
        start_conv = ConversationHandler(
            entry_points=[CommandHandler('start', self.command_start)],
            states={
                1: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.verif_phone)]
            },
            fallbacks=[CommandHandler('cancel', self.conv_cancel)],
        )
        # on different commands - answer in Telegram
        application.add_handler(start_conv)
        application.add_handler(CommandHandler('help', self.command_help))
        application.add_handler(CommandHandler('role', self.command_role))
        # Run the bot until the user presses Ctrl-C
        application.run_polling()
