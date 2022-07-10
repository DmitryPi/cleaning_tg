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


def build_user(user_data: dict, tg_data: dict, manager=False) -> User:
    """user_data - из json файла; tg_data - объект телеграм пользователя"""
    now = str(datetime.now())
    username = tg_data['username'] if tg_data['username'] else tg_data['first_name']
    user_role = UserRole.MANAGER.value if manager else UserRole.USER.value
    user = User(
        tg_data['id'],
        username,
        tg_data['first_name'],
        user_data['full_name'],
        user_data['phone_num'],
        user_role,
        now,
        now,
    )
    return user
