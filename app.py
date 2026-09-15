import secrets
from datetime import date
from flask import Flask, render_template, request, redirect, url_for, session
from db import get_connection
from cabinet_engine import recommend_cabinet
from sales_trend import build_daily_trend_chart, build_top_medicines_chart, build_market_benchmark_chart
from ml_predict import predict_all_medicines
from expiry_alert import start_scheduler, get_expiring_medicines, get_expired_medicines
from substitute_engine import suggest_substitute_if_low, get_substitutes
from auth import register_user, authenticate_user, login_required, current_user_id
from analytics import classify_medicine_movement, detect_unusual_purchases, get_refill_reminders

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

scheduler = start_scheduler()


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


@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    success = None

    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        ok, message = register_user(name, email, password)
        if ok:
            success = message
        else:
            error = message

    return render_template("register.html", error=error, success=success)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        ok, result = authenticate_user(email, password)
        if ok:
            session["user_id"] = result["user_id"]
            session["user_name"] = result["name"]
            return redirect(url_for("dashboard"))
        else:
            error = result

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    user_id = current_user_id()
    conn = get_connection()
    medicines = []
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM medicines WHERE user_id = ?", (user_id,))
        medicines = cursor.fetchall()
        cursor.close()
        conn.close()

    for med in medicines:
        if med["stock_status"] == "Low Stock":
            med["substitutes"] = suggest_substitute_if_low(user_id, med["medicine_id"])
        else:
            med["substitutes"] = []

    expiring_soon = get_expiring_medicines(user_id)
    expired = get_expired_medicines(user_id)
    movement = classify_medicine_movement(user_id)
    fast_moving = [m for m in movement if m["movement"] == "Fast-moving"]
    slow_moving = [m for m in movement if m["movement"] == "Slow-moving"]
    unusual_purchases = detect_unusual_purchases(user_id)
    refill_reminders = get_refill_reminders(user_id)

    return render_template(
        "dashboard.html",
        medicines=medicines,
        expiring_soon=expiring_soon,
        expired=expired,
        fast_moving=fast_moving,
        slow_moving=slow_moving,
        unusual_purchases=unusual_purchases,
        refill_reminders=refill_reminders,
        user_name=session.get("user_name"),
        error=request.args.get("error")
    )


@app.route("/add_sale", methods=["GET", "POST"])
@login_required
def add_sale():
    user_id = current_user_id()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT medicine_id, medicine_name, stock_quantity FROM medicines WHERE user_id = ?",
        (user_id,)
    )
    medicines = cursor.fetchall()

    message = None
    success = False
    last_sale_id = None

    if request.method == "POST":
        customer_name = request.form["customer_name"]
        contact_number = request.form["contact_number"]
        typed_medicine_name = request.form["medicine_name"].strip()
        quantity = int(request.form["quantity"])

        cursor.execute(
            "SELECT medicine_id, stock_quantity, prescription_required, medicine_name FROM medicines WHERE user_id = ? AND LOWER(medicine_name) = LOWER(?)",
            (user_id, typed_medicine_name)
        )
        matched_medicine = cursor.fetchone()

        if not matched_medicine:
            message = f'"{typed_medicine_name}" isn\'t in your inventory yet. Check the spelling, or add it first via "Add Medicine" if it\'s new.'
            success = False
        elif matched_medicine["prescription_required"] == "Yes" and not request.form.get("prescription_verified"):
            message = f'Prescription verification required before dispensing {matched_medicine["medicine_name"]}. Check the box once verified, then resubmit.'
            success = False
        else:
            medicine_id = matched_medicine["medicine_id"]

            cursor.execute(
                "INSERT INTO customers (user_id, name, contact_number) VALUES (?, ?, ?)",
                (user_id, customer_name, contact_number)
            )
            customer_id = cursor.lastrowid

            cursor.execute(
                "INSERT INTO sales (user_id, customer_id, medicine_id, quantity_sold) VALUES (?, ?, ?, ?)",
                (user_id, customer_id, medicine_id, quantity)
            )
            last_sale_id = cursor.lastrowid

            update_stock_after_sale(conn, medicine_id, quantity)

            conn.commit()

            message = "Sale recorded successfully."
            success = True

            cursor.execute(
                "SELECT medicine_id, medicine_name, stock_quantity FROM medicines WHERE user_id = ?",
                (user_id,)
            )
            medicines = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("add_sale.html", medicines=medicines, message=message, success=success, last_sale_id=last_sale_id)


