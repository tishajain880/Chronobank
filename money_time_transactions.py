from flask import Blueprint, request, jsonify, render_template, session
from adapter import MoneyToTimeAdapter
from adapter_legacy_system import LegacyBankSystem
from singleton_db import DatabaseConnection
import datetime

money_time_transactions_bp = Blueprint('legacy', __name__)

legacy_system = LegacyBankSystem()
adapter = MoneyToTimeAdapter(legacy_system)

@money_time_transactions_bp.route('/money-time-transactions', methods=['GET'])
def money_time_transactions_page():
    return render_template('money_time_transactions.html')


@money_time_transactions_bp.route('/legacy_deposit', methods=['POST'])
def legacy_deposit():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    data = request.get_json()
    account_number = data.get('account_number')
    money_amount = int(data.get('money_amount'))
    user_id = session['user_id']

    try:
        conn = DatabaseConnection.get_instance().get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT account_type FROM accounts 
            WHERE account_number = %s AND user_id = %s
        ''', (account_number, user_id))
        row = cursor.fetchone()
        if not row:
            return jsonify({'error': 'Invalid or unauthorized account number'}), 400

        account_type = row[0]

        time_equivalent_str = adapter.deposit(user_id, account_number, money_amount)

        cursor.execute('''
            INSERT INTO money_time_transactions
            (user_id, account_type, transaction_type, time_amount, time_equivalent)
            VALUES (%s, %s, %s, %s, %s)
        ''', (user_id, account_type, 'deposit', money_amount, time_equivalent_str))

        conn.commit()
        cursor.close()

        return jsonify({
            'message': 'Deposit successful via legacy system.',
            'time_equivalent': time_equivalent_str
        })

    except Exception as e:
        conn.rollback()
        print(f"[Deposit Error]: {e}")
        if cursor: cursor.close()
        return jsonify({'error': 'Internal server error during deposit.'}), 500


@money_time_transactions_bp.route('/legacy_withdraw', methods=['POST'])
def legacy_withdraw():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    data = request.get_json()
    account_number = data.get('account_number')
    money_amount = int(data.get('money_amount'))
    user_id = session['user_id']

    try:
        conn = DatabaseConnection.get_instance().get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT account_type FROM accounts 
            WHERE account_number = %s AND user_id = %s
        ''', (account_number, user_id))
        row = cursor.fetchone()
        if not row:
            return jsonify({'error': 'Invalid or unauthorized account number'}), 400

        account_type = row[0]

        time_equivalent_str = adapter.withdraw(user_id, account_number, money_amount)

        cursor.execute('''
            INSERT INTO money_time_transactions 
            (user_id, account_type, transaction_type, time_amount, time_equivalent)
            VALUES (%s, %s, %s, %s, %s)
        ''', (user_id, account_type, 'withdraw', money_amount, time_equivalent_str))

        conn.commit()
        cursor.close()

        return jsonify({
            'message': 'Withdrawal successful via legacy system.',
            'time_equivalent': time_equivalent_str
        })

    except Exception as e:
        conn.rollback()
        print(f"[Withdraw Error]: {e}")
        if cursor: cursor.close()
        return jsonify({'error': 'Internal server error during withdrawal.'}), 500



@money_time_transactions_bp.route('/api/transactions', methods=['GET'])
def get_transactions():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']
    conn = DatabaseConnection.get_instance().get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(''' 
        SELECT transaction_type, time_amount, timestamp, time_equivalent 
        FROM money_time_transactions 
        WHERE user_id = %s 
        ORDER BY timestamp DESC
    ''', (user_id,))
    
    transactions = cursor.fetchall()
    cursor.close()

    result = [
        {
            'type': row['transaction_type'],
            'amount': row['time_amount'],
            'timestamp': row['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(row['timestamp'], datetime.datetime) else row['timestamp'],
            'time_equivalent': row['time_equivalent']
        }
        for row in transactions
    ]

    return jsonify(result)
