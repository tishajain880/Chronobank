from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
from account_factory import AccountFactory

create_account_bp = Blueprint('create_account_bp', __name__)

@create_account_bp.route('/create_account', methods=['GET'])
def create_account_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('create_account.html')

@create_account_bp.route('/create_account', methods=['POST'])
def create_account():
    if 'user_id' not in session:
        return jsonify({'message': 'User not logged in'}), 401

    data = request.get_json()
    user_id = session['user_id']

    first_name = data.get('first_name')
    last_name = data.get('last_name')

    full_name = f"{first_name} {last_name}"

    account_type = data.get('account_type')
    balance = data.get('balance')

    try:
        
        factory = AccountFactory(user_id, account_type, balance, full_name)
        account_number = factory.create_account()
        return jsonify({
            'message': f'{account_type} account created successfully!',
            'account_number': account_number
        }), 201
    except ValueError as ve:
        return jsonify({'message': str(ve)}), 400
    except Exception as e:
        return jsonify({'message': f'Error creating account: {str(e)}'}), 500
