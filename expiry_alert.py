from datetime import date, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from db import get_connection

expiring_soon_cache = {}
expired_cache = {}


def check_expiring_medicines(days_threshold=15):
    global expiring_soon_cache, expired_cache

    conn = get_connection()
    if not conn:
        print("Expiry check skipped - DB connection failed.")
        return

    cursor = conn.cursor()
    cutoff_date = date.today() + timedelta(days=days_threshold)
    today_str = date.today().isoformat()
    cutoff_str = cutoff_date.isoformat()

    cursor.execute("""
        SELECT user_id, medicine_id, medicine_name, expiry_date, stock_quantity
        FROM medicines
        WHERE expiry_date <= ? AND expiry_date >= ?
        ORDER BY expiry_date ASC
    """, (cutoff_str, today_str))
    soon_rows = cursor.fetchall()

    cursor.execute("""
        SELECT user_id, medicine_id, medicine_name, expiry_date, stock_quantity
        FROM medicines
        WHERE expiry_date < ?
        ORDER BY expiry_date ASC
    """, (today_str,))
    expired_rows = cursor.fetchall()

    cursor.close()
    conn.close()

    new_soon_cache = {}
    for row in soon_rows:
        new_soon_cache.setdefault(row["user_id"], []).append(row)

    new_expired_cache = {}
    for row in expired_rows:
        new_expired_cache.setdefault(row["user_id"], []).append(row)

    expiring_soon_cache = new_soon_cache
    expired_cache = new_expired_cache
    print(f"Expiry check complete. {len(soon_rows)} expiring soon, {len(expired_rows)} already expired, across all users.")


def get_expiring_medicines(user_id):
    return expiring_soon_cache.get(user_id, [])


def get_expired_medicines(user_id):
    return expired_cache.get(user_id, [])


def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_expiring_medicines, "interval", days=1, id="expiry_check_job")
    scheduler.start()

    check_expiring_medicines()

    return scheduler


if __name__ == "__main__":
    check_expiring_medicines()
    print("Expiring soon:", expiring_soon_cache)
    print("Expired:", expired_cache)
