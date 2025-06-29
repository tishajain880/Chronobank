def serialize_user(user):
    return {
        "id": user[0],
        "name": user[1],
        "balance": user[2]
    }

def serialize_goal(goal):
    return {
        "id": goal[0],
        "user_id": goal[1],
        "title": goal[2],
        "saved_hours": goal[3]
    }

def serialize_transaction(tx):
    return {
        "id": tx[0],
        "user_id": tx[1],
        "goal_id": tx[2],
        "hours": tx[3],
        "type": tx[4],
        "timestamp": tx[5].strftime("%Y-%m-%d %H:%M:%S")
    }