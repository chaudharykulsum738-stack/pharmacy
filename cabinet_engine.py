from db import get_connection


def get_cabinet_load(cursor, cabinet_id):
    cursor.execute(
        "SELECT COALESCE(SUM(stock_quantity), 0) AS total FROM medicines WHERE cabinet_id = ?",
        (cabinet_id,)
    )
    result = cursor.fetchone()
    return result["total"] if result else 0


def recommend_cabinet(user_id, usage_frequency, stock_quantity):
    conn = get_connection()
    if not conn:
        return {"error": "Could not connect to database"}

    cursor = conn.cursor()

    if usage_frequency >= 50:
        ideal_priority = "High"
    elif usage_frequency >= 20:
        ideal_priority = "Medium"
    else:
        ideal_priority = "Low"

    cursor.execute(
        "SELECT * FROM cabinets WHERE user_id = ? AND priority_level = ?",
        (user_id, ideal_priority)
    )
    candidate_cabinets = cursor.fetchall()

    if not candidate_cabinets:
        cursor.execute("SELECT * FROM cabinets WHERE user_id = ?", (user_id,))
        candidate_cabinets = cursor.fetchall()

    best_cabinet = None
    alert = None

    for cabinet in candidate_cabinets:
        current_load = get_cabinet_load(cursor, cabinet["cabinet_id"])
        remaining_space = cabinet["capacity"] - current_load

        if remaining_space >= stock_quantity:
            best_cabinet = cabinet
            break

    if not best_cabinet:
        cursor.execute("SELECT * FROM cabinets WHERE user_id = ?", (user_id,))
        all_cabinets = cursor.fetchall()
        best_fit = None
        max_space = -1

        for cabinet in all_cabinets:
            current_load = get_cabinet_load(cursor, cabinet["cabinet_id"])
            remaining_space = cabinet["capacity"] - current_load
            if remaining_space > max_space:
                max_space = remaining_space
                best_fit = cabinet

        best_cabinet = best_fit
        alert = (
            f"All '{ideal_priority}' priority cabinets are at/near capacity. "
            f"Falling back to '{best_cabinet['cabinet_name']}' "
            f"(only {max_space} units free)."
        )

    cursor.close()
    conn.close()

    return {
        "cabinet_id": best_cabinet["cabinet_id"],
        "cabinet_name": best_cabinet["cabinet_name"],
        "priority_level": best_cabinet["priority_level"],
        "alert": alert
    }


if __name__ == "__main__":
    result = recommend_cabinet(user_id=1, usage_frequency=60, stock_quantity=30)
    print(result)
