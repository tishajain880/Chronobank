from datetime import datetime
from abc import ABC, abstractmethod

class RepaymentStrategy(ABC):
    @abstractmethod
    def repay(self, db, user_id, loan_id, loan_hours):
        pass

def deduct_from_accounts(cursor, user_id, minutes_to_deduct):
    cursor.execute("""
        SELECT id, balance FROM accounts 
        WHERE user_id = %s AND account_type != 'Loan' 
        ORDER BY id ASC
    """, (user_id,))

    accounts = cursor.fetchall()

    for acc_id, balance_str in accounts:
        hours, minutes = map(int, balance_str.split(":"))
        total = hours * 60 + minutes

        if total == 0:
            continue

        if total >= minutes_to_deduct:
            new_total = total - minutes_to_deduct
            new_balance = f"{new_total // 60:02}:{new_total % 60:02}"
            cursor.execute("UPDATE accounts SET balance = %s WHERE id = %s", (new_balance, acc_id))
            break
        else:
            cursor.execute("UPDATE accounts SET balance = '00:00' WHERE id = %s", (acc_id,))
            minutes_to_deduct -= total

def calculate_fixed_interest_minutes(loan_minutes):
    if loan_minutes <= 200 * 60:
        return loan_minutes * 2 // 100
    elif loan_minutes <= 400 * 60:
        return loan_minutes * 3 // 100
    else:
        return loan_minutes * 5 // 100

def calculate_installment_interest(loan_hours):
    if loan_hours <= 200:
        return loan_hours * 0.04
    elif loan_hours <= 400:
        return loan_hours * 0.06
    else:
        return loan_hours * 0.10

class FixedRepayment(RepaymentStrategy):
    def repay(self, db, user_id, loan_id, loan_hours):
        loan_minutes = int(float(loan_hours) * 60)
        interest_minutes = calculate_fixed_interest_minutes(loan_minutes)
        total_minutes = loan_minutes + interest_minutes

        cursor = db.cursor()
        try:
            cursor.execute("SELECT total_balance_minutes FROM users WHERE id = %s", (user_id,))
            current_balance = int(cursor.fetchone()[0])
            if current_balance < total_minutes:
                raise Exception("Insufficient balance for fixed repayment.")

            cursor.execute("""
                SELECT repayment_id FROM repayments 
                WHERE loan_id = %s AND user_id = %s AND status = 'Pending'
            """, (loan_id, user_id))
            repayment_record = cursor.fetchone()

            if repayment_record:
                cursor.execute("""
                    UPDATE repayments
                    SET status = 'Paid', amount = %s, due_date = %s
                    WHERE repayment_id = %s
                """, (total_minutes / 60, datetime.today().date(), repayment_record[0]))
            else:
                cursor.execute("""
                    INSERT INTO repayments (user_id, loan_id, strategy, amount, status, installment_number, due_date)
                    VALUES (%s, %s, 'Fixed', %s, 'Paid', 1, %s)
                """, (user_id, loan_id, total_minutes / 60, datetime.today().date()))

            cursor.execute("""
                UPDATE users SET total_balance_minutes = total_balance_minutes - %s WHERE id = %s
            """, (total_minutes, user_id))

            deduct_from_accounts(cursor, user_id, total_minutes)

            cursor.execute("""
                UPDATE loans SET status = 'Repaid' WHERE loan_id = %s
            """, (loan_id,))

            db.commit()
        except Exception as e:
            db.rollback()
            raise Exception(f"Fixed repayment failed: {str(e)}")
        finally:
            cursor.close()

class InstallmentRepayment(RepaymentStrategy):
    def repay(self, db, user_id, loan_id, loan_hours):
        loan_hours = float(loan_hours)

        cursor = db.cursor()
        try:
            cursor.execute("""
                SELECT repayment_id, amount, installment_number FROM repayments 
                WHERE loan_id = %s AND user_id = %s AND status = 'pending'
                ORDER BY installment_number ASC LIMIT 1
            """, (loan_id, user_id))
            installment = cursor.fetchone()

            if not installment:
                raise Exception("No pending installment found.")

            repayment_id, amount, installment_number = installment

            cursor.execute("""
                SELECT COUNT(*) FROM repayments 
                WHERE loan_id = %s AND user_id = %s
            """, (loan_id, user_id))
            total_installments = cursor.fetchone()[0]

            interest = calculate_installment_interest(loan_hours) / total_installments
            total_amount = float(amount) + interest
            total_minutes = int(total_amount * 60)

            cursor.execute("SELECT total_balance_minutes FROM users WHERE id = %s", (user_id,))
            current_balance = int(cursor.fetchone()[0])

            if current_balance < total_minutes:
                raise Exception("Insufficient balance for installment.")

            cursor.execute("""
                UPDATE repayments 
                SET status = 'paid', due_date = %s 
                WHERE repayment_id = %s
            """, (datetime.today().date(), repayment_id))

            cursor.execute("""
                UPDATE users SET total_balance_minutes = total_balance_minutes - %s WHERE id = %s
            """, (total_minutes, user_id))

            deduct_from_accounts(cursor, user_id, total_minutes)

            cursor.execute("""
                SELECT COUNT(*) FROM repayments 
                WHERE loan_id = %s AND status != 'paid'
            """, (loan_id,))
            remaining = cursor.fetchone()[0]

            if remaining == 0:
                cursor.execute("UPDATE loans SET status = 'Repaid' WHERE loan_id = %s", (loan_id,))

            db.commit()
        except Exception as e:
            db.rollback()
            raise Exception(f"Installment repayment failed: {str(e)}")
        finally:
            cursor.close()


class RepaymentContext:
    def __init__(self, strategy: RepaymentStrategy):
        self.strategy = strategy

    def execute(self, db, user_id, loan_id, loan_hours):
        self.strategy.repay(db, user_id, loan_id, loan_hours)
