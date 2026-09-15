from db import get_connection


def classify_medicine_movement(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT medicine_id, medicine_name, usage_frequency FROM medicines WHERE user_id = ?",
        (user_id,)
    )
    medicines = cursor.fetchall()
    cursor.close()
    conn.close()

    for med in medicines:
        freq = med["usage_frequency"]
        if freq >= 50:
            med["movement"] = "Fast-moving"
        elif freq >= 20:
            med["movement"] = "Moderate-moving"
        else:
            med["movement"] = "Slow-moving"

    return medicines


def detect_unusual_purchases(user_id, lookback_limit=50, min_sales_for_baseline=3, multiplier=3):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s.sale_id, s.quantity_sold, s.sale_date, m.medicine_id, m.medicine_name,
               c.name AS customer_name, c.contact_number
        FROM sales s
        JOIN medicines m ON s.medicine_id = m.medicine_id
        JOIN customers c ON s.customer_id = c.customer_id
        WHERE s.user_id = ?
        ORDER BY s.sale_date DESC
        LIMIT ?
    """, (user_id, lookback_limit))
    recent_sales = cursor.fetchall()

    flagged = []
    for sale in recent_sales:
        cursor.execute("""
            SELECT AVG(quantity_sold) AS avg_qty, COUNT(*) AS n
            FROM sales
            WHERE user_id = ? AND medicine_id = ? AND sale_id != ?
        """, (user_id, sale["medicine_id"], sale["sale_id"]))
        baseline = cursor.fetchone()

        if baseline["n"] < min_sales_for_baseline or not baseline["avg_qty"]:
            continue

        if sale["quantity_sold"] > multiplier * baseline["avg_qty"]:
            flagged.append({
                "medicine_name": sale["medicine_name"],
                "customer_name": sale["customer_name"],
                "contact_number": sale["contact_number"],
                "quantity_sold": sale["quantity_sold"],
                "typical_quantity": round(baseline["avg_qty"], 1),
                "sale_date": sale["sale_date"]
            })

    cursor.close()
    conn.close()
    return flagged


def get_refill_reminders(user_id, min_purchase_count=2):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.name AS customer_name, c.contact_number, m.medicine_name,
               COUNT(*) AS purchase_count, MAX(s.sale_date) AS last_purchase_date
        FROM sales s
        JOIN customers c ON s.customer_id = c.customer_id
        JOIN medicines m ON s.medicine_id = m.medicine_id
        WHERE s.user_id = ?
        GROUP BY c.contact_number, m.medicine_id
        HAVING COUNT(*) >= ?
        ORDER BY purchase_count DESC
    """, (user_id, min_purchase_count))
    reminders = cursor.fetchall()
    cursor.close()
    conn.close()
    return reminders
