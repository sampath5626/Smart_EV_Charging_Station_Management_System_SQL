# Smart EV Charging Station Management System with Data Quality Monitor

A full-stack data quality monitoring tool built on top of a 17-table MySQL EV charging database. After every data load, it compares the operational (source) database with a reporting database, runs automated data-quality checks, and shows the results on a web dashboard.

**Tech stack:** Python · Flask · MySQL · SQL · Pandas · openpyxl · Jinja2 · HTML5 · CSS3

---

## Problem Statement

EV charging operators copy booking, session and payment data from the live transactional database into a reporting database that feeds dashboards (energy delivered, revenue, slot utilization). If a load drops sessions, duplicates a booking, or stores a wrong payment amount, the reports show wrong numbers, and nobody notices until a business user questions them.

Checking this by hand across many tables is slow and error-prone.

## Solution

This project adds an automated monitoring layer to the existing EV charging database:

1. An **ETL script** loads data from the source database into a reporting database.
2. A **check engine** runs data-quality checks after each load and stores the results per run.
3. A **Flask dashboard** shows the latest run, per-dimension status, run history and the failing records.
4. A **defect injector** deliberately corrupts data so you can demonstrate that the checks catch real problems.

---

## Architecture

```
 Excel upload (.xlsx)
        |
        v
+---------------------------+   etl_load.py   +----------------------+
| Smart_EV_Charging_System  | --------------> |     ev_reporting     |
| (source, 17 tables)       |                 | (reporting + dq_*)   |
+---------------------------+                 +----------+-----------+
                                                         ^
                                      dq_checks.py       | results stored per run
                                                         |
                                            +------------+-----------+
                                            |  Flask + Jinja2 UI     |
                                            |  (HTML / CSS)          |
                                            +------------------------+
```

## Features

- Source-to-target reconciliation after each ETL load
- Data-quality checks grouped by dimension (completeness, uniqueness, validity, consistency, referential integrity, timeliness)
- Run history with pass/fail counts and status for every run
- Per-check results with bad record counts and sample failing rows
- **Run checks now**, **Download report** (Excel) and **Inject defects (demo)** buttons
- Excel upload of session data with row-level validation (invalid users, vehicles, chargers and statuses are rejected with the row number)
- Operational KPIs: stations, chargers, sessions and successful revenue

## Database Design

**Source database:** `Smart_EV_Charging_System` (17 tables)

| # | Table | Purpose |
|---|-------|---------|
| 1 | Roles | Customer, Operator, Admin |
| 2 | Users | All users |
| 3 | MembershipPlans | Subscription plans |
| 4 | UserMemberships | User subscriptions |
| 5 | EVVehicles | User vehicles |
| 6 | ChargingStations | Station details |
| 7 | Chargers | Chargers inside stations |
| 8 | Tariffs | Charging prices |
| 9 | Bookings | Slot bookings |
| 10 | ChargingSessions | Charging sessions |
| 11 | ChargingSessionStatus | Live session readings |
| 12 | Payments | Payment records |
| 13 | WalletTransactions | Wallet recharge and payments |
| 14 | Reviews | Station reviews |
| 15 | Maintenance | Charger maintenance |
| 16 | Notifications | User notifications |
| 17 | LoginHistory / AuditLogs | Login and audit trail |

**Reporting database:** `ev_reporting` holds the loaded reporting data plus the monitor's own tables:

- `dq_runs`: one row per monitoring run (run date, total checks, passed, failed, status)
- `dq_check_results`: one row per check per run (check name, dimension, table tested, result, bad record count, sample failing rows)

## Data Quality Checks

Checks are grouped into the following dimensions. *(Edit this table to match the checks implemented in `dq_checks.py`.)*

| Dimension | What is verified | Example |
|-----------|------------------|---------|
| Completeness | No records lost between source and target | Session count matches in both databases |
| Uniqueness | No duplicate records | No repeated session or booking IDs |
| Validity | Values are in valid ranges and formats | No negative energy or amounts; end time after start time |
| Consistency | Totals agree across source and target | Revenue and energy totals match |
| Referential integrity | Every foreign key points to an existing record | Session → booking, user, vehicle, charger |
| Timeliness | Data is current | Latest loaded record is within the expected window |

