from flask import session
from singleton_db import DatabaseConnection

class LegacyBankSystem:
    def validate_account(self, account_number):
        user_id = session.get('user_id')
        if user_id is None:
            raise Exception("User is not logged in.")

        conn = DatabaseConnection.get_instance().get_connection()
        cursor = conn.cursor()

        cursor.execute(''' 
            SELECT id FROM accounts 
            WHERE account_number = %s AND user_id = %s AND is_deleted = 0
        ''', (account_number, user_id))

        account = cursor.fetchone()
        cursor.close()

        if not account:
            raise ValueError("Invalid or unauthorized account number.")

        return account[0] 

    def deposit(self, user_id, money_amount, time_str):
        print(f"[LegacySystem] Deposited ₹{money_amount} (Time Equivalent: {time_str}) for User ID: {user_id}")
        return time_str

    def withdraw(self, user_id, money_amount, time_str):
        print(f"[LegacySystem] Withdrew ₹{money_amount} (Time Equivalent: {time_str}) for User ID: {user_id}")
        return time_str