@app.route("/add_medicine", methods=["GET", "POST"])
@login_required
def add_medicine():
    user_id = current_user_id()
    message = None
    success = False
    cabinet_result = None

    if request.method == "POST":
        conn = get_connection()
        cursor = conn.cursor()

        name = request.form["medicine_name"]
        category = request.form.get("category", "")
        usage_description = request.form.get("usage_description", "")
        active_ingredient = request.form.get("active_ingredient", "")
        dosage_strength = request.form.get("dosage_strength", "")
        storage_condition = request.form.get("storage_condition", "Room temperature")
        prescription_required = request.form.get("prescription_required", "No")
        stock_quantity = int(request.form["stock_quantity"])
        min_stock_level = int(request.form["min_stock_level"])
        expiry_date = request.form["expiry_date"]

        cabinet_result = recommend_cabinet(user_id, usage_frequency=0, stock_quantity=stock_quantity)

        stock_status = "Low Stock" if stock_quantity <= min_stock_level else "OK"

        cursor.execute("""
            INSERT INTO medicines
            (user_id, medicine_name, category, usage_description, active_ingredient, dosage_strength,
             storage_condition, prescription_required, stock_quantity, min_stock_level, expiry_date, cabinet_id, usage_frequency, stock_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
        """, (user_id, name, category, usage_description, active_ingredient, dosage_strength,
              storage_condition, prescription_required, stock_quantity, min_stock_level, expiry_date, cabinet_result["cabinet_id"], stock_status))
        conn.commit()

        cursor.close()
        conn.close()

        message = f"Medicine added and assigned to {cabinet_result['cabinet_name']}."
        success = True

    return render_template("add_medicine.html", message=message, success=success, cabinet_result=cabinet_result)


@app.route("/edit_medicine/<int:medicine_id>", methods=["GET", "POST"])
@login_required
def edit_medicine(medicine_id):
    user_id = current_user_id()
    conn = get_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        name = request.form["medicine_name"]
        category = request.form.get("category", "")
        usage_description = request.form.get("usage_description", "")
        active_ingredient = request.form.get("active_ingredient", "")
        dosage_strength = request.form.get("dosage_strength", "")
        storage_condition = request.form.get("storage_condition", "Room temperature")
        prescription_required = request.form.get("prescription_required", "No")
        stock_quantity = int(request.form["stock_quantity"])
        min_stock_level = int(request.form["min_stock_level"])
        expiry_date = request.form["expiry_date"]

        stock_status = "Low Stock" if stock_quantity <= min_stock_level else "OK"

        cursor.execute("""
            UPDATE medicines
            SET medicine_name = ?, category = ?, usage_description = ?,
                active_ingredient = ?, dosage_strength = ?, storage_condition = ?,
                prescription_required = ?, stock_quantity = ?, min_stock_level = ?,
                expiry_date = ?, stock_status = ?
            WHERE medicine_id = ? AND user_id = ?
        """, (name, category, usage_description, active_ingredient, dosage_strength, storage_condition,
              prescription_required, stock_quantity, min_stock_level, expiry_date, stock_status, medicine_id, user_id))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for("dashboard"))

    cursor.execute(
        "SELECT * FROM medicines WHERE medicine_id = ? AND user_id = ?",
        (medicine_id, user_id)
    )
    medicine = cursor.fetchone()
    cursor.close()
    conn.close()

    if not medicine:
        return redirect(url_for("dashboard"))

    return render_template("edit_medicine.html", medicine=medicine)


