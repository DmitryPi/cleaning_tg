import os

from unittest import TestCase
from pathlib import Path

from ..db import Database


test_db = 'testdb.sqlite3'

try:
    os.remove(test_db)
except FileNotFoundError:
    pass


class TestDatabase(TestCase):
    def setUp(self):
        self.db_file = test_db
        self.db_table = 'test_table'
        self.db = Database()
        self.db_conn = self.db.create_connection(db_file=self.db_file)
        self.sql_test_table = """
            CREATE TABLE IF NOT EXISTS {} (
                id integer PRIMARY KEY,
                test_bool boolean NOT NULL,
                test_text text NOT NULL
            );""".format(self.db_table)

    def tearDown(self):
        self.db_conn.close()

    def insert_test_objects(self):
        test_fields = ('test_bool', 'test_text')
        test_data = [(True, 'test1'), (False, 'test2'), (True, 'test3')]
        for values in test_data:
            self.db.insert_object(self.db_conn, self.db_table, test_fields, values)

    def test_db_create_connection(self):
        self.assertTrue(self.db_conn)
        self.assertTrue(Path(self.db_file).is_file())

    def test_db_create_table(self):
        created = self.db.create_table(self.db_conn, sql=self.sql_test_table)
        self.assertTrue(created)
        created = self.db.create_table(self.db_conn)
        self.assertTrue(created)

    def test_insert_object_get_objects_all(self):
        self.insert_test_objects()
        qs = self.db.get_objects_all(self.db_conn, self.db_table)
        self.assertTrue(len(qs))

    def test_update_object(self):
        qs = self.db.get_objects_all(self.db_conn, self.db_table)
        for obj in qs:
            self.db.update_object(self.db_conn, self.db_table, 'test_text', 'test_bool', ('changed', 1))
        qs = self.db.get_objects_all(self.db_conn, self.db_table)
        for obj in qs:
            if not obj[1]:  # test_bool=False
                self.assertTrue('test' in obj[2])
            else:
                self.assertTrue(obj[2] == 'changed')

    def test_delete_object(self):
        self.insert_test_objects()
        self.db.delete_object(self.db_conn, self.db_table, 'id', '2')
        qs = self.db.get_objects_all(self.db_conn, self.db_table)
        self.assertTrue(len(qs))
        for obj in qs:
            self.assertTrue(obj[0] != 2)

    def test_get_objects_filter_by_value(self):
        qs = self.db.get_objects_filter_by_value(self.db_conn, self.db_table, 'test_bool', False)
        self.assertTrue(not len(qs))
        qs = self.db.get_objects_filter_by_value(self.db_conn, self.db_table, 'test_bool', True)
        self.assertTrue(len(qs))

    def test_get_objects_field_values(self):
        qs = self.db.get_objects_field_values(self.db_conn, self.db_table, 'test_text')
        self.assertTrue(len(qs))
        self.assertTrue(isinstance(qs, list))
        for obj in qs:
            self.assertTrue(isinstance(obj, str))
            self.assertTrue('test' in obj)
