from datetime import timedelta
import random
from singleton_db import DatabaseConnection


class AccountFactory:
    VALID_ACCOUNT_TYPES = ['Savings', 'Investment', 'Loan']

    def __init__(self, user_id, account_type, balance, full_name):
        self.user_id = user_id
        self.account_type = account_type
        self.balance = balance
        self.full_name = full_name

    def validate_input(self):
        if not all([self.account_type, self.balance, self.full_name]):
            raise ValueError("All fields are required.")
        if self.account_type not in self.VALID_ACCOUNT_TYPES:
            raise ValueError("Invalid account type.")

    def convert_balance_to_time(self):
        balance_float = float(self.balance)
        hours = int(balance_float)
        minutes = int((balance_float - hours) * 60)
        return f"{hours:02d}:{minutes:02d}:00"

    def determine_interest_rate(self, balance_float):
        if self.account_type == 'Savings':
            if balance_float < 100:
                return 2.00
            elif balance_float < 500:
                return 3.00
            else:
                return 4.00
        elif self.account_type == 'Investment':
            if balance_float < 500:
                return 5.00
            else:
                return 7.00
        elif self.account_type == 'Loan':
            return -6.00  
        else:
            return 0.00

    def generate_unique_account_number(self, cursor):
        while True:
            account_number = random.randint(10**10, 10**11 - 1)
            cursor.execute("SELECT 1 FROM accounts WHERE account_number = %s", (account_number,))
            if not cursor.fetchone():
                return account_number

    def create_account(self):
        self.validate_input()

        balance_float = float(self.balance)
        balance_time = self.convert_balance_to_time()
        new_balance_minutes = int(balance_float * 60)

        interest_rate = self.determine_interest_rate(balance_float)
        transaction_limit = round(balance_float * 10, 2)

        db_connection = DatabaseConnection.get_instance().get_connection()
        cursor = db_connection.cursor(dictionary=True)

        account_number = self.generate_unique_account_number(cursor)

        cursor.execute("""
            INSERT INTO accounts (
                user_id, fullname, account_number, account_type, balance,
                interest_rate, transaction_limit, account_status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'active')
        """, (
            self.user_id,
            self.full_name,
            account_number,
            self.account_type,
            balance_time,
            interest_rate,
            transaction_limit
        ))

        cursor.execute("""
            UPDATE users
            SET total_balance_minutes = IFNULL(total_balance_minutes, 0) + %s
            WHERE id = %s
        """, (
            new_balance_minutes,
            self.user_id
        ))

        db_connection.commit()
        cursor.close()

        return account_number
