import re

from .db import Database
from .users import UserRole, build_user
from .utils import load_config, load_json

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.constants import ParseMode
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

    @property
    def auth_invalid_msg(self) -> str:
        return 'Пройдите аутентификацию.\nИспользуйте команду - /start'

    async def command_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Инициировать аутентификацию пользователя"""
        user_id = update.effective_user.id
        try:
            user = self.db.get_user(self.db_conn, user_id)
            msg = f'Здравствуйте, {user.full_name}'
            await update.message.reply_text(msg)
            return ConversationHandler.END
        except IndexError:
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
                user = [user for user in self.users if user['phone_num'] == int(phone)][0]
                msg = f'Здравствуйте, {user["full_name"]}'
                await update.message.reply_text(msg)
                # insert user to db
                user = build_user(user, update.effective_user)
                self.db.insert_user(self.db_conn, user)
                # end conversation
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
        try:
            user = self.db.get_user(self.db_conn, update.effective_user.id)
            msg = [
                '<b>Доступные команды:</b>',
                '/start - Аутентификацию по номеру телефона',
                '/help - Вызвать помошник команд',
                '/review - Оставить отзыв',
            ]
            if user.role == UserRole.MANAGER.value:
                msg.append('/upload - Загрузить таблицу пользователей')
            msg = '\n'.join(msg)
            await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
        except IndexError:
            await update.message.reply_text(self.auth_invalid_msg)

    async def command_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Загрузить обновленных пользователей"""
        try:
            user = self.db.get_user(self.db_conn, update.effective_user.id)
            if user.role == UserRole.MANAGER.value:
                msg = 'Загрузите файл в формате json'
                await update.message.reply_text(msg)
                return 1
            else:
                msg = 'У вас недостаточно прав.'
                await update.message.reply_text(msg)
                return ConversationHandler.END
        except IndexError:
            await update.message.reply_text(self.auth_invalid_msg)
            return ConversationHandler.END

    async def upload_users(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        try:
            new_users = update.message.document
            new_users_path = 'assets/users.json'
            if new_users['mime_type'] == 'application/json':  # check type
                new_users = await new_users.get_file()
                await new_users.download(new_users_path)
                msg = 'Новые пользователи загружены'
                await update.message.reply_text(msg)
                return ConversationHandler.END
            else:  # invalid type
                raise TypeError
        except TypeError:
            msg = 'Неверный формат файла\nДля отмены операции - /cancel'
            await update.message.reply_text(msg)
            return 1

    async def command_review(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        pass

    async def command_role(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Изменение роли пользователя"""
        try:
            self.db.get_user(self.db_conn, update.effective_user.id)  # validate user
            role_btns = [
                InlineKeyboardButton(role.value, callback_data=role.value) for role in UserRole]
            reply_keyboard = [role_btns]
            reply_markup = InlineKeyboardMarkup(reply_keyboard)
            msg = 'Выберите роль:'
            await update.message.reply_text(msg, reply_markup=reply_markup)
            return 1
        except IndexError:
            await update.message.reply_text(self.auth_invalid_msg)
            return ConversationHandler.END

    async def role_change(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Изменение роли без пароля"""
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        new_role = query.data
        if new_role == UserRole.MANAGER.value:
            context.user_data.update({'role_change': new_role})
            msg = 'Введите пароль:'
            await query.edit_message_text(text=msg)
            return 2
        else:
            msg = f'Ваша роль изменена на [{query.data}]'
            await query.edit_message_text(text=msg)
            self.db.update_object(
                self.db_conn, 'users', 'role', 'uid', (new_role, user_id))
            return ConversationHandler.END

    async def role_change_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Изменение роли с введением пароля"""
        password = update.message.text
        if password == self.config['TELEGRAM']['manager_password']:
            user_id = update.effective_user.id
            new_role = context.user_data['role_change']
            self.db.update_object(
                self.db_conn, 'users', 'role', 'uid', (new_role, user_id))
            msg = f'Ваша роль изменена на [{new_role}]'
            await update.message.reply_text(msg)
            return ConversationHandler.END
        else:
            msg = 'Введите пароль:\n/cancel - для отмены операции'
            await update.message.reply_text(msg)
            return 2

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
        start_conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', self.command_start)],
            states={
                1: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.verif_phone)]
            },
            fallbacks=[CommandHandler('cancel', self.conv_cancel)],
        )
        # role change conversation
        role_conv_handler = ConversationHandler(
            entry_points=[CommandHandler('role', self.command_role)],
            states={
                1: [CallbackQueryHandler(self.role_change)],
                2: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.role_change_password)]
            },
            fallbacks=[CommandHandler('cancel', self.conv_cancel)],
        )
        # upload conversation
        upload_conv_handler = ConversationHandler(
            entry_points=[CommandHandler('upload', self.command_upload)],
            states={
                1: [MessageHandler(~filters.COMMAND, self.upload_users)],
            },
            fallbacks=[CommandHandler('cancel', self.conv_cancel)],
        )
        # on different commands - answer in Telegram
        application.add_handler(start_conv_handler)
        application.add_handler(CommandHandler('help', self.command_help))
        application.add_handler(role_conv_handler)
        application.add_handler(upload_conv_handler)
        # Run the bot until the user presses Ctrl-C
        application.run_polling()
