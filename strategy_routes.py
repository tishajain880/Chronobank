from flask import Blueprint, render_template, request, redirect, session, flash, url_for
from repayment_strategy import RepaymentContext, FixedRepayment, InstallmentRepayment
from singleton_db import DatabaseConnection
from datetime import datetime

repayment_bp = Blueprint('repayment', __name__)
db = DatabaseConnection.get_instance().get_connection()

@repayment_bp.route('/repay', methods=['GET', 'POST'])
def repay():
    if 'user_id' not in session:
        return redirect('/login')
    user_id = session['user_id']

    with db.cursor(dictionary=True) as cursor:
        cursor.execute(""" 
            SELECT * FROM loans 
            WHERE user_id = %s AND status = 'Approved'  
            ORDER BY applied_at DESC 
            LIMIT 1
        """, (user_id,))
        loan = cursor.fetchone()

        if not loan:
            flash("No active loan found with 'Approved' status.", "danger")
            return render_template('repay.html', loan=None)

        loan_id, loan_amount = loan['loan_id'], loan['loan_amount']
        strategy_type = loan.get('strategy', '').lower()

        if strategy_type == 'installment':
            cursor.execute("""
                SELECT installment_number FROM repayments 
                WHERE loan_id = %s AND status != 'Paid'
                ORDER BY installment_number ASC
                LIMIT 1
            """, (loan_id,))
            pending = cursor.fetchone()
            installment_number = pending['installment_number'] if pending else None
        else:
            installment_number = None

        if request.method == 'POST':
            if strategy_type not in ['fixed', 'installment']:
                flash("Invalid repayment strategy.", "danger")
                return render_template('repay.html', loan=loan, strategy_type=strategy_type, installment_number=installment_number)

            try:
                

                strategy_class = FixedRepayment() if strategy_type == 'fixed' else InstallmentRepayment()
                context = RepaymentContext(strategy_class)
                context.execute(db, user_id, loan_id, loan_amount)

                if strategy_type == 'installment' and installment_number:
                    cursor.execute("""
                        UPDATE repayments SET status = 'Paid'
                        WHERE loan_id = %s AND installment_number = %s
                    """, (loan_id, installment_number))

                    cursor.execute("""
                        SELECT COUNT(*) as remaining FROM repayments 
                        WHERE loan_id = %s AND status != 'Paid'
                    """, (loan_id,))
                    if cursor.fetchone()['remaining'] == 0:
                        cursor.execute("UPDATE loans SET status = 'Repaid' WHERE loan_id = %s", (loan_id,))
                else:
                    cursor.execute("UPDATE loans SET status = 'Repaid' WHERE loan_id = %s", (loan_id,))

                db.commit()
                session['repayment_processed'] = True
                return redirect('/repayment_success')

            except Exception as e:
                db.rollback()
                flash(f"Error processing repayment: {e}", "danger")
                return render_template('repay.html', loan=loan, strategy_type=strategy_type, installment_number=installment_number)

    return render_template('repay.html', loan=loan, strategy_type=strategy_type, installment_number=installment_number)


@repayment_bp.route('/repayment_success')
def repayment_success():
    user_id = session['user_id']
    with db.cursor(dictionary=True) as cursor:
        cursor.execute("""
            SELECT * FROM loans
            WHERE user_id = %s AND status IN ('Approved', 'In Installments')
            ORDER BY applied_at DESC LIMIT 1
        """, (user_id,))
        loan = cursor.fetchone()

        if loan and loan['strategy'].lower() == 'installment':
            cursor.execute("""
                SELECT installment_number FROM repayments
                WHERE loan_id = %s AND status != 'Paid'
                ORDER BY installment_number ASC LIMIT 1
            """, (loan['loan_id'],))
            pending = cursor.fetchone()
            installment_number = pending['installment_number'] if pending else None
        else:
            installment_number = None

    return render_template('repayment_success.html', installment_number=installment_number, loan=loan)


@repayment_bp.route('/repay_next_installment/<int:loan_id>/<int:installment_number>', methods=['POST'])
def repay_next_installment(loan_id, installment_number):
    user_id = session['user_id']

    with db.cursor(dictionary=True) as cursor:
        cursor.execute("SELECT * FROM loans WHERE loan_id = %s AND user_id = %s", (loan_id, user_id))
        loan = cursor.fetchone()

        if not loan:
            flash("Loan not found.", "danger")
            return redirect(url_for('dashboard'))

        cursor.execute("""
            SELECT * FROM repayments 
            WHERE loan_id = %s AND installment_number = %s
        """, (loan_id, installment_number))
        installment = cursor.fetchone()

        if not installment or installment['status'] == 'Paid':
            flash("Installment already paid or not found.", "warning")
            return redirect(url_for('dashboard'))

        try:
            context = RepaymentContext(InstallmentRepayment())
            context.execute(db, user_id, loan_id, loan['loan_amount'])

            cursor.execute("""
                UPDATE repayments 
                SET status = 'Paid' 
                WHERE loan_id = %s AND installment_number = %s
            """, (loan_id, installment_number))

            cursor.execute("""
                SELECT COUNT(*) as remaining FROM repayments 
                WHERE loan_id = %s AND status != 'Paid'
            """, (loan_id,))
            if cursor.fetchone()['remaining'] == 0:
                cursor.execute("UPDATE loans SET status = 'Repaid' WHERE loan_id = %s", (loan_id,))

            db.commit()
            flash("Installment paid successfully.", "success")
        except Exception as e:
            db.rollback()
            flash(f"Error processing installment: {str(e)}", "danger")

    return redirect(url_for('repayment.repayment_success'))
