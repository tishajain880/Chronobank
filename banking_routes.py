from flask import Blueprint, request, jsonify, render_template, session
from facade import BankingFacade

banking_bp = Blueprint('banking_bp', __name__, url_prefix='/banking')

@banking_bp.route("/", methods=["GET"])
def banking_page():
    return render_template("banking.html")

@banking_bp.route("/deposit", methods=["POST"])
def deposit():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "User not logged in"}), 401

    data = request.get_json()
    account_number = data.get('account_number')
    hours = data.get('hours')
    minutes = data.get('minutes')

    if not account_number or hours is None or minutes is None:
        return jsonify({"error": "Missing account number or time fields"}), 400

    try:
        total_minutes = int(hours) * 60 + int(minutes)
    except ValueError:
        return jsonify({"error": "Invalid hours or minutes"}), 400

    account = BankingFacade.get_account(user_id, account_number)
    if not account:
        return jsonify({"error": "Account not found or is not linked to this user"}), 400

    total_secs = BankingFacade.time_to_minutes(account[1]) * 60
    new_total_secs = total_secs + total_minutes * 60
    BankingFacade.update_account_balance(user_id, account_number, new_total_secs)
    BankingFacade.update_user_balance(user_id, new_total_secs)

    new_total_balance = f"{new_total_secs // 3600:02}:{(new_total_secs % 3600) // 60:02}:00"
    return jsonify({"message": "Deposit successful", "new_total_balance": new_total_balance})

@banking_bp.route("/withdraw", methods=["POST"])
def withdraw():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "User not logged in"}), 401

    data = request.get_json()
    account_number = data.get("account_number")
    time = data.get("time")

    if not account_number or time is None:
        return jsonify({"error": "Missing account number or time field"}), 400

    try:
        hours, minutes = map(int, time.strip().split(":"))
        withdraw_minutes = hours * 60 + minutes
    except ValueError:
        return jsonify({"error": "Invalid time format, use HH:MM"}), 400

    account = BankingFacade.get_account(user_id, account_number)
    if not account:
        return jsonify({"error": "Account not found or is not linked to this user"}), 400

    total_secs = BankingFacade.time_to_minutes(account[1]) * 60
    withdraw_secs = withdraw_minutes * 60

    if total_secs < withdraw_secs:
        return jsonify({"error": "Insufficient balance"}), 400

    new_total_secs = total_secs - withdraw_secs
    BankingFacade.update_account_balance(user_id, account_number, new_total_secs)
    BankingFacade.update_user_balance(user_id, new_total_secs)

    new_total_balance = f"{new_total_secs // 3600:02}:{(new_total_secs % 3600) // 60:02}:00"
    return jsonify({"message": "Withdrawal successful", "new_total_balance": new_total_balance})

@banking_bp.route("/balance", methods=["GET"])
def balance():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "User not logged in"}), 401

    account_number = request.args.get("account_number")
    if not account_number:
        return jsonify({"error": "Missing account number"}), 400

    account = BankingFacade.get_account(user_id, account_number)
    if not account:
        return jsonify({"error": "Account not found or is not linked to this user"}), 400

    current_balance = account[1]
    return jsonify({"balance": BankingFacade.minutes_to_time(BankingFacade.time_to_minutes(current_balance))})
