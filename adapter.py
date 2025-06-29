from singleton_db import DatabaseConnection

class MoneyToTimeAdapter:
    def __init__(self, legacy_system):
        self.legacy_system = legacy_system
        self.rate = 2  

    def convert_money_to_time(self, money):
        total_minutes = money * self.rate
        hours = total_minutes // 60
        minutes = total_minutes % 60
        return f"{hours:02d}:{minutes:02d}"

    def time_to_minutes(self, time_str):
        h, m = map(int, time_str.split(":"))
        return h * 60 + m

    def minutes_to_time(self, total_minutes):
        h = total_minutes // 60
        m = total_minutes % 60
        return f"{h:02d}:{m:02d}"

    def deposit(self, user_id, account_number, money_amount):
        conn = DatabaseConnection.get_instance().get_connection()
        cursor = conn.cursor()

        try:
            time_str = self.convert_money_to_time(money_amount)
            time_minutes = self.time_to_minutes(time_str)


            cursor.execute('''
                SELECT balance FROM accounts
                WHERE account_number = %s AND user_id = %s
            ''', (account_number, user_id))
            result = cursor.fetchone()
            if not result:
                raise Exception("Invalid account.")
            current_balance = self.time_to_minutes(result[0])
            new_balance = current_balance + time_minutes
            cursor.execute('''
                UPDATE accounts SET balance = %s
                WHERE account_number = %s AND user_id = %s
            ''', (self.minutes_to_time(new_balance), account_number, user_id))

            cursor.execute('''
                SELECT total_balance_minutes FROM users WHERE id = %s
            ''', (user_id,))
            user_total = cursor.fetchone()[0] or 0
            new_user_total = user_total + time_minutes
            cursor.execute('''
                UPDATE users SET total_balance_minutes = %s WHERE id = %s
            ''', (new_user_total, user_id))


            self.legacy_system.deposit(user_id, money_amount, time_str)

            conn.commit()
            return time_str

        except Exception as e:
            conn.rollback()
            raise

        finally:
            cursor.close()

    def withdraw(self, user_id, account_number, money_amount):
        conn = DatabaseConnection.get_instance().get_connection()
        cursor = conn.cursor()

        try:
            time_str = self.convert_money_to_time(money_amount)
            time_minutes = self.time_to_minutes(time_str)


            cursor.execute('''
                SELECT balance FROM accounts
                WHERE account_number = %s AND user_id = %s
            ''', (account_number, user_id))
            result = cursor.fetchone()
            if not result:
                raise Exception("Invalid account.")
            current_balance = self.time_to_minutes(result[0])
            if current_balance < time_minutes:
                raise Exception("Insufficient account balance.")


            new_balance = current_balance - time_minutes
            cursor.execute('''
                UPDATE accounts SET balance = %s
                WHERE account_number = %s AND user_id = %s
            ''', (self.minutes_to_time(new_balance), account_number, user_id))


            cursor.execute('''
                SELECT total_balance_minutes FROM users WHERE id = %s
            ''', (user_id,))
            user_total = cursor.fetchone()[0] or 0
            new_user_total = user_total - time_minutes
            cursor.execute('''
                UPDATE users SET total_balance_minutes = %s WHERE id = %s
            ''', (new_user_total, user_id))


            self.legacy_system.withdraw(user_id, money_amount, time_str)

            conn.commit()
            return time_str

        except Exception as e:
            conn.rollback()
            raise

        finally:
            cursor.close()
