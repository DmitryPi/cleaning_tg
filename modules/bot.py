import asyncio
import re
import html
import json
import logging
import traceback

from datetime import datetime
from time import sleep
from telegram import (
    Bot,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
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
from telegram.error import BadRequest

from .users import User, UserRole, build_user
from .utils import (
    load_config,
    load_json,
    handle_error,
    update_json_file,
    get_datetime_passed_seconds,
    slice_sheet_dates,
    format_cleaning_date,
)


class SenderBot:
    def __init__(self, api_token: str, db, db_conn, config=None):
        self.api_token = api_token
        self.db = db
        self.db_conn = db_conn
        self.jobs_path = 'assets/task_jobs.json'

    async def raw_send_message(self, chat_id, msg):
        """Raw api send_message: asyncio.run(raw_send_message())"""
        async with Bot(self.api_token) as bot:
            await bot.send_message(chat_id, msg)

    def get_task_jobs(self) -> list[dict]:
        """Получить задачи или создать пустой файл"""
        try:
            jobs = load_json(self.jobs_path)
        except FileNotFoundError:
            update_json_file([], self.jobs_path)
            jobs = load_json(self.jobs_path)
        return jobs

    def build_task_job(self, user: User, date: str) -> dict:
        """Создать объект задачи"""
        job = {
            'uid': user.uid,
            'phone_num': user.phone_num,
            'job_at': date,
            'sent': False,
        }
        return job

    def build_task_jobs(self, users: dict, users_db: list[User]) -> list[dict]:
        """Создать задачи, если юзер в таблице и в базе данных бота"""
        jobs = []
        for user in users:
            date = slice_sheet_dates(user['clean_time'])
            date = format_cleaning_date(date)
            if not date:
                continue
            for user_db in users_db:
                if user['phone_num'] == user_db.phone_num:
                    job = self.build_task_job(user_db, date)
                    jobs.append(job)
        return jobs

    def run(self):
        """Берем пользователей из базы данных и таблицы
           Создаем новые задачи build_task_jobs
           Проверяем, если нет задач, добавить новые
           Проверяем, если задача отправлена(sent),
             Проверяем текущий день/удаляем из задач
           Проверяем количество секунд до задачи
             Если < 0, отправляем сообщение в телеграм
                Обновляем sent=True
           Обновляем файл задач
        """
        while True:
            try:
                users = load_json('assets/users.json')
                users_db = [
                    User(*user) for user in self.db.get_objects_all(self.db_conn, 'users')]
                current_tasks = self.get_task_jobs()
                new_tasks = self.build_task_jobs(users, users_db)
                # если нет задач, добавить новые задачи
                if not current_tasks:
                    if new_tasks:
                        update_json_file(new_tasks, file_path=self.jobs_path)
                        current_tasks = self.get_task_jobs()
                # проверить таски по времени / отправить сообщение в тг / задать sent=True
                for i, task in enumerate(current_tasks):
                    if task['sent']:
                        # проверить если наступил новый день
                        today = str(datetime.today().date())
                        if today not in task['job_at']:
                            del current_tasks[i]
                        continue
                    # сколько секунд до задачи
                    until_task = get_datetime_passed_seconds(task['job_at'], reverse=True)
                    if until_task < 0:
                        print('- Sending message to:', task['uid'])
                        msg = 'Если вы хотите оставить отзыв.\nВызовите команду - /review'
                        try:
                            asyncio.run(self.raw_send_message(task['uid'], msg))
                        except BadRequest:
                            print('- chat not found')
                        task['sent'] = True
                update_json_file(current_tasks, file_path=self.jobs_path)
            except Exception as e:
                handle_error(e, to_file=True)
            sleep(5)


class TelegramBot:
    def __init__(self, api_token: str, db, db_conn, config=None):
        self.api_token = api_token
        self.config = config if config else load_config()
        self.db = db
        self.db_conn = db_conn
        self.users = load_json('assets/users.json')

    @property
    def auth_invalid_msg(self) -> str:
        return 'Пройдите идентификацию.\nИспользуйте команду - /start'

    async def command_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Инициировать аутентификацию пользователя"""
        user_id = update.effective_user.id
        try:
            user = self.db.get_user(self.db_conn, user_id)
            msg = [
                f'Здравствуйте, {user.full_name}',
                'Если вы хотите оставить отзыв',
                'Вызовите команду - /review',
            ]
            msg = '\n'.join(msg)
            await update.message.reply_text(msg)
            return ConversationHandler.END
        except IndexError:
            msg = [
                'Введите номер телефона для идентификации',
                'Формат телефона c 8',
            ]
            msg = '\n'.join(msg)
            await update.message.reply_text(msg)
            return 1

    async def verif_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Принять и проверить номер телефона пользователя"""
        phone = ''.join(re.findall(r'\d+', update.message.text))
        phone_len = len(phone)
        num_limit = 11
        # Проверка если пользователь ввел секретный пароль
        if phone == self.config['TELEGRAM']['manager_password']:
            user = {
                'full_name': update.effective_user.first_name,
                'phone_num': 0,
            }
            msg = f'Здравствуйте, {user["full_name"]}\nВаша роль менеджер'
            await update.message.reply_text(msg)
            user = build_user(user, update.effective_user, manager=True)
            self.db.insert_user(self.db_conn, user)
            return ConversationHandler.END
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
                '/role - Изменение роли',
                '/review - Оставить отзыв',
            ]
            if user.role == UserRole.MANAGER.value:
                msg.append('/upload - Загрузить таблицу пользователей')
            msg = '\n'.join(msg)
            await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
        except IndexError:
            await update.message.reply_text(self.auth_invalid_msg)

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
        msg = 'Напишите комментарий:\nПропустить - /skip'
        await query.edit_message_text(text=msg)
        return 2

    async def review_comment(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Принятие комментария пользователя и завершения диалога"""
        managers = self.db.get_managers(self.db_conn)
        user = context.user_data['user']
        score = context.user_data['review_score']
        comment = update.message.text.replace('/skip', '')
        msg = 'Спасибо за оставленный отзыв!'
        review_msg = [
            '<b>Отзыв пользователя:</b>',
            f'<b>ID:</b> {user.uid}',
            f'<b>ФИО:</b> {user.full_name}',
            f'<b>Номер телефон:</b> {user.phone_num}',
            f'<b>Оценка:</b> {score}',
            f'<b>Комментарий:</b> {comment}',
        ]
        await update.message.reply_text(msg)
        for manager in managers:
            await context.bot.send_message(
                chat_id=manager.uid,
                text='\n'.join(review_msg),
                parse_mode=ParseMode.HTML,
            )
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
            chat_id=self.config['TELEGRAM']['developer_id'],
            text=message,
            parse_mode=ParseMode.HTML
        )

    def run(self):
        """Запустить бота"""
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
        # application.add_handler(upload_conv_handler)
        application.add_handler(review_conv_handler)
        # ...and the error handler
        application.add_error_handler(self.error_handler)
        # Run the bot until the user presses Ctrl-C
        application.run_polling()
