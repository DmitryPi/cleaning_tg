from unittest import TestCase

from ..users import UserRole, build_user


class TestUsers(TestCase):
    def setUp(self):
        pass

    def test_build_user(self):
        local_data = {
            "full_name": "Иванов Иван Иванович",
            "phone_num": 79787873919
        }
        tg_data = {
            'is_bot': False,
            'username': 'DmitrydevPy',
            'first_name': 'Dmitry',
            'id': 5156307333,
            'language_code': 'ru'
        }
        user = build_user(local_data, tg_data)
        assert user.uid == tg_data['id']
        assert user.username == tg_data['username']
        assert user.first_name == tg_data['first_name']
        assert user.full_name == local_data['full_name']
        assert user.phone_num == local_data['phone_num']
        assert user.role == UserRole.USER.value
        assert isinstance(user.created, str)
        assert isinstance(user.updated, str)
