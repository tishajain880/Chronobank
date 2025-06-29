from flask import Blueprint, request, render_template, redirect, url_for, session
from datetime import date, timedelta
from singleton_db import DatabaseConnection

loan_bp = Blueprint('loan', __name__, template_folder='../templates')

def get_user_account(user_id, account_number=None):
    db = DatabaseConnection.get_instance().get_connection()
    cursor = db.cursor(dictionary=True)
    if account_number:
        cursor.execute("""
            SELECT * FROM accounts 
            WHERE user_id = %s AND account_number = %s AND account_type = 'Savings' AND is_deleted = 0
        """, (user_id, account_number))
    else:
        cursor.execute("""
            SELECT * FROM accounts 
            WHERE user_id = %s AND account_type = 'Savings' AND is_deleted = 0
        """, (user_id,))
    return cursor.fetchone()

def add_minutes_to_balance(balance, additional_minutes):
    if not balance or ':' not in balance:
        return "0:00"
    try:
        hours, minutes = map(int, balance.split(':'))
        total_minutes = hours * 60 + minutes + additional_minutes
        new_hours = total_minutes // 60
        new_minutes = total_minutes % 60
        return f"{new_hours}:{new_minutes:02d}"
    except Exception:
        return "0:00"

@loan_bp.route('/loan', methods=['GET'])
def dashboard():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login'))

    active_tab = request.args.get('active_tab', 'loan')
    account = get_user_account(user_id)
    if not account:
        return render_template("loan.html", error=" Account not found", history=[], user=None, warnings=[], message="", active_tab=active_tab)

    db = DatabaseConnection.get_instance().get_connection()
    cursor = db.cursor(dictionary=True)

    warnings = session.pop('warnings', [])
    message = session.pop('message', "")

    cursor.execute("""
        SELECT loan_id, loan_amount, strategy, status, applied_at, repayment_due 
        FROM loans 
        WHERE user_id = %s 
        ORDER BY applied_at DESC
    """, (user_id,))
    history = cursor.fetchall()

    return render_template("loan.html", message=message, history=history, user=account, warnings=warnings, error="", active_tab=active_tab)

@loan_bp.route('/apply_loan', methods=['POST'])
def apply_loan():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login'))

    account_number = request.form.get('account_number')
    account = get_user_account(user_id, account_number)
    warnings = []

    if not account:
        warnings.append("Invalid account number.")
        session['warnings'] = warnings
        return redirect(url_for('loan.dashboard', active_tab='alerts'))

    if account.get('loan_blocked') == 1:
        warnings.append("Loan requests are currently blocked for this account.")
        session['warnings'] = warnings
        return redirect(url_for('loan.dashboard', active_tab='alerts'))

    db = DatabaseConnection.get_instance().get_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT * FROM loans 
        WHERE user_id = %s AND status = 'Approved'
    """, (user_id,))
    existing_loan = cursor.fetchone()

    if existing_loan:
        warnings.append("You already have an approved loan for this account.")
        session['warnings'] = warnings
        return redirect(url_for('loan.dashboard', active_tab='alerts'))

    try:
        loan_amount_hours = int(request.form['loan_amount'])
        if loan_amount_hours <= 0:
            raise ValueError
    except (ValueError, TypeError):
        warnings.append("Invalid loan amount. Please enter a positive number of minutes.")
        session['warnings'] = warnings
        return redirect(url_for('loan.dashboard', active_tab='alerts'))

    if loan_amount_hours > 1000:
        warnings.append(" Suspicious loan request detected. Your account has been blocked from future loan applications.")
        cursor.execute("""
            UPDATE accounts 
            SET loan_blocked = 1 
            WHERE user_id = %s AND account_number = %s
        """, (user_id, account_number))
        db.commit()
        session['warnings'] = warnings
        return redirect(url_for('loan.dashboard', active_tab='alerts'))

    strategy = request.form.get('strategy', 'basic')
    status = "Approved" if loan_amount_hours <= 500 else "Rejected"
    repayment_due = date.today() + timedelta(days=5) if status == "Approved" else None

    cursor.execute("""
        INSERT INTO loans (user_id, loan_amount, status, strategy, repayment_due)
        VALUES (%s, %s, %s, %s, %s)
    """, (user_id, loan_amount_hours, status, strategy, repayment_due))
    db.commit()

    if status == "Approved":
        loan_amount_minutes = loan_amount_hours * 60
        new_balance = add_minutes_to_balance(account['balance'], loan_amount_minutes)

      
        cursor.execute("""
            UPDATE accounts 
            SET balance = %s 
            WHERE user_id = %s AND account_number = %s
        """, (new_balance, user_id, account_number))

        cursor.execute("""
            UPDATE users 
            SET total_balance_minutes = total_balance_minutes + %s 
            WHERE id = %s
        """, (loan_amount_minutes, user_id))

      
        cursor.execute("""
            SELECT loan_id FROM loans 
            WHERE user_id = %s 
            ORDER BY applied_at DESC 
            LIMIT 1
        """, (user_id,))
        loan = cursor.fetchone()

        if loan and strategy.lower() in ['installment', 'fixed']:
            loan_id = loan['loan_id']
            now = date.today()

            if strategy.lower() == 'installment':
                installment_amount = loan_amount_hours / 4
                for i in range(4):
                    due_date = now + timedelta(weeks=(i + 1))
                    cursor.execute("""
                        INSERT INTO repayments (loan_id, user_id, installment_number, amount, due_date, strategy, status)
                        VALUES (%s, %s, %s, %s, %s, %s, 'Pending')
                    """, (loan_id, user_id, i + 1, installment_amount, due_date, strategy))

            elif strategy.lower() == 'fixed':
                due_date = now + timedelta(weeks=4)
                cursor.execute("""
                    INSERT INTO repayments (loan_id, user_id, installment_number, amount, due_date, strategy, status)
                    VALUES (%s, %s, %s, %s, %s, %s, 'Pending')
                """, (loan_id, user_id, 1, loan_amount_hours, due_date, strategy))

    db.commit()
    session['message'] = f" Loan {status} for {loan_amount_hours} hours submitted."
    return redirect(url_for('loan.dashboard', active_tab='history'))

@loan_bp.route('/eligibility', methods=['GET', 'POST'])
def eligibility():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        try:
            loan_amount = int(request.form.get('loan_amount', 0))
        except ValueError:
            return render_template("loan_eligibility.html", error=" Invalid loan amount")

        return render_template("loan_eligibility.html", message=f" Loan of {loan_amount} hours is within safe limits.")

    return render_template("loan_eligibility.html")
