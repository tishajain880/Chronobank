from flask import Blueprint, render_template, request, redirect, session, flash, jsonify
from goal_command import AllocateTimeCommand, WithdrawTimeCommand, DeleteGoalCommand, command_manager
from goal_models import serialize_goal
from singleton_db import DatabaseConnection

goal_bp = Blueprint('goal_bp', __name__)

def get_db_connection():
    return DatabaseConnection.get_instance().get_connection()

def get_user_balance_minutes(user_id, conn):
    cur = conn.cursor()
    cur.execute("SELECT total_balance_minutes FROM users WHERE id = %s", (user_id,))
    return cur.fetchone()[0]

def format_minutes_to_time_string(minutes):
    hours = minutes // 60
    remaining_minutes = minutes % 60
    return f"{int(hours)}:{int(remaining_minutes):02d}"

@goal_bp.route('/goals')
def goals():
    if 'user_id' not in session:
        flash("Session expired or no user logged in.")
        return redirect('/login')

    user_id = session['user_id']
    try:
        conn = get_db_connection()
        total_balance_minutes = get_user_balance_minutes(user_id, conn)
        total_balance = format_minutes_to_time_string(total_balance_minutes)

        cur = conn.cursor()
        cur.execute("SELECT * FROM time_goals WHERE user_id = %s", (user_id,))
        goals = [serialize_goal(g) for g in cur.fetchall()]
        conn.close()
    except Exception as e:
        flash(f"Error: {str(e)}")
        return redirect('/login')

    return render_template('goals/goals.html', goals=goals, balance=total_balance)

@goal_bp.route('/create_goal', methods=['GET', 'POST'])
def create_goal():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    if request.method == 'POST':
        title = request.form['title']
        time_str = request.form['hours']
        hours = convert_to_hours(time_str)
        minutes_requested = int(hours * 60)

        try:
            conn = get_db_connection()
            total_balance_minutes = get_user_balance_minutes(user_id, conn)

            if minutes_requested > total_balance_minutes:
                flash("Cannot allocate more time than your current balance.")
                return redirect('/create_goal')

            cur = conn.cursor()
            cur.execute("INSERT INTO time_goals (user_id, title, saved_hours) VALUES (%s, %s, 0)", (user_id, title))
            goal_id = cur.lastrowid
            conn.commit()

            cmd = AllocateTimeCommand(user_id, goal_id, hours)
            command_manager.execute_command(cmd)

            conn.close()
            flash("Goal created successfully.")
            return redirect('/goals')

        except Exception as e:
            flash(f"Error: {str(e)}")
            return redirect('/create_goal')

    return render_template('goals/allocate_time.html')

@goal_bp.route('/withdraw_goal_hours', methods=['GET', 'POST'])
def withdraw_goal_hours():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM time_goals WHERE user_id = %s", (user_id,))
        goals = [serialize_goal(g) for g in cur.fetchall()]
        conn.close()
    except Exception as e:
        flash(f"Error: {str(e)}")
        return redirect('/goals')

    if request.method == 'POST':
        goal_id = int(request.form['goal_id'])
        time_str = request.form['hours']
        hours = convert_to_hours(time_str)

        cmd = WithdrawTimeCommand(user_id, goal_id, hours)
        command_manager.execute_command(cmd)

        return redirect('/goals')

    return render_template('goals/withdraw_time.html', goals=goals)

@goal_bp.route('/edit_goal/<int:goal_id>', methods=['GET', 'POST'])
def edit_goal(goal_id):
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM time_goals WHERE id = %s AND user_id = %s", (goal_id, user_id))
        goal = cur.fetchone()

        if not goal:
            return "Goal not found", 404

        if request.method == 'POST':
            new_title = request.form['title']
            cur.execute("UPDATE time_goals SET title = %s WHERE id = %s", (new_title, goal_id))
            conn.commit()
            conn.close()
            flash('Goal updated successfully!')
            return redirect('/goals')

        conn.close()
    except Exception as e:
        flash(f"Error: {str(e)}")
        return redirect('/goals')

    return render_template('goals/edit_goal.html', goal=serialize_goal(goal))

@goal_bp.route('/delete_goal/<int:goal_id>', methods=['POST'])
def delete_goal(goal_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM time_goals WHERE id = %s", (goal_id,))
        goal = cur.fetchone()

        if goal:
            goal_data = {
                'id': goal[0],
                'user_id': goal[1],
                'title': goal[2],
                'saved_hours': goal[3]
            }

            cmd = DeleteGoalCommand(goal_data)
            command_manager.execute_command(cmd)
            flash('Goal deleted successfully!')
        else:
            flash('Goal not found.')

        conn.close()
    except Exception as e:
        flash(f"Error: {str(e)}")

    return redirect('/goals')

@goal_bp.route('/undo', methods=['POST'])
def undo():
    command_manager.undo()
    flash('Undo successful!')
    return redirect('/goals')

@goal_bp.route('/redo', methods=['POST'])
def redo():
    command_manager.redo()
    flash('Redo successful!')
    return redirect('/goals')

def convert_to_hours(time_str):
    try:
        if ':' in time_str:
            hh, mm = map(int, time_str.split(':'))
            return hh + mm / 60
        return float(time_str)
    except ValueError:
        flash("Invalid time format")
        return 0.0
