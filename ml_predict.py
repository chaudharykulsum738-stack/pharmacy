import numpy as np
from sklearn.linear_model import LinearRegression
from db import get_connection


def get_sales_history(user_id, medicine_id):
    conn = get_connection()
    if not conn:
        return []

    cursor = conn.cursor()
    cursor.execute("""
        SELECT sale_date, SUM(quantity_sold) AS qty
        FROM sales
        WHERE medicine_id = ? AND user_id = ?
        GROUP BY sale_date
        ORDER BY sale_date ASC
    """, (medicine_id, user_id))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def predict_shortage(user_id, medicine_id, forecast_days=7, min_history_points=3):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT stock_quantity, min_stock_level, medicine_name FROM medicines WHERE medicine_id = ? AND user_id = ?",
        (medicine_id, user_id)
    )
    medicine = cursor.fetchone()
    cursor.close()
    conn.close()

    if not medicine:
        return None

    history = get_sales_history(user_id, medicine_id)

    if len(history) < min_history_points:
        return {
            "medicine_id": medicine_id,
            "medicine_name": medicine["medicine_name"],
            "method": "insufficient_data",
            "predicted_demand_next_7_days": None,
            "current_stock": medicine["stock_quantity"],
            "risk": "Unknown - not enough sales history yet"
        }

    X = np.array(range(len(history))).reshape(-1, 1)
    y = np.array([row["qty"] for row in history])

    model = LinearRegression()
    model.fit(X, y)

    future_days = np.array(range(len(history), len(history) + forecast_days)).reshape(-1, 1)
    daily_predictions = model.predict(future_days)
    daily_predictions = np.clip(daily_predictions, 0, None)
    regression_demand = float(np.sum(daily_predictions))

    recent_window = min(7, len(history))
    recent_avg_daily = float(np.mean([row["qty"] for row in history[-recent_window:]]))
    moving_avg_demand = recent_avg_daily * forecast_days

    predicted_demand = round(0.6 * regression_demand + 0.4 * moving_avg_demand, 1)

    projected_stock = medicine["stock_quantity"] - predicted_demand
    is_shortage_risk = projected_stock < medicine["min_stock_level"]

    reorder_quantity = None
    if is_shortage_risk:
        shortfall_below_min = medicine["min_stock_level"] - projected_stock
        reorder_quantity = int(np.ceil(shortfall_below_min + predicted_demand))

    return {
        "medicine_id": medicine_id,
        "medicine_name": medicine["medicine_name"],
        "method": "linear_regression_blended_with_moving_average",
        "predicted_demand_next_7_days": predicted_demand,
        "current_stock": medicine["stock_quantity"],
        "projected_stock": round(projected_stock, 1),
        "min_stock_level": medicine["min_stock_level"],
        "risk": "Predicted Shortage" if is_shortage_risk else "OK",
        "reorder_quantity": reorder_quantity
    }


def predict_all_medicines(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT medicine_id FROM medicines WHERE user_id = ?", (user_id,))
    ids = [row["medicine_id"] for row in cursor.fetchall()]
    cursor.close()
    conn.close()

    return [predict_shortage(user_id, mid) for mid in ids]


if __name__ == "__main__":
    results = predict_all_medicines(user_id=1)
    for r in results:
        print(r)
