from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from singleton_db import DatabaseConnection
from datetime import timedelta
from admin.admin_decorator import BaseTransaction, TaxDecorator, BonusDecorator
from blockchain import Blockchain
import hashlib
import json

transactions_bp = Blueprint('transactions', __name__, url_prefix='/transactions')
blockchain = Blockchain()

def convert_to_decimal(time_str):
    if isinstance(time_str, timedelta):
        total_seconds = time_str.total_seconds()
        return total_seconds / 3600
    else:
        try:
            hours, minutes = map(int, time_str.split(":"))
            if minutes >= 60 or minutes < 0:
                raise ValueError("Invalid minute value.")
            return hours + minutes / 60
        except ValueError:
            raise ValueError("Invalid time format. Expected HH:MM.")

def convert_to_hhmm(decimal_amount):
    hours = int(decimal_amount)
    minutes = int((decimal_amount - hours) * 60)
    return f"{hours:02d}:{minutes:02d}"

@transactions_bp.route('/record_transaction', methods=['GET', 'POST'])
def record_transaction():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = DatabaseConnection.get_instance().get_connection()
    cursor = conn.cursor(dictionary=True)

    error = None
    success = None

    if request.method == 'POST':
        data = request.form
        sender_id = session['user_id']
        sender_account_number = data.get('sender_account_number')
        receiver_username = data.get('receiver_username')
        receiver_account_number = data.get('receiver_account_number')
        time_input = data.get('amount')

        if not all([sender_account_number, receiver_username, receiver_account_number, time_input]):
            error = "All fields are required."
        else:
            try:
                decimal_amount = convert_to_decimal(time_input)
                if decimal_amount <= 0:
                    raise ValueError("Amount must be greater than 0.")
            except ValueError as e:
                error = f"Invalid amount format: {str(e)}"

        if not error:
            cursor.execute("SELECT id FROM users WHERE username = %s", (receiver_username,))
            receiver_user = cursor.fetchone()

            if not receiver_user:
                error = "Receiver username not found."
            else:
                receiver_id = receiver_user['id']

                cursor.execute("SELECT * FROM accounts WHERE account_number = %s AND user_id = %s",
                               (sender_account_number, sender_id))
                sender_account = cursor.fetchone()

                cursor.execute("SELECT * FROM accounts WHERE account_number = %s AND user_id = %s",
                               (receiver_account_number, receiver_id))
                receiver_account = cursor.fetchone()

                if not sender_account:
                    error = "Sender account not found."
                elif not receiver_account:
                    error = "Receiver account not found."
                elif sender_id == receiver_id:
                    error = "Cannot transfer to your own account."
                else:
                    try:
                        sender_balance = sender_account.get('balance')
                        receiver_balance = receiver_account.get('balance')

                        if sender_balance is None or receiver_balance is None:
                            error = "Account balances are not valid."
                        else:
                            sender_balance_decimal = convert_to_decimal(sender_balance)
                            receiver_balance_decimal = convert_to_decimal(receiver_balance)

                            base_transaction = BaseTransaction(decimal_amount)
                            taxed_transaction = TaxDecorator(base_transaction)
                            final_transaction = BonusDecorator(taxed_transaction)

                            final_amount = final_transaction.get_final_amount()
                            tax_amount = final_transaction.get_tax()
                            bonus_amount = final_transaction.get_bonus()

                            if sender_balance_decimal < final_amount:
                                error = "Insufficient balance after tax and bonus."
                            else:
                                new_sender_balance = sender_balance_decimal - final_amount
                                new_receiver_balance = receiver_balance_decimal + final_amount

                                sender_balance_updated = convert_to_hhmm(new_sender_balance)
                                receiver_balance_updated = convert_to_hhmm(new_receiver_balance)

                                cursor.execute("UPDATE accounts SET balance = %s WHERE account_number = %s",
                                               (sender_balance_updated, sender_account_number))
                                cursor.execute("UPDATE accounts SET balance = %s WHERE account_number = %s",
                                               (receiver_balance_updated, receiver_account_number))

                                cursor.execute("SELECT balance FROM accounts WHERE user_id = %s", (sender_id,))
                                sender_balances = cursor.fetchall()
                                total_minutes_sender = sum(convert_to_decimal(acc['balance']) * 60 for acc in sender_balances)

                                cursor.execute("UPDATE users SET total_balance_minutes = %s WHERE id = %s", 
                                               (total_minutes_sender, sender_id))

                                cursor.execute("SELECT balance FROM accounts WHERE user_id = %s", (receiver_id,))
                                receiver_balances = cursor.fetchall()
                                total_minutes_receiver = sum(convert_to_decimal(acc['balance']) * 60 for acc in receiver_balances)

                                cursor.execute("UPDATE users SET total_balance_minutes = %s WHERE id = %s", 
                                               (total_minutes_receiver, receiver_id))

                              
                                blockchain.add_transaction(
                                    sender_id=sender_id,
                                    receiver_id=receiver_id,
                                    amount=final_amount,
                                    txn_type='transfer'
                                )
                                block = blockchain.create_block(previous_hash=blockchain.get_last_block()['hash'])

                                
                                last_txn = block['transactions'][-1]
                                txn_string = json.dumps(last_txn, sort_keys=True).encode()
                                txn_hash = hashlib.sha256(txn_string).hexdigest()

                               
                                cursor.execute("""
                                    INSERT INTO transactions (
                                        sender_id, receiver_id, sender_account_number, receiver_account_number,
                                        time_amount, transaction_type, tax, bonus, timestamp, txn_hash
                                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s)
                                """, (
                                    sender_id,
                                    receiver_id,
                                    sender_account_number,
                                    receiver_account_number,
                                    f"{final_amount:.2f}",
                                    'transfer',
                                    f"{tax_amount:.2f}",
                                    f"{bonus_amount:.2f}",
                                    txn_hash
                                ))

                                conn.commit()
                                success = "Transaction completed with tax and bonus, and recorded on blockchain."

                    except (ValueError, TypeError) as e:
                        error = f"Error processing transaction: {str(e)}"

    cursor.close()
    conn.close()
    return render_template('transactions.html', error=error, success=success)

@transactions_bp.route('/view_transactions', methods=['GET'])
def view_transactions():
    if 'user_id' not in session:
        return jsonify({"message": "User not logged in"}), 401

    sender_id = session['user_id']
    conn = DatabaseConnection.get_instance().get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        query = '''
            SELECT 
                t.id, t.sender_id, t.receiver_id,
                t.sender_account_number, t.receiver_account_number,
                t.time_amount, t.transaction_type, t.timestamp,
                t.txn_hash, u.username AS receiver_username
            FROM transactions t
            JOIN users u ON t.receiver_id = u.id
            WHERE t.sender_id = %s
            ORDER BY t.timestamp DESC
        '''
        cursor.execute(query, (sender_id,))
        transactions = cursor.fetchall()

        if not transactions:
            return render_template('view_transactions.html', message="No transactions found", user_id=sender_id)

        return render_template('view_transactions.html', transactions=transactions, user_id=sender_id)

    except Exception as e:
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500

    finally:
        cursor.close()
        conn.close()
