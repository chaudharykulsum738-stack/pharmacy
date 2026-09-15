# Smart Pharmacy Inventory & Cabinet Recommendation System

An AI-powered pharmacy management system that predicts stock shortages,
flags near-expiry medicines, recommends cabinet storage, and suggests
substitute medicines when stock runs low.

## Features

0. **Multi-user login** - every pharmacy owner registers their own account. All data (medicines, sales, customers, cabinets) is private to that account - two people can use the app at the same time on different browsers/phones and never see each other's data
1. **Customer & purchase records** - stores customer name, contact, and what they bought
1b. **Usage description** - each medicine has a short "what it's for" note (e.g. "Fever and pain relief"), shown on the dashboard and set when adding a medicine
2. **ML shortage prediction** - Linear Regression model (scikit-learn) predicts demand for the next 7 days per medicine
3. **Expiry alerts** - scheduled task (APScheduler) runs daily, flags medicines expiring within 15 days
4. **Low stock alerts** - MySQL trigger fires instantly on every sale
5. **Cabinet recommendation** - rule-based engine assigns cabinets by usage frequency + remaining capacity, with capacity-full alerts
6. **Substitute medicine suggestion** - when a medicine is low on stock, suggests alternates with the same salt composition
7. **Sales trend dashboard** - Plotly charts for daily sales trend and top-selling medicines
8. **Installable as a PWA** - can be added to your phone's home screen like a real app (icon, standalone window, works without the browser address bar)
9. **Overall Medicine Review** - single-lookup search page showing everything about one medicine (active ingredient, dosage, stock, expiry, storage, prescription status) before dispensing
10. **Expired medicine tracking** - separate from "expiring soon"; already-expired medicines are flagged on their own for immediate removal
11. **Fast/Moderate/Slow-moving classification** - medicines tagged by how often they sell, based on usage frequency
12. **Refill reminders** - flags when the same customer has bought the same medicine 2+ times, for the pharmacist to verify (never assumes the customer needs it)
13. **Prescription verification** - medicines marked as requiring a prescription block the sale until a "verified" checkbox is ticked
14. **Unusual purchase detection** - flags a sale if the quantity is unusually high vs. that medicine's typical sale size, for pharmacist review only (never an accusation)
15. **Storage condition tracking** - each medicine records its required storage condition, shown as a warning note when it's not simple room temperature

## Mapping to the mentor's spec

| Spec feature | Where it lives in the app |
|---|---|
| 1. Medicine Records | `medicines` table + Add/Edit Medicine forms |
| 2. Overall Medicine Review | `/medicine_review` - search page |
| 3. Expiry Management | Dashboard - separate Expired and Expiring Soon banners |
| 4. Stock Monitoring | Dashboard stat cards + inventory table |
| 5. Restock Recommendation | `/shortage_prediction` - "Suggested Reorder" column |
| 6. Fast/Slow-moving | Dashboard stat cards, `analytics.py` |
| 7. Refill Reminder | Dashboard panel, `analytics.py` |
| 8. Alternative Medicine Suggestions | Dashboard (low stock) + Medicine Review page + `/manage_substitutes` |
| 9. Prescription Verification | Add Sale form - blocks submission until verified |
| 10. Unusual Purchase Detection | Dashboard panel, `analytics.py` |
| 11. Storage Condition | Medicine fields + dashboard warning note |

## Why a trigger AND a scheduled task (not just one)?

- **Low stock** is event-based - it only changes when a sale happens, so a MySQL **trigger** checks it instantly at that moment.
- **Expiry** is time-based, not event-based - a medicine can become "near expiry" with zero sales activity, just because a day passed. So it needs a **scheduled task** that runs independently of any transaction.

## Project Structure

