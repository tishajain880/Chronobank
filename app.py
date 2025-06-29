from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from flask_cors import CORS
from datetime import timedelta
from create_account import create_account_bp
from transactions import transactions_bp
from customize_account import customize_account_bp 
from banking_routes import banking_bp
from admin.models import db
from admin.admin import admin_blueprint, init_admin
from singleton_db import DatabaseConnection
from account_state import Account 
from goal_routes import goal_bp
from apply_loan import loan_bp
from money_time_transactions import money_time_transactions_bp  # adjust path if needed
from alert_routes import transaction_monitor_bp
from strategy_routes import repayment_bp

app = Flask(__name__)
CORS(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root@localhost/chronobank'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key'

db.init_app(app)

# Register Blueprints
app.register_blueprint(create_account_bp)
app.register_blueprint(customize_account_bp)
app.register_blueprint(transactions_bp, url_prefix='/transactions')
app.register_blueprint(banking_bp)
app.register_blueprint(admin_blueprint)
app.register_blueprint(goal_bp)
app.register_blueprint(money_time_transactions_bp)
app.register_blueprint(loan_bp, url_prefix='/loan')
app.register_blueprint(transaction_monitor_bp, url_prefix='/monitor')
app.register_blueprint(repayment_bp)
init_admin(app)

@app.route('/', endpoint='index')
@app.route('/index')
def home():
    return render_template('index.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    return render_template('contact.html')

@app.route('/about', methods=['GET', 'POST'])
def about():
    return render_template('about.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    username = session['username']
    db_conn = DatabaseConnection.get_instance().get_connection()

    with db_conn.cursor(dictionary=True, buffered=True) as account_cursor:
        account_cursor.execute("SELECT * FROM accounts WHERE user_id = %s", (user_id,))
        account = account_cursor.fetchone()

    if account:
        balance_str = str(account['balance'])
        try:
            if ':' in balance_str:
                hours, minutes = map(int, balance_str.split(':'))
            else:
                hours = int(float(balance_str))
                minutes = int(round((float(balance_str) - hours) * 60))
        except Exception as e:
            print(f"Invalid balance format in dashboard: {balance_str}, error: {e}")
            hours, minutes = 0, 0

        balance_hours = hours + minutes / 60
        is_premium = balance_hours > 50
        interest_rate = account.get('interest_rate', 0)
        account_status = account.get('account_status', 'Unknown')
        account['balance'] = round(balance_hours, 2)
    else:
        account = {'balance': 0}
        is_premium = False
        interest_rate = 0
        account_status = 'Unknown'

    with db_conn.cursor(dictionary=True, buffered=True) as txn_cursor:
        txn_cursor.execute("""
            SELECT * FROM transactions
            WHERE sender_id = %s OR receiver_id = %s
            ORDER BY timestamp DESC LIMIT 5
        """, (user_id, user_id))
        transactions = txn_cursor.fetchall()

    return render_template(
        'dashboard.html',
        username=username,
        account=account,
        is_premium=is_premium,
        transactions=transactions,
        user_id=user_id,
        interest_rate=interest_rate,
        account_status=account_status,
        total_balance=account['balance']
    )


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.json
        username = data['username']
        password = data['password']

        db_conn = DatabaseConnection.get_instance().get_connection()
        cursor = db_conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()

        if user and user['password'] == password:
            cursor.execute("SELECT * FROM accounts WHERE user_id = %s", (user['id'],))
            account = cursor.fetchone()

            if account:
                balance_str = str(account['balance'])
                try:
                    if ':' in balance_str:
                        hours, minutes = map(int, balance_str.split(':'))
                    else:
                        hours = int(float(balance_str))
                        minutes = int(round((float(balance_str) - hours) * 60))
                except Exception as e:
                    print(f"Invalid balance format in login: {balance_str}, error: {e}")
                    hours, minutes = 0, 0

                balance_hours = hours + minutes / 60
                is_premium = balance_hours > 50
                account['balance'] = round(balance_hours, 2)
            else:
                is_premium = False
                account = {'balance': 0}

            # Set session variables
            session['username'] = user['username']
            session['user_id'] = user['id']

            return jsonify({
                "user_id": user['id'],
                "username": user['username'],
                "is_premium": is_premium,
                "account": account
            })

        flash("Invalid credentials.")
        return jsonify({"error": "Invalid credentials"}), 401

    return render_template('login.html')



@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if not username or not password:
            return jsonify({'message': 'All fields are required'}), 400

        conn = DatabaseConnection.get_instance().get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        existing_user = cursor.fetchone()

        if existing_user:
            return jsonify({'message': 'Username already taken'}), 400

        cursor.execute(
            "INSERT INTO users (username, password, total_balance_minutes) VALUES (%s, %s, %s)",
            (username, password, 0)
        )
        conn.commit()
        cursor.close()
        conn.close()

        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/account_status', methods=['GET'], endpoint='account_status_page')
def show_account_status_form():
    return render_template("account_status.html")

@app.route('/get_account_status', methods=['POST'])
def get_account_status():
    # Check if user is logged in
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized access. Please log in."}), 401

    data = request.get_json()
    account_number = data.get("account_number")

    if not account_number:
        return jsonify({"error": "Account number is required"}), 400

    try:
        conn = DatabaseConnection.get_instance().get_connection()
        cursor = conn.cursor(dictionary=True)
        # Only fetch account if it belongs to current session user
        cursor.execute("""
            SELECT * FROM accounts 
            WHERE account_number = %s AND user_id = %s
        """, (account_number, user_id))
        record = cursor.fetchone()
        conn.close()

        if not record:
            return jsonify({"error": "Account not found or does not belong to the logged-in user"}), 404

        # Create Account object (without account_id)
        account = Account(
            account_number=record["account_number"],
            balance=record["balance"],
            status_code=record["account_status"]
        )

        return jsonify({
            "account_number": account.account_number,
            "balance": account.balance,
            "status": account.get_state_description()
        })

    except Exception as e:
        print(f"Error fetching account: {e}")
        return jsonify({"error": "Internal Server Error"}), 500



@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    return redirect(url_for('index'))



if __name__ == '__main__':
    app.run(debug=True)
