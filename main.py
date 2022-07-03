import logging

from modules.db import Database
from modules.utils import load_config


if __name__ == '__main__':
    config = load_config()
    logging_fmt = '%(name)s - %(levelname)s - %(message)s'
    DEBUG = config['MAIN'].getboolean('debug')

    if DEBUG:
        logging.basicConfig(level=logging.INFO, format=logging_fmt)

    # Database init
    db = Database()
    db_conn = db.create_connection()