@app.route("/delete_medicine/<int:medicine_id>", methods=["POST"])
@login_required
def delete_medicine(medicine_id):
    user_id = current_user_id()
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT medicine_id FROM medicines WHERE medicine_id = ? AND user_id = ?",
        (medicine_id, user_id)
    )
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return redirect(url_for("dashboard"))

    cursor.execute("SELECT COUNT(*) AS cnt FROM sales WHERE medicine_id = ?", (medicine_id,))
    has_sales = cursor.fetchone()["cnt"] > 0

    if has_sales:
        cursor.close()
        conn.close()
        return redirect(url_for("dashboard", error="Can't delete - this medicine has sales history. Edit it instead, or set stock to 0."))

    cursor.execute(
        "DELETE FROM substitutes WHERE medicine_id = ? OR substitute_medicine_id = ?",
        (medicine_id, medicine_id)
    )
    cursor.execute(
        "DELETE FROM medicines WHERE medicine_id = ? AND user_id = ?",
        (medicine_id, user_id)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for("dashboard"))


@app.route("/receipt/<int:sale_id>")
@login_required
def receipt(sale_id):
    user_id = current_user_id()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.sale_id, s.quantity_sold, s.sale_date, m.medicine_name, m.dosage_strength,
               c.name AS customer_name, c.contact_number
        FROM sales s
        JOIN medicines m ON s.medicine_id = m.medicine_id
        JOIN customers c ON s.customer_id = c.customer_id
        WHERE s.sale_id = ? AND s.user_id = ?
    """, (sale_id, user_id))
    sale = cursor.fetchone()
    cursor.close()
    conn.close()

    if not sale:
        return redirect(url_for("dashboard"))

    return render_template("receipt.html", sale=sale, pharmacy_name=session.get("user_name"))


@app.route("/medicine_review")
@login_required
def medicine_review():
    user_id = current_user_id()
    query = request.args.get("q", "").strip()
    result = None
    substitutes = []

    if query:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM medicines WHERE user_id = ? AND medicine_name LIKE ? LIMIT 1",
            (user_id, f"%{query}%")
        )
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result:
            substitutes = get_substitutes(user_id, result["medicine_id"])

    return render_template("medicine_review.html", query=query, result=result, substitutes=substitutes, today=date.today())


@app.route("/manage_substitutes", methods=["GET", "POST"])
@login_required
def manage_substitutes():
    user_id = current_user_id()
    conn = get_connection()
    cursor = conn.cursor()

    message = None
    success = False

    if request.method == "POST":
        medicine_id = int(request.form["medicine_id"])
        substitute_id = int(request.form["substitute_id"])

        if medicine_id == substitute_id:
            message = "A medicine can't be its own substitute."
            success = False
        else:
            cursor.execute(
                "SELECT medicine_id FROM medicines WHERE medicine_id IN (?, ?) AND user_id = ?",
                (medicine_id, substitute_id, user_id)
            )
            valid_count = len(cursor.fetchall())

            if valid_count != 2:
                message = "Both medicines must belong to your account."
                success = False
            else:
                cursor.execute(
                    "INSERT OR IGNORE INTO substitutes (user_id, medicine_id, substitute_medicine_id) VALUES (?, ?, ?)",
                    (user_id, medicine_id, substitute_id)
                )
                cursor.execute(
                    "INSERT OR IGNORE INTO substitutes (user_id, medicine_id, substitute_medicine_id) VALUES (?, ?, ?)",
                    (user_id, substitute_id, medicine_id)
                )
                conn.commit()
                message = "Substitute link added."
                success = True

    cursor.execute(
        "SELECT medicine_id, medicine_name FROM medicines WHERE user_id = ? ORDER BY medicine_name",
        (user_id,)
    )
    all_medicines = cursor.fetchall()

    cursor.execute("""
        SELECT s.substitute_id, m1.medicine_name AS medicine_name, m2.medicine_name AS substitute_name,
               m1.medicine_id AS medicine_id, m2.medicine_id AS substitute_medicine_id
        FROM substitutes s
        JOIN medicines m1 ON s.medicine_id = m1.medicine_id
        JOIN medicines m2 ON s.substitute_medicine_id = m2.medicine_id
        WHERE s.user_id = ?
        ORDER BY m1.medicine_name
    """, (user_id,))
    existing_links = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "manage_substitutes.html",
        all_medicines=all_medicines,
        existing_links=existing_links,
        message=message,
        success=success
    )


@app.route("/remove_substitute/<int:substitute_id>", methods=["POST"])
@login_required
def remove_substitute(substitute_id):
    user_id = current_user_id()
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT medicine_id, substitute_medicine_id FROM substitutes WHERE substitute_id = ? AND user_id = ?",
        (substitute_id, user_id)
    )
    link = cursor.fetchone()

    if link:
        cursor.execute(
            "DELETE FROM substitutes WHERE user_id = ? AND ((medicine_id = ? AND substitute_medicine_id = ?) OR (medicine_id = ? AND substitute_medicine_id = ?))",
            (user_id, link["medicine_id"], link["substitute_medicine_id"], link["substitute_medicine_id"], link["medicine_id"])
        )
        conn.commit()

    cursor.close()
    conn.close()
    return redirect(url_for("manage_substitutes"))


@app.route("/export_inventory_report")
@login_required
def export_inventory_report():
    import csv
    import io

    user_id = current_user_id()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT medicine_name, category, active_ingredient, dosage_strength, usage_description,
               storage_condition, prescription_required, stock_quantity, min_stock_level,
               stock_status, expiry_date, cabinet_id, usage_frequency
        FROM medicines
        WHERE user_id = ?
        ORDER BY medicine_name
    """, (user_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    output = io.StringIO()
    fieldnames = ["medicine_name", "category", "active_ingredient", "dosage_strength", "usage_description",
                  "storage_condition", "prescription_required", "stock_quantity", "min_stock_level",
                  "stock_status", "expiry_date", "cabinet_id", "usage_frequency"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

    from flask import Response
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=inventory_report.csv"}
    )


@app.route("/export_sales_dataset")
@login_required
def export_sales_dataset():
    import csv
    import io

    user_id = current_user_id()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.sale_id, m.medicine_name, m.category, s.quantity_sold, s.sale_date,
               c.name AS customer_name, c.contact_number
        FROM sales s
        JOIN medicines m ON s.medicine_id = m.medicine_id
        JOIN customers c ON s.customer_id = c.customer_id
        WHERE s.user_id = ?
        ORDER BY s.sale_date ASC
    """, (user_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        "sale_id", "medicine_name", "category", "quantity_sold",
        "sale_date", "customer_name", "contact_number"
    ])
    writer.writeheader()
    writer.writerows(rows)

    from flask import Response
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=sales_dataset.csv"}
    )


@app.route("/suggest_cabinet/<int:medicine_id>")
@login_required
def suggest_cabinet(medicine_id):
    user_id = current_user_id()
    conn = get_connection()
    if not conn:
        return {"error": "DB connection failed"}, 500

    cursor = conn.cursor()
    cursor.execute(
        "SELECT usage_frequency, stock_quantity FROM medicines WHERE medicine_id = ? AND user_id = ?",
        (medicine_id, user_id)
    )
    med = cursor.fetchone()
    cursor.close()
    conn.close()

    if not med:
        return {"error": "Medicine not found"}, 404

    result = recommend_cabinet(user_id, med["usage_frequency"], med["stock_quantity"])
    return result


@app.route("/sales_trend")
@login_required
def sales_trend():
    user_id = current_user_id()
    daily_chart = build_daily_trend_chart(user_id)
    top_chart = build_top_medicines_chart(user_id)
    benchmark_chart = build_market_benchmark_chart()
    return render_template("sales_trend.html", daily_chart=daily_chart, top_chart=top_chart, benchmark_chart=benchmark_chart)


@app.route("/shortage_prediction")
@login_required
def shortage_prediction():
    user_id = current_user_id()
    predictions = predict_all_medicines(user_id)
    benchmark_chart = build_market_benchmark_chart()
    return render_template("shortage_prediction.html", predictions=predictions, benchmark_chart=benchmark_chart)


if __name__ == "__main__":
    app.run(debug=True)