Total checks per run: **[N]**

## Project Structure

```
.
├── app.py                    # Flask routes and Excel upload handling
├── db.py                     # MySQL connection helper
├── setup_databases.py        # Creates databases and tables
├── etl_load.py               # Source -> reporting load
├── dq_checks.py              # Data-quality check engine
├── inject_defects.py         # Demo: introduces known defects
├── EV_Management_Project.sql # Source schema (17 tables)
├── EV_Management_Records.sql # Sample data
├── EV_Management_Queries.sql # Analytical SQL queries
├── README_ETL.md             # ETL details
├── requirements.txt
├── .env.example
├── templates/                # Jinja2 HTML pages
├── static/                   # CSS
└── demo_uploads/             # Sample Excel files for testing the upload
```

## Setup

**Prerequisites:** Python 3.10+, MySQL 8+

```bash
# 1. Clone the repository
git clone https://github.com/sampath5626/Smart_EV_Charging_Station_Management_System_SQL.git
cd Smart_EV_Charging_Station_Management_System_SQL

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure the database connection
cp .env.example .env        # then edit .env with your MySQL credentials

# 4. Create the databases and load the sample data
python setup_databases.py

# 5. Start the app
python app.py
```

Open `http://127.0.0.1:5000` in your browser.

## How to Use

1. Open the dashboard and review the KPI cards and the latest run.
2. Click **Run checks now** to execute the data-quality checks on the current data.
3. Click **Inject defects (demo)**, then **Run checks now** again, and watch the failing dimensions turn red.
4. Open **Run History** and select a run to see each check, its bad record count and sample failing rows.
5. Click **Download report** to export the latest run to Excel.

## Excel Upload Format

The upload accepts an `.xlsx` workbook (first sheet) with these columns:

`user_id, vehicle_id, charger_id, booking_start, booking_end, session_start, estimated_completion, session_end, energy_kwh, session_status, booking_status, payment_amount, payment_method, payment_status, transaction_date`

Rules enforced on upload:

- Every required column must be present and no required cell may be blank
- `vehicle_id` must belong to `user_id`, and `user_id` and `charger_id` must exist
- `session_status`: InProgress, Completed, Interrupted, Failed
- `booking_status`: Pending, Confirmed, Cancelled, Completed, NoShow
- `payment_method`: Wallet, Card, UPI, NetBanking, Cash
- `payment_status`: Pending, Success, Failed, Refunded
- If any row is invalid, the whole upload is rolled back and the row number is reported

After uploading, run the ETL and then the checks to see the new data in the results. Sample files are in `demo_uploads/`.

## Screenshots

| Overview (clean run) | Overview (after injecting defects) |
|---|---|
| *add screenshot* | *add screenshot* |

| Run history | Check details |
|---|---|
| *add screenshot* | *add screenshot* |

## Testing the Monitor

| Scenario | Expected result |
|----------|-----------------|
| Upload clean sample file, run ETL and checks | All checks pass |
| Upload sample file with defects, run ETL and checks | Failing checks are reported with bad record counts |
| Upload file with a missing column | Upload rejected: "Missing required columns" |
| Upload file with an unknown user or mismatched vehicle | Upload rejected with the row number |
| Upload file with an invalid status value | Upload rejected with the row number |
| Upload a non-.xlsx file | Upload rejected: "Only .xlsx workbooks are supported" |

Defects detected in testing: **[X] of [Y]**

## Future Improvements

- Incremental ETL loads instead of full reloads
- Scheduled runs (for example with cron) and email alerts on failed runs
- Trend chart of pass rate across runs
- Automated API and UI test suite (pytest, Postman, Playwright) with a GitHub Actions pipeline
- Additional business-rule checks (billing amount versus tariff, overlapping bookings)

## Author

**Pedapati Sampath Rama Krishna**
B.Tech, Artificial Intelligence & Data Science
[GitHub](https://github.com/sampath5626) · [LinkedIn](https://linkedin.com/in/sampath5626)
