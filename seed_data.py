import sys
import csv
import os
from collections import defaultdict
from datetime import date, timedelta
from db import get_connection

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MEDICINES_CSV = os.path.join(DATA_DIR, "medicines_master.csv")
SALES_CSV = os.path.join(DATA_DIR, "sales_history.csv")


def load_medicines_dataset():
    groups = defaultdict(list)
    with open(MEDICINES_CSV, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            groups[row["group_id"]].append(row)
    return groups


def load_sales_dataset():
    with open(SALES_CSV, newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


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


def seed_for_user(email):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT user_id FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    if not user:
        print(f"No user found with email {email}. Register that account first (or run create_demo_user.py).")
        return
    user_id = user["user_id"]

    cursor.execute("SELECT cabinet_id, priority_level FROM cabinets WHERE user_id = ?", (user_id,))
    cabinets = cursor.fetchall()
    cabinets_by_priority = {c["priority_level"]: c["cabinet_id"] for c in cabinets}

    today = date.today()
    medicine_groups = load_medicines_dataset()

    medicine_id_by_name = {}
    medicine_ids_by_group = []

    for group_id, meds in medicine_groups.items():
        group_ids = []
        for med in meds:
            expiry_date = today + timedelta(days=int(med["expiry_days_from_today"]))
            cabinet_id = cabinets_by_priority.get("Medium") or cabinets[0]["cabinet_id"]

            cursor.execute("""
                INSERT INTO medicines
                (user_id, medicine_name, category, usage_description, active_ingredient, dosage_strength,
                 storage_condition, prescription_required, stock_quantity, min_stock_level, expiry_date, cabinet_id, usage_frequency)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                user_id, med["medicine_name"], med["category"], med["usage_description"],
                med["active_ingredient"], med["dosage_strength"], med["storage_condition"], med["prescription_required"],
                int(med["start_stock_quantity"]), int(med["min_stock_level"]), expiry_date.isoformat(), cabinet_id
            ))

            new_id = cursor.lastrowid
            medicine_id_by_name[med["medicine_name"]] = new_id
            group_ids.append(new_id)

        medicine_ids_by_group.append(group_ids)

    conn.commit()

    for group_ids in medicine_ids_by_group:
        for med_id in group_ids:
            for other_id in group_ids:
                if med_id != other_id:
                    cursor.execute(
                        "INSERT OR IGNORE INTO substitutes (user_id, medicine_id, substitute_medicine_id) VALUES (?, ?, ?)",
                        (user_id, med_id, other_id)
                    )
    conn.commit()

    sales_rows = load_sales_dataset()
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
    cursor.close()
    conn.close()

    print(f"Loaded from dataset files: {len(medicine_id_by_name)} medicines, {len(customer_id_by_contact)} customers, {total_sales_inserted} sales records for {email}.")
    if skipped:
        print(f"Skipped {skipped} sales rows - medicine name not found in medicines_master.csv (dataset mismatch).")


if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else "demo@pharmacy.com"
    seed_for_user(email)
