from datetime import datetime
from singleton_db import DatabaseConnection

class Command:
    def execute(self): pass
    def undo(self): pass

def format_minutes_to_time_string(minutes):
    hours = minutes // 60
    remaining_minutes = minutes % 60
    return f"{hours:02d}:{remaining_minutes:02d}"

def update_account_balance_from_user(cur, user_id):
    cur.execute("SELECT total_balance_minutes FROM users WHERE id = %s", (user_id,))
    minutes = cur.fetchone()[0]
    formatted = format_minutes_to_time_string(minutes)
    cur.execute("UPDATE accounts SET balance = %s WHERE user_id = %s", (formatted, user_id))

class AllocateTimeCommand(Command):
    def __init__(self, user_id, goal_id, hours):
        self.user_id = user_id
        self.goal_id = goal_id
        self.hours = hours
        self.transaction_id = None

    def execute(self):
        conn = DatabaseConnection.get_instance().get_connection()
        cur = conn.cursor()
        try:
            minutes = int(self.hours * 60)

            cur.execute("UPDATE time_goals SET saved_hours = saved_hours + %s WHERE id = %s", (self.hours, self.goal_id))
            cur.execute("UPDATE users SET total_balance_minutes = total_balance_minutes - %s WHERE id = %s", (minutes, self.user_id))
            update_account_balance_from_user(cur, self.user_id)

            cur.execute("INSERT INTO goal_transactions (user_id, goal_id, hours, type, timestamp) VALUES (%s, %s, %s, 'allocate', %s)",
                        (self.user_id, self.goal_id, self.hours, datetime.now()))
            self.transaction_id = cur.lastrowid

            conn.commit()
        except Exception as e:
            print(f"Error during execution: {e}")
            conn.rollback()
        finally:
            conn.close()

    def undo(self):
        conn = None
        try:
            conn = DatabaseConnection.get_instance().get_connection()
            cur = conn.cursor()
            minutes = int(self.hours * 60)

            cur.execute("UPDATE users SET total_balance_minutes = total_balance_minutes + %s WHERE id = %s",
                        (minutes, self.user_id))
            cur.execute("UPDATE time_goals SET saved_hours = saved_hours - %s WHERE id = %s",
                        (self.hours, self.goal_id))
            update_account_balance_from_user(cur, self.user_id)

            if self.transaction_id:
                cur.execute("DELETE FROM goal_transactions WHERE id = %s", (self.transaction_id,))

            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()

class WithdrawTimeCommand(Command):
    def __init__(self, user_id, goal_id, hours):
        self.user_id = user_id
        self.goal_id = goal_id
        self.hours = hours
        self.transaction_id = None

    def execute(self):
        conn = None
        try:
            conn = DatabaseConnection.get_instance().get_connection()
            cur = conn.cursor()
            minutes = int(self.hours * 60)

            cur.execute("UPDATE users SET total_balance_minutes = total_balance_minutes + %s WHERE id = %s",
                        (minutes, self.user_id))
            cur.execute("UPDATE time_goals SET saved_hours = saved_hours - %s WHERE id = %s",
                        (self.hours, self.goal_id))
            update_account_balance_from_user(cur, self.user_id)

            cur.execute("INSERT INTO goal_transactions (user_id, goal_id, hours, type, timestamp) VALUES (%s, %s, %s, 'withdraw', %s)",
                        (self.user_id, self.goal_id, self.hours, datetime.now()))
            self.transaction_id = cur.lastrowid

            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()

    def undo(self):
        conn = None
        try:
            conn = DatabaseConnection.get_instance().get_connection()
            cur = conn.cursor()
            minutes = int(self.hours * 60)

            cur.execute("UPDATE users SET total_balance_minutes = total_balance_minutes - %s WHERE id = %s",
                        (minutes, self.user_id))
            cur.execute("UPDATE time_goals SET saved_hours = saved_hours + %s WHERE id = %s",
                        (self.hours, self.goal_id))
            update_account_balance_from_user(cur, self.user_id)

            if self.transaction_id:
                cur.execute("DELETE FROM goal_transactions WHERE id = %s", (self.transaction_id,))

            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()

class DeleteGoalCommand(Command):
    def __init__(self, goal_data):
        self.goal_data = goal_data

    def execute(self):
        conn = None
        try:
            conn = DatabaseConnection.get_instance().get_connection()
            cur = conn.cursor()
            cur.execute("DELETE FROM time_goals WHERE id = %s", (self.goal_data['id'],))
            cur.execute("DELETE FROM goal_transactions WHERE goal_id = %s", (self.goal_data['id'],))
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()

    def undo(self):
        conn = None
        try:
            conn = DatabaseConnection.get_instance().get_connection()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO time_goals (id, user_id, title, saved_hours) VALUES (%s, %s, %s, %s)",
                (self.goal_data['id'], self.goal_data['user_id'], self.goal_data['title'], self.goal_data['saved_hours'])
            )
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()

class CommandManager:
    def __init__(self):
        self.undo_stack = []
        self.redo_stack = []

    def execute_command(self, command):
        command.execute()
        self.undo_stack.append(command)
        self.redo_stack.clear()

    def undo(self):
        if self.undo_stack:
            command = self.undo_stack.pop()
            command.undo()
            self.redo_stack.append(command)

    def redo(self):
        if self.redo_stack:
            command = self.redo_stack.pop()
            command.execute()
            self.undo_stack.append(command)

command_manager = CommandManager()