```
pharmacy_project/
├── requirements.txt
├── data/
│   ├── medicines_master.csv   # THE medicine dataset (63 medicines, categories, usage, stock/expiry)
│   └── sales_history.csv      # THE sales dataset (1248 transactions) - what the ML model trains on
├── models/
│   └── shortage_models.pkl    # trained models (created by running train_model.py)
├── sql/
│   └── schema.sql             # tables (incl. users) + low-stock trigger
└── app/
    ├── app.py                  # Flask routes (main entry point)
    ├── db.py                   # MySQL connection helper
    ├── auth.py                 # registration, login, session, login_required decorator
    ├── create_demo_user.py     # one-time script to set the demo account's password
    ├── seed_data.py            # loads data/*.csv into the database for a given user
    ├── train_model.py          # visible ML training pipeline: load -> split -> train -> evaluate -> save
    ├── cabinet_engine.py       # cabinet recommendation logic (per-user)
    ├── ml_predict.py           # ML shortage prediction (per-user)
    ├── expiry_alert.py         # scheduled expiry check (per-user cache)
    ├── substitute_engine.py    # substitute medicine suggestion (per-user)
    ├── sales_trend.py          # Plotly chart builders (per-user)
    ├── static/
    │   ├── manifest.json
    │   ├── sw.js
    │   └── icons/
    └── templates/
        ├── login.html
        ├── register.html
        ├── dashboard.html
        ├── add_sale.html
        ├── add_medicine.html
        ├── edit_medicine.html
        ├── manage_substitutes.html
        ├── sales_trend.html
        └── shortage_prediction.html
```

## Setup

1. Install MySQL and create the database + tables:
   ```
   mysql -u root -p < sql/schema.sql
   ```

2. Install Python dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Update your MySQL credentials in `app/db.py` (host, user, password).

4. Set the demo account's password (schema.sql can't hash passwords by itself):
   ```
   cd app
   python create_demo_user.py
   ```

5. (Optional but recommended for demo/viva) Load the dataset so the ML
   shortage prediction actually has real data to work with:
   ```
   python seed_data.py demo@pharmacy.com
   ```
   This reads `data/medicines_master.csv` (63 medicines) and
   `data/sales_history.csv` (1,248 sales records) and loads them into
   your database - inserted through the real `sales` table so the
   low-stock trigger fires naturally and several medicines end up
   genuinely low on stock. Substitute pairs (same-salt groupings) are
   created automatically from the `group_id` column in the medicines CSV.

6. (Optional, for demonstrating the training pipeline itself) Train and
   evaluate the ML models directly from the dataset file:
   ```
   python train_model.py
   ```
   This prints an accuracy (MAE) table for all 63 medicines and saves
   the trained models to `models/shortage_models.pkl`. The live app
   doesn't depend on this file - it retrains fresh on live data per
   request - but this script is what demonstrates the actual training +
   evaluation process on the dataset.

7. Run the app:
   ```
   python app.py
   ```

7. Open `http://127.0.0.1:5000` - you'll land on the login page.
   - Log in with the demo account (`demo@pharmacy.com` / `demo1234`), or
   - Click "Register here" to create your own separate account.
   - Every account gets its own private set of medicines, cabinets, sales, and customers.

## Installing as a PWA (on your phone)

1. Deploy the app somewhere reachable from your phone - options for a college project:
   - Run it on your laptop and access it from your phone over the same Wi-Fi (`http://<your-laptop-IP>:5000`)
   - Or deploy free-tier to something like Render/Railway/PythonAnywhere so it has a proper URL
   - Note: browsers require HTTPS for full PWA install support (except `localhost`), so a real deployment with HTTPS is the more reliable path for demoing on a phone.
2. Open the URL in Chrome (Android) or Safari (iPhone).
3. Chrome: tap the "Install app" prompt or menu → "Add to Home Screen". Safari: Share button → "Add to Home Screen".
4. It'll now open as a standalone app with its own icon, no browser address bar.

The manifest (`app/static/manifest.json`), icons (`app/static/icons/`), and service worker
(`app/static/sw.js`) are already wired into every page. No extra Python packages needed for this part.

## Pages

| Route                  | Purpose                                      |
|-------------------------|-----------------------------------------------|
| `/`                     | Owner dashboard - inventory, expiry alerts, substitutes |
| `/add_sale`             | Record a new sale (triggers low-stock check)  |
| `/add_medicine`         | Add new medicine (auto cabinet assignment)    |
| `/sales_trend`          | Plotly charts - daily trend & top sellers     |
| `/shortage_prediction`  | ML-based 7-day shortage prediction            |

