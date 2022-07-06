import logging

from threading import Thread

from modules.bot import SenderBot, TelegramBot
from modules.db import Database
from modules.utils import load_config


if __name__ == '__main__':
    config = load_config()
    logging_fmt = '- %(name)s - %(levelname)s - %(message)s'
    DEBUG = config.getboolean('MAIN', 'debug')

    if DEBUG:
        logging.basicConfig(level=logging.INFO, format=logging_fmt)

    # Database init
    db = Database()
    db_conn = db.create_connection(check_same_thread=False)  # only telegram_bot writes data
    db.create_table(db_conn, sql=db.sql_create_users_table)

    sender_bot = SenderBot(config['TELEGRAM']['api_token'], db, db_conn)
    Thread(target=sender_bot.run, daemon=True).start()
    telegram_bot = TelegramBot(config['TELEGRAM']['api_token'], db, db_conn)
    telegram_bot.run()
