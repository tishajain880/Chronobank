from singleton_db import DatabaseConnection
from datetime import timedelta

class BankingFacade:

    @staticmethod
    def time_to_minutes(time_input):
        if isinstance(time_input, str):
            hours, minutes = map(int, time_input.strip().split(':'))
            return hours * 60 + minutes
        elif isinstance(time_input, timedelta):
            return int(time_input.total_seconds() // 60)
        else:
            raise TypeError(f'Unsupported type for time_to_minutes: {type(time_input)}')

    @staticmethod
    def minutes_to_time(minutes):
        hours = minutes // 60
        minutes = minutes % 60
        return f'{hours:02}:{minutes:02}'

    @staticmethod
    def get_account(user_id, account_number):
        conn = DatabaseConnection.get_instance().get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT id, balance FROM accounts 
                WHERE user_id = %s AND account_number = %s AND is_deleted = 0
                LIMIT 1
            ''', (user_id, account_number))
            return cursor.fetchone()
        finally:
            cursor.close()

    @staticmethod
    def update_account_balance(user_id, account_number, new_total_secs):
        conn = DatabaseConnection.get_instance().get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE accounts 
                SET balance = SEC_TO_TIME(%s), updated_at = NOW() 
                WHERE user_id = %s AND account_number = %s AND is_deleted = 0
                LIMIT 1
            ''', (new_total_secs, user_id, account_number))
            conn.commit()
        finally:
            cursor.close()

    @staticmethod
    def update_user_balance(user_id, new_total_secs):
        conn = DatabaseConnection.get_instance().get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE users 
                SET total_balance = SEC_TO_TIME(%s), total_balance_minutes = FLOOR(%s / 60)
                WHERE id = %s
            ''', (new_total_secs, new_total_secs, user_id))
            conn.commit()
        finally:
            cursor.close()
