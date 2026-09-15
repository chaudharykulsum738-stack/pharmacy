import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "pharmacy.db")
print(f"DB Path: {db_path}")
print(f"DB Exists: {os.path.exists(db_path)}")
if os.path.exists(db_path):
    print(f"DB Size: {os.path.getsize(db_path)} bytes")

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()

tables = ['users', 'cabinets', 'medicines', 'customers', 'sales', 'substitutes']
for t in tables:
    cnt = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"{t}: {cnt} rows")

print("\n--- Users ---")
for r in c.execute("SELECT user_id, email, name FROM users").fetchall():
    print(f"  id={r['user_id']}, email={r['email']}, name={r['name']}")

print("\n--- Sample Medicines (first 5) ---")
for r in c.execute("SELECT medicine_id, medicine_name, stock_quantity, stock_status FROM medicines LIMIT 5").fetchall():
    print(f"  [{r['medicine_id']}] {r['medicine_name']}: stock={r['stock_quantity']}, status={r['stock_status']}")

print("\n--- Sample Sales (first 5) ---")
for r in c.execute("SELECT sale_id, medicine_id, quantity_sold, sale_date FROM sales LIMIT 5").fetchall():
    print(f"  sale_id={r['sale_id']}, med_id={r['medicine_id']}, qty={r['quantity_sold']}, date={r['sale_date']}")

conn.close()
