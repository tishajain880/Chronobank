import mysql.connector
from mysql.connector import errors

class DatabaseConnection:
    _instance = None

    def __init__(self):
        if DatabaseConnection._instance is not None:
            raise Exception("This class is a singleton!")
        self._connect()
        DatabaseConnection._instance = self

    def _connect(self):
        self.connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="chronobank"
        )

    @staticmethod
    def get_instance():
        if DatabaseConnection._instance is None:
            DatabaseConnection()
        return DatabaseConnection._instance

    def get_connection(self):
        try:
            if not self.connection.is_connected():
                self.connection.reconnect(attempts=3, delay=2)
        except errors.Error:
            try:
                self.connection.close()
            except:
                pass
            self._connect()
        return self.connection
