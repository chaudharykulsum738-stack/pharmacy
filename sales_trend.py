import plotly.graph_objs as go
import plotly.offline as pyo
from db import get_connection


def get_daily_sales_trend(user_id):
    conn = get_connection()
    if not conn:
        return None

    cursor = conn.cursor()
    cursor.execute("""
        SELECT sale_date, SUM(quantity_sold) AS total_qty
        FROM sales
        WHERE user_id = ? AND sale_date >= DATE('now', '-30 days')
        GROUP BY sale_date
        ORDER BY sale_date ASC
    """, (user_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def get_top_selling_medicines(user_id, limit=5):
    conn = get_connection()
    if not conn:
        return None

    cursor = conn.cursor()
    cursor.execute("""
        SELECT m.medicine_name, SUM(s.quantity_sold) AS total_sold
        FROM sales s
        JOIN medicines m ON s.medicine_id = m.medicine_id
        WHERE s.user_id = ?
        GROUP BY m.medicine_name
        ORDER BY total_sold DESC
        LIMIT ?
    """, (user_id, limit))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def build_daily_trend_chart(user_id):
    data = get_daily_sales_trend(user_id)
    if not data:
        return "<p>No sales data available yet.</p>"

    dates = [str(row["sale_date"]) for row in data]
    quantities = [row["total_qty"] for row in data]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates,
        y=quantities,
        mode="lines+markers",
        name="Units Sold",
        line=dict(color="#2c3e50", width=2)
    ))
    fig.update_layout(
        title="Daily Sales Trend (Last 30 Days)",
        xaxis_title="Date",
        yaxis_title="Units Sold",
        template="plotly_white",
        height=400
    )

    return pyo.plot(fig, output_type="div", include_plotlyjs=False)


def build_top_medicines_chart(user_id):
    data = get_top_selling_medicines(user_id)
    if not data:
        return "<p>No sales data available yet.</p>"

    names = [row["medicine_name"] for row in data]
    totals = [row["total_sold"] for row in data]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=names,
        y=totals,
        marker_color="#27ae60"
    ))
    fig.update_layout(
        title="Top Selling Medicines",
        xaxis_title="Medicine",
        yaxis_title="Units Sold",
        template="plotly_white",
        height=400
    )

    return pyo.plot(fig, output_type="div", include_plotlyjs=False)


def build_market_benchmark_chart():
    import csv
    import os

    path = os.path.join(os.path.dirname(__file__), "..", "data", "external_kaggle_pharma_sales_monthly.csv")
    if not os.path.exists(path):
        return "<p>Real-world benchmark dataset not found.</p>"

    months = []
    paracetamol_family = []
    antihistamines = []
    nsaid_family = []

    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            months.append(row["datum"][:7])
            paracetamol_family.append(float(row["N02BE"]))
            antihistamines.append(float(row["R06"]))
            nsaid_family.append(float(row["M01AE"]))

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=months, y=paracetamol_family, mode="lines", name="Paracetamol family (N02BE)", line=dict(color="#2c3e50")))
    fig.add_trace(go.Scatter(x=months, y=antihistamines, mode="lines", name="Antihistamines (R06)", line=dict(color="#27ae60")))
    fig.add_trace(go.Scatter(x=months, y=nsaid_family, mode="lines", name="NSAIDs - Ibuprofen family (M01AE)", line=dict(color="#c0392b")))

    fig.update_layout(
        title="Real-World Market Benchmark - Monthly Sales by Drug Category (2014-2019)",
        xaxis_title="Month",
        yaxis_title="Units Sold (real pharmacy data)",
        template="plotly_white",
        height=420,
        legend=dict(orientation="h", yanchor="bottom", y=1.02)
    )

    return pyo.plot(fig, output_type="div", include_plotlyjs=False)