## Dataset & Training Methodology

This project has an actual dataset checked into the repo - see the
`data/` folder:

- **`data/medicines_master.csv`** - the medicine catalog: 63 medicines
  across 20 categories, with name, category, usage description, minimum
  stock level, expiry offset, and starting stock quantity. This is the
  master reference data.
- **`data/sales_history.csv`** - the transactional dataset: 1,248 sales
  records (medicine, customer, quantity sold, date), spanning the last
  30 days. **This is the dataset the ML model actually trains on.**
- **`data/external_kaggle_pharma_sales_monthly.csv`** - a REAL, publicly
  available dataset: ["Pharma Sales Data" by milanzdravkovic on
  Kaggle](https://www.kaggle.com/datasets/milanzdravkovic/pharma-sales-data),
  70 months (2014-2019) of real pharmacy sales across 8 drug categories
  (ATC codes). Used as a **reference benchmark** on both the Sales Trend
  page and the Shortage Prediction page
  - three of its categories (N02BE = Paracetamol family, R06 =
  Antihistamines, M01AE = Ibuprofen family) map directly onto categories
  in your own inventory, showing that real-world pharmacies see similar
  seasonal demand patterns for these drug types. This is NOT used to
  train the shortage prediction model (the ATC categories are too broad
  to map onto individual branded medicines like "Paracetamol 500mg")
  - it's shown for external validation/context, not as training input.

These are NOT a pre-downloaded external dataset (e.g. Kaggle) - they're
a **synthetic but realistic transactional dataset**, generated once with
a fixed random seed (so it's reproducible, not different every run) to
simulate what would organically accumulate as a real pharmacy uses the
system over time. `seed_data.py` reads both CSVs and loads them into
the database for a chosen user account.

**How training actually works:**
- **`train_model.py`** is the visible training pipeline your mentors will
  want to see. Run it with:
  ```
  cd app
  python train_model.py
  ```
  It does the standard ML workflow, step by step:
  1. **Loads** `data/sales_history.csv`
  2. **Splits** each medicine's sales history into training data (first
     80% of its recorded days) and testing data (last 20%)
  3. **Trains** a Linear Regression model on the training portion
  4. **Evaluates** it on the testing portion using Mean Absolute Error
     (MAE) - a real accuracy number, not just a claim
  5. **Saves** all 63 trained models to `models/shortage_models.pkl`

  On the current dataset, this produces **63 trained models with an
  average Test MAE of 1.72 units** - meaning the model's demand
  prediction is, on average, off by under 2 units per day on sales data
  it never saw during training.

- **The live app** (`ml_predict.py`) trains fresh per-request using each
  medicine's LIVE, up-to-date sales history from the database - this is
  intentional, not a shortcut: a model saved once from `train_model.py`
  would go stale as new real sales come in, so the live app always
  reflects the most current data. `train_model.py` exists specifically
  to make the training + evaluation process visible and measurable on
  its own, the way a standard ML pipeline is expected to look, using
  the actual dataset file.
- Once trained, the live prediction blends the Linear Regression trend
  with a recent 7-day moving average (60% trend / 40% average) so the
  prediction stays stable even with limited data.
- You can also download the live sales data (whatever's actually in
  the database at that moment) as CSV any time from the Shortage
  Prediction page.

## Notes for Viva/Report

- Cabinet recommendation logic first tries to match the medicine's usage
  frequency to a cabinet's priority tier, then checks if there's enough
  remaining capacity. If the ideal cabinet is full, it falls back to the
  cabinet with the most free space and raises an alert.
- ML prediction uses Linear Regression on each medicine's daily sales
  history to project demand for the next 7 days. If a medicine has fewer
  than 3 days of sales history, it's marked "insufficient data" rather
  than guessed.
- Substitute suggestions only show up when a medicine's `stock_status`
  is `Low Stock`, and only recommend substitutes that currently have
  stock themselves.
