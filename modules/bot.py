import re
import html
import json
import logging
import traceback

from .db import Database
from .users import UserRole, build_user
from .utils import load_config, load_json

from telegram import (
    Bot,
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
        """Проверка типа файла и его обновление"""
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

    async def command_review(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Создать клавиатуру для оценки 1-10"""
        try:
            user = self.db.get_user(self.db_conn, update.effective_user.id)
            msg = 'Оцените качество услуги:'
            score_btns = [
                [InlineKeyboardButton(i, callback_data=i) for i in range(1, 6)],
                [InlineKeyboardButton(i, callback_data=i) for i in range(6, 11)]
            ]
            reply_keyboard = [score_btns[0], score_btns[1]]
            reply_markup = InlineKeyboardMarkup(reply_keyboard)
            context.user_data.update({'user': user})  # save current user
            await update.message.reply_text(msg, reply_markup=reply_markup)
            return 1
        except IndexError:
            await update.message.reply_text(self.auth_invalid_msg)
            return ConversationHandler.END

    async def review_score(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка ответа оценки"""
        query = update.callback_query
        await query.answer()
        context.user_data.update({'review_score': query.data})
        msg = 'Напишите отзыв:\nПропустить - /skip'
        await query.edit_message_text(text=msg)
        return 2

    async def review_comment(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Принятие комментария пользователя и завершения диалога"""
        score = context.user_data['review_score']
        comment = update.message.text.replace('/', '')
        msg = 'Спасибо за оставленный отзыв'
        await update.message.reply_text(msg)
        return ConversationHandler.END

    async def command_role(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Log the error and send a telegram message to notify the developer."""
        # Log the error before we do anything else, so we can see it even if something breaks.
        logging.error(msg="\n\nException while handling an update:", exc_info=context.error)

        # traceback.format_exception returns the usual python message about an exception, but as a
        # list of strings rather than a single string, so we have to join them together.
        tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
        tb_string = "".join(tb_list)

        # Build the message with some markup and additional information about what happened.
        # You might need to add some logic to deal with messages longer than the 4096 character limit.
        update_str = update.to_dict() if isinstance(update, Update) else str(update)
        message = (
            f"An exception was raised while handling an update\n"
            f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
            "</pre>\n\n"
            f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
            f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n"
            f"<pre>{html.escape(tb_string)}</pre>"
        )

        # Finally, send the message
        await context.bot.send_message(
            chat_id=self.config['TELEGRAM']['admin_id'], text=message, parse_mode=ParseMode.HTML
        )

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
        # review conversation
        review_conv_handler = ConversationHandler(
            entry_points=[CommandHandler('review', self.command_review)],
            states={
                1: [CallbackQueryHandler(self.review_score)],
                2: [MessageHandler(filters.TEXT, self.review_comment)],
            },
            fallbacks=[CommandHandler('cancel', self.conv_cancel)],
        )
        # on different commands - answer in Telegram
        application.add_handler(start_conv_handler)
        application.add_handler(CommandHandler('help', self.command_help))
        application.add_handler(role_conv_handler)
        application.add_handler(upload_conv_handler)
        application.add_handler(review_conv_handler)
        # ...and the error handler
        application.add_error_handler(self.error_handler)
        # Run the bot until the user presses Ctrl-C
        application.run_polling()
