from flask import Blueprint, session, redirect, url_for, render_template, request, jsonify
from singleton_db import DatabaseConnection
from customize_account_builder import CustomizeAccountBuilder

customize_account_bp = Blueprint('customize_account_bp', __name__)

def get_db_connection():
    return DatabaseConnection.get_instance().get_connection()

@customize_account_bp.route('/customize')
def customize_account():
    print("Session contents in /customize route:", session)

    if 'user_id' not in session or 'username' not in session:
        print("Redirecting to login due to missing session data.")
        return redirect(url_for('login'))

    print(f"User ID from session: {session['user_id']}, Username from session: {session['username']}")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM accounts WHERE user_id = %s", (session['user_id'],))
    account = cursor.fetchone()

    if not account:
        print("No account found for user_id:", session['user_id'])
        return render_template('customize_account.html', account=None, username=session['username'], is_premium=False)

    print("Account fetched from DB:", account)

    builder = CustomizeAccountBuilder(account)
    built_data = builder.convert_balance_to_hours().determine_premium_status().build()

    print("Built Data:", built_data)

    account_data = built_data.get('account', {})
    print("Account data to be passed to template:", account_data)

    return render_template(
        'customize_account.html',
        account=account_data,  
        username=session['username'],
        is_premium=built_data['is_premium'],
        user_id=session['user_id'] 
    )

@customize_account_bp.route('/update-preferences', methods=['PUT'])
def update_preferences():
    if 'user_id' not in session:
        print("Unauthorized access to update-preferences: session missing user_id")
        return jsonify({"error": "Unauthorized"}), 401

    print(f"User ID from session: {session['user_id']}, Username from session: {session['username']}")

    data = request.json
    if not data or not all(k in data for k in ('interest_rate', 'transaction_limit')):
        print("Bad request: missing required data", data)
        return jsonify({"error": "Missing data"}), 400

    user_id = session['user_id']
    interest_rate = data['interest_rate']
    transaction_limit = data['transaction_limit']

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT balance FROM accounts WHERE user_id = %s", (user_id,))
    account = cursor.fetchone()

    if not account:
        print(f"Account not found for user_id: {user_id}")
        return jsonify({"error": "Account not found"}), 404

    builder = CustomizeAccountBuilder(account)
    built_data = builder.convert_balance_to_hours().determine_premium_status().build()

    if not built_data['is_premium']:
        print(f"User {user_id} is not premium; cannot update preferences.")
        return jsonify({"error": "Only premium users can update preferences"}), 403

    cursor.execute(
        "UPDATE accounts SET interest_rate = %s, transaction_limit = %s WHERE user_id = %s",
        (interest_rate, transaction_limit, user_id)
    )
    db.commit()

    print(f"Preferences updated successfully for user_id: {user_id}")
    return jsonify({"message": "Preferences updated successfully", "user_id": user_id, "username": session['username']})
