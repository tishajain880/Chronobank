from flask import Blueprint, render_template, Response, session
from observer import Observer, Subject
import time
from singleton_db import DatabaseConnection

transaction_monitor_bp = Blueprint('transaction_monitor', __name__)


class User(Observer):
    def __init__(self, user_id, balance):
        self.user_id = user_id
        self.balance = balance
        self.messages = []

    def update(self, message):
        print(f"User {self.user_id} with balance {self.balance} received message: {message}")
        self.messages.append(message)


class TransactionMonitor(Subject):
    def __init__(self):
        super().__init__()
        self.latest_message = None
        self.users_loaded = set() 

    def notify_observers(self, message):
        self.latest_message = message
        super().notify_observers(message)

    def get_notifications(self):
        message = self.latest_message
        self.latest_message = None
        return message

    def load_users_as_observers(self, user_id):
        if user_id in self.users_loaded:
            return

        conn = DatabaseConnection.get_instance().get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT total_balance FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        cursor.close()

        if user:
            balance = user['total_balance']
            observer = User(user_id=user_id, balance=balance)
            self.add_observer(observer)
            self.users_loaded.add(user_id)

    def check_users_for_alerts(self, user_id):
        self.check_balance(user_id)
        self.check_suspicious_transactions(user_id)
        self.check_loan_due_dates(user_id)

    def check_balance(self, user_id):
        conn = DatabaseConnection.get_instance().get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT total_balance FROM users WHERE id = %s", (user_id,))
        result = cursor.fetchone()
        cursor.close()

        if result:
            balance = result["total_balance"]
            try:
                if balance and isinstance(balance, str) and ":" in balance:
                    hours, minutes = map(int, balance.split(":"))
                    total_minutes = hours * 60 + minutes
                    if total_minutes < 1200:  # 20 hours
                        self.notify_observers(f" Warning: User {user_id} has a low balance!")
                else:
                    raise ValueError("Invalid format")
            except (ValueError, IndexError) as e:
                print(f"[Error] Failed to parse balance for user {user_id}: {balance} ({e})")

    def check_suspicious_transactions(self, user_id):
        conn = DatabaseConnection.get_instance().get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT time_amount FROM transactions WHERE sender_id = %s OR receiver_id = %s", (user_id, user_id))
        transactions = cursor.fetchall()
        cursor.close()

        for transaction in transactions:
            try:
                hours, minutes = map(int, transaction["time_amount"].split(":"))
                total_minutes = hours * 60 + minutes
                if total_minutes > 5400:  # 90 hours
                    self.notify_observers(f"⚠️ Suspicious transaction detected for User {user_id}. Amount: {transaction['time_amount']}")
            except (ValueError, IndexError):
                print(f"[Error] Invalid time_amount format for transaction {transaction['time_amount']}")

    def check_loan_due_dates(self, user_id):
        conn = DatabaseConnection.get_instance().get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT loan_amount, repayment_due FROM loans WHERE user_id = %s AND status = 'Approved'", (user_id,))
        loans = cursor.fetchall()
        cursor.close()

        for loan in loans:
            if loan['repayment_due']:
                try:
                    repayment_due = time.mktime(time.strptime(loan['repayment_due'], '%Y-%m-%d'))
                    if repayment_due <= time.time() + 86400:  # 24 hours
                        self.notify_observers(
                            f"⏰ Reminder: Loan repayment due soon for User {user_id}. Loan amount: {loan['loan_amount']}"
                        )
                except Exception as e:
                    print(f"[Error] Failed to parse repayment date: {loan['repayment_due']} ({e})")


transaction_monitor = TransactionMonitor()


@transaction_monitor_bp.route('/events')
def sse():
    user_id = session.get("user_id")

    def generate():
        if user_id:
            transaction_monitor.load_users_as_observers(user_id)
            try:
                while True:
                    transaction_monitor.check_users_for_alerts(user_id)
                    message = transaction_monitor.get_notifications()
                    if message:
                        yield f"data: {message}\n\n"
                    time.sleep(60)
            except GeneratorExit:
                print(f"Client closed SSE connection for user {user_id}")
        else:
            yield "data: Unauthorized\n\n"

    return Response(generate(), content_type='text/event-stream')


@transaction_monitor_bp.route('/')
def index():
    conn = DatabaseConnection.get_instance().get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, total_balance FROM users")
    users = cursor.fetchall()
    cursor.close()
    return render_template("index.html", users=users)


def setup_users():
    user_id = session.get("user_id")
    if user_id:
        transaction_monitor.load_users_as_observers(user_id)
