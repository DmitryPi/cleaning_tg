from enum import Enum
from dataclasses import dataclass
from datetime import datetime


class UserRole(Enum):
    USER = 'Пользователь'
    MANAGER = 'Менеджер'


@dataclass
class User:
    uid: int
    username: str
    first_name: str
    full_name: str
    phone_num: int
    role: UserRole
    created: str
    updated: str


def build_user(user_data, tg_data: dict) -> User:
    """user_data - из json файла; tg_data - объект телеграм пользователя"""
    now = str(datetime.now())
    user = User(
        tg_data['id'],
        tg_data['username'],
        tg_data['first_name'],
        user_data['full_name'],
        user_data['phone_num'],
        UserRole.USER.value,
        now,
        now,
    )
    return user
