import os
import sys
import csv
from collections import defaultdict
from datetime import date, timedelta
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(__file__))
from db import DB_PATH


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cabinets (
    cabinet_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INT NOT NULL,
    cabinet_name VARCHAR(50) NOT NULL,
    priority_level VARCHAR(20) NOT NULL,
    capacity INT DEFAULT 100,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS medicines (
    medicine_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INT NOT NULL,
    medicine_name VARCHAR(100) NOT NULL,
    category VARCHAR(50),
    usage_description VARCHAR(255),
    active_ingredient VARCHAR(100),
    dosage_strength VARCHAR(50),
    storage_condition VARCHAR(100) DEFAULT 'Room temperature',
    prescription_required VARCHAR(3) DEFAULT 'No',
    stock_quantity INT NOT NULL DEFAULT 0,
    min_stock_level INT NOT NULL DEFAULT 10,
    expiry_date DATE NOT NULL,
    cabinet_id INT,
    usage_frequency INT DEFAULT 0,
    stock_status VARCHAR(20) DEFAULT 'OK',
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (cabinet_id) REFERENCES cabinets(cabinet_id)
);

CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    contact_number VARCHAR(15) NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS sales (
    sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INT NOT NULL,
    customer_id INT NOT NULL,
    medicine_id INT NOT NULL,
    quantity_sold INT NOT NULL,
    sale_date DATE NOT NULL DEFAULT (DATE('now')),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (medicine_id) REFERENCES medicines(medicine_id)
);

CREATE TABLE IF NOT EXISTS substitutes (
    substitute_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INT NOT NULL,
    medicine_id INT NOT NULL,
    substitute_medicine_id INT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (medicine_id) REFERENCES medicines(medicine_id),
    FOREIGN KEY (substitute_medicine_id) REFERENCES medicines(medicine_id),
    UNIQUE(user_id, medicine_id, substitute_medicine_id)
);
"""


def update_stock_after_sale(conn, medicine_id, quantity_sold):
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE medicines
        SET stock_quantity = stock_quantity - ?,
            usage_frequency = usage_frequency + ?
        WHERE medicine_id = ?
    """, (quantity_sold, quantity_sold, medicine_id))
    cursor.execute("""
        UPDATE medicines
        SET stock_status = CASE
            WHEN stock_quantity <= min_stock_level THEN 'Low Stock'
            ELSE 'OK'
        END
        WHERE medicine_id = ?
    """, (medicine_id,))


def init_database():
    import sqlite3

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    if os.path.exists(DB_PATH):
        print(f"Removing existing database at {DB_PATH}")
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = lambda cursor, row: {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    print("Database schema created.")

    DEMO_EMAIL = "demo@pharmacy.com"
    DEMO_PASSWORD = "demo1234"
    DEMO_NAME = "Demo Owner"

    cursor = conn.cursor()
    password_hash = generate_password_hash(DEMO_PASSWORD)
    cursor.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (DEMO_NAME, DEMO_EMAIL, password_hash)
    )
    user_id = cursor.lastrowid
    print(f"Demo user created: id={user_id}, email={DEMO_EMAIL}")

    cursor.execute("""
        INSERT INTO cabinets (user_id, cabinet_name, priority_level, capacity) VALUES
        (?, 'Cabinet A - Front Counter', 'High', 50),
        (?, 'Cabinet B - Mid Shelf', 'Medium', 100),
        (?, 'Cabinet C - Back Storage', 'Low', 200)
    """, (user_id, user_id, user_id))
    conn.commit()
    print("Default cabinets created.")

    cursor.execute("SELECT cabinet_id, priority_level FROM cabinets WHERE user_id = ?", (user_id,))
    cabinets = cursor.fetchall()
    cabinets_by_priority = {}
    for c in cabinets:
        cabinets_by_priority[c["priority_level"]] = c["cabinet_id"]

    DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
    MEDICINES_CSV = os.path.join(DATA_DIR, "medicines_master.csv")
    SALES_CSV = os.path.join(DATA_DIR, "sales_history.csv")

    medicine_groups = defaultdict(list)
    with open(MEDICINES_CSV, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            medicine_groups[row["group_id"]].append(row)

    today = date.today()
    medicine_id_by_name = {}
    medicine_ids_by_group = []

    for group_id, meds in medicine_groups.items():
        group_ids = []
        for med in meds:
            expiry_date = today + timedelta(days=int(med["expiry_days_from_today"]))
            cabinet_id = cabinets_by_priority.get("Medium") or cabinets[0]["cabinet_id"]
            stock_qty = int(med["start_stock_quantity"])
            min_stock = int(med["min_stock_level"])
            stock_status = "Low Stock" if stock_qty <= min_stock else "OK"

            cursor.execute("""
                INSERT INTO medicines
                (user_id, medicine_name, category, usage_description, active_ingredient, dosage_strength,
                 storage_condition, prescription_required, stock_quantity, min_stock_level, expiry_date, cabinet_id, usage_frequency, stock_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """, (
                user_id, med["medicine_name"], med["category"], med["usage_description"],
                med["active_ingredient"], med["dosage_strength"], med["storage_condition"], med["prescription_required"],
                stock_qty, min_stock, expiry_date.isoformat(), cabinet_id, stock_status
            ))

            new_id = cursor.lastrowid
            medicine_id_by_name[med["medicine_name"]] = new_id
            group_ids.append(new_id)

        medicine_ids_by_group.append(group_ids)

    conn.commit()
    print(f"{len(medicine_id_by_name)} medicines loaded.")

    for group_ids in medicine_ids_by_group:
        for med_id in group_ids:
            for other_id in group_ids:
                if med_id != other_id:
                    cursor.execute(
                        "INSERT OR IGNORE INTO substitutes (user_id, medicine_id, substitute_medicine_id) VALUES (?, ?, ?)",
                        (user_id, med_id, other_id)
                    )
    conn.commit()
    print("Substitute links created.")

    with open(SALES_CSV, newline="") as f:
        reader = csv.DictReader(f)
        sales_rows = list(reader)

    customer_id_by_contact = {}
    total_sales_inserted = 0
    skipped = 0

    for row in sales_rows:
        contact = row["contact_number"]
        if contact not in customer_id_by_contact:
            cursor.execute(
                "INSERT INTO customers (user_id, name, contact_number) VALUES (?, ?, ?)",
                (user_id, row["customer_name"], contact)
            )
            customer_id_by_contact[contact] = cursor.lastrowid
        customer_id = customer_id_by_contact[contact]

        medicine_id = medicine_id_by_name.get(row["medicine_name"])
        if not medicine_id:
            skipped += 1
            continue

        cursor.execute(
            "INSERT INTO sales (user_id, customer_id, medicine_id, quantity_sold, sale_date) VALUES (?, ?, ?, ?, ?)",
            (user_id, customer_id, medicine_id, int(row["quantity_sold"]), row["sale_date"])
        )
        update_stock_after_sale(conn, medicine_id, int(row["quantity_sold"]))
        total_sales_inserted += 1

    conn.commit()
    print(f"{len(customer_id_by_contact)} customers, {total_sales_inserted} sales records loaded.")
    if skipped:
        print(f"Skipped {skipped} sales rows (medicine name mismatch).")

    cursor.close()
    conn.close()
    print(f"\nDatabase initialized successfully: {DB_PATH}")
    print(f"Demo login: email='{DEMO_EMAIL}', password='{DEMO_PASSWORD}'")


if __name__ == "__main__":
    init_database()
