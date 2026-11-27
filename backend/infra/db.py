from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
import pymysql

from infra.config import DB_ENGINE, DB_HOST, DB_NAME, DB_PASSWORD, DB_USER


class Session:
    def __init__(self, connection):
        self.connection = connection

    def one(self, sql, params=()):
        with self.connection.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchone()

    def all(self, sql, params=()):
        with self.connection.cursor() as cursor:
            cursor.execute(sql, params)
            return list(cursor.fetchall())

    def execute(self, sql, params=()):
        with self.connection.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.rowcount


def connect():
    if DB_ENGINE == "mysql":
        return pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD,
                               database=DB_NAME, charset="utf8mb4",
                               cursorclass=pymysql.cursors.DictCursor, connect_timeout=5)
    return psycopg.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD,
                           dbname=DB_NAME, row_factory=dict_row, connect_timeout=5)


@contextmanager
def tx():
    connection = connect()
    try:
        yield Session(connection)
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()
