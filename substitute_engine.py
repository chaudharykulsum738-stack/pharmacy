from db import get_connection


def get_substitutes(user_id, medicine_id):
    conn = get_connection()
    if not conn:
        return []

    cursor = conn.cursor()
    cursor.execute("""
        SELECT m.medicine_id, m.medicine_name, m.stock_quantity, m.stock_status
        FROM substitutes s
        JOIN medicines m ON s.substitute_medicine_id = m.medicine_id
        WHERE s.medicine_id = ? AND s.user_id = ?
    """, (medicine_id, user_id))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def suggest_substitute_if_low(user_id, medicine_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT stock_status, medicine_name FROM medicines WHERE medicine_id = ? AND user_id = ?",
        (medicine_id, user_id)
    )
    medicine = cursor.fetchone()
    cursor.close()
    conn.close()

    if not medicine or medicine["stock_status"] != "Low Stock":
        return []

    substitutes = get_substitutes(user_id, medicine_id)
    available_substitutes = [s for s in substitutes if s["stock_quantity"] > 0]

    return available_substitutes


if __name__ == "__main__":
    print(suggest_substitute_if_low(user_id=1, medicine_id=1))
