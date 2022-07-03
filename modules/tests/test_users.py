from unittest import TestCase

from ..users import build_user


class TestUtils(TestCase):
    def setUp(self):
        pass

    def test_build_user(self):
        local_data = {
            "full_name": "Иванов Иван Иванович",
            "phone_num": 79787873919
        }}
