import io
import json
import os

from flask import Flask, flash, redirect, render_template, request, send_file, url_for
from openpyxl import Workbook, load_workbook

from db import get_db
from dq_checks import run_checks
from inject_defects import inject_defects


app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "ev-data-quality-demo")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024


def fetch_all(database, sql, params=None):
    connection = get_db(database)
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(sql, params or ())
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def fetch_one(database, sql, params=None):
    rows = fetch_all(database, sql, params)
    return rows[0] if rows else None


@app.route("/")
def overview():
    latest = fetch_one(
        "ev_reporting",
        """
        SELECT * FROM dq_runs
        ORDER BY RunDate DESC, RunID DESC
        LIMIT 1
        """,
    )
    dimensions = []
    if latest:
        dimensions = fetch_all(
            "ev_reporting",
            """
            SELECT Dimension,
                   COUNT(*) AS TotalChecks,
                   SUM(Result = 'Passed') AS PassedChecks,
                   SUM(Result = 'Failed') AS FailedChecks
            FROM dq_check_results
            WHERE RunID = %s
            GROUP BY Dimension
            ORDER BY Dimension
            """,
            (latest["RunID"],),
        )
    station_count = fetch_one(
        "Smart_EV_Charging_System",
        "SELECT COUNT(*) AS CountValue FROM ChargingStations",
    )
    charger_count = fetch_one(
        "Smart_EV_Charging_System",
        "SELECT COUNT(*) AS CountValue FROM Chargers",
    )
    session_count = fetch_one(
        "Smart_EV_Charging_System",
        "SELECT COUNT(*) AS CountValue FROM ChargingSessions",
    )
    payment_total = fetch_one(
        "Smart_EV_Charging_System",
        "SELECT COALESCE(SUM(Amount), 0) AS CountValue FROM Payments WHERE PaymentStatus = 'Success'",
    )
    return render_template(
        "overview.html",
        latest=latest,
        dimensions=dimensions,
        station_count=station_count["CountValue"],
        charger_count=charger_count["CountValue"],
        session_count=session_count["CountValue"],
        payment_total=payment_total["CountValue"],
    )


@app.post("/actions/upload-source")
def upload_source():
    uploaded = request.files.get("source_file")
    if not uploaded or not uploaded.filename:
        flash("Choose an Excel workbook to upload.", "error")
        return redirect(url_for("overview"))

    if not uploaded.filename.lower().endswith(".xlsx"):
        flash("Only .xlsx workbooks are supported.", "error")
        return redirect(url_for("overview"))

    connection = get_db("Smart_EV_Charging_System")
    cursor = connection.cursor()
    try:
        workbook = load_workbook(uploaded, read_only=True, data_only=True)
        sheet = workbook.active
        rows = sheet.iter_rows(values_only=True)
        headers = next(rows, None)
        if not headers:
            raise ValueError("The workbook is empty.")

        columns = [str(value).strip().lower() if value is not None else "" for value in headers]
        required = {
            "user_id", "vehicle_id", "charger_id", "booking_start",
            "booking_end", "session_start", "estimated_completion",
            "session_end", "energy_kwh", "session_status", "booking_status",
            "payment_amount", "payment_method", "payment_status", "transaction_date",
        }
        missing = sorted(required.difference(columns))
        if missing:
            raise ValueError(f"Missing required columns: {', '.join(missing)}.")

        positions = {name: columns.index(name) for name in required}
        allowed_session_statuses = {"InProgress", "Completed", "Interrupted", "Failed"}
        allowed_booking_statuses = {"Pending", "Confirmed", "Cancelled", "Completed", "NoShow"}
        allowed_payment_methods = {"Wallet", "Card", "UPI", "NetBanking", "Cash"}
        allowed_payment_statuses = {"Pending", "Success", "Failed", "Refunded"}
        imported = 0

        for row_number, values in enumerate(rows, start=2):
            if not values or all(value is None for value in values):
                continue
            data = {
                name: values[position] if position < len(values) else None
                for name, position in positions.items()
            }
            if any(data[name] is None for name in required):
                raise ValueError(f"Row {row_number} has blank required values.")
            if data["session_status"] not in allowed_session_statuses:
                raise ValueError(f"Row {row_number} has an invalid session_status.")
            if data["booking_status"] not in allowed_booking_statuses:
                raise ValueError(f"Row {row_number} has an invalid booking_status.")
            if data["payment_method"] not in allowed_payment_methods:
                raise ValueError(f"Row {row_number} has an invalid payment_method.")
            if data["payment_status"] not in allowed_payment_statuses:
                raise ValueError(f"Row {row_number} has an invalid payment_status.")

            cursor.execute(
                """
                SELECT
                    EXISTS(
                        SELECT 1 FROM Users
                        WHERE UserID = %s
                    ) AS UserExists,
                    EXISTS(
                        SELECT 1 FROM EVVehicles
                        WHERE VehicleID = %s AND UserID = %s
                    ) AS VehicleMatchesUser,
                    EXISTS(
                        SELECT 1 FROM Chargers
                        WHERE ChargerID = %s
                    ) AS ChargerExists
                """,
                (
                    data["user_id"], data["vehicle_id"], data["user_id"],
                    data["charger_id"],
                ),
            )
            user_exists, vehicle_matches_user, charger_exists = cursor.fetchone()
            if not user_exists or not vehicle_matches_user or not charger_exists:
                invalid_ids = []
                if not user_exists:
                    invalid_ids.append(f"user_id={data['user_id']}")
                if not vehicle_matches_user:
                    invalid_ids.append(
                        f"vehicle_id={data['vehicle_id']} does not belong "
                        f"to user_id={data['user_id']}"
                    )
                if not charger_exists:
                    invalid_ids.append(f"charger_id={data['charger_id']}")
                raise ValueError(
                    f"Row {row_number} has invalid references: "
                    f"{'; '.join(invalid_ids)}."
                )

            cursor.execute(
                """
                INSERT INTO Bookings
                    (UserID, VehicleID, ChargerID, BookingDate, StartTime, EndTime, Status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    data["user_id"], data["vehicle_id"], data["charger_id"],
                    data["booking_start"].date(), data["booking_start"],
                    data["booking_end"], data["booking_status"],
                ),
            )
            booking_id = cursor.lastrowid
            cursor.execute(
                """
                INSERT INTO ChargingSessions
                    (BookingID, UserID, VehicleID, ChargerID, StartTime,
                     EstimatedCompletionTime, EndTime, EnergyDeliveredKWh, Status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    booking_id, data["user_id"], data["vehicle_id"],
                    data["charger_id"], data["session_start"],
                    data["estimated_completion"], data["session_end"],
                    data["energy_kwh"], data["session_status"],
                ),
            )
            session_id = cursor.lastrowid
            cursor.execute(
                """
                INSERT INTO Payments
                    (UserID, SessionID, Amount, PaymentMethod, PaymentStatus, TransactionDate)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    data["user_id"], session_id, data["payment_amount"],
                    data["payment_method"], data["payment_status"],
                    data["transaction_date"],
                ),
            )
            imported += 1

        if imported == 0:
            raise ValueError("The workbook has no data rows.")

        connection.commit()
        workbook.close()
        flash(f"Imported {imported} session row(s). Run ETL and checks to see results.", "success")
    except Exception as exc:
        if "workbook" in locals():
            workbook.close()
        connection.rollback()
        flash(f"Excel upload failed: {exc}", "error")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("overview"))


@app.route("/history")
def history():
    runs = fetch_all(
        "ev_reporting",
        """
        SELECT * FROM dq_runs
        ORDER BY RunDate DESC, RunID DESC
        """,
    )
    return render_template("history.html", runs=runs)


@app.route("/runs/<int:run_id>")
def run_details(run_id):
    run = fetch_one(
        "ev_reporting",
        "SELECT * FROM dq_runs WHERE RunID = %s",
        (run_id,),
    )
    if not run:
        flash("Run not found.", "error")
        return redirect(url_for("history"))
    results = fetch_all(
        "ev_reporting",
        """
        SELECT * FROM dq_check_results
        WHERE RunID = %s
        ORDER BY ResultID
        """,
        (run_id,),
    )
    return render_template("run_details.html", run=run, results=results)


@app.route("/runs/<int:run_id>/checks/<int:result_id>/failures")
def failing_records(run_id, result_id):
    result = fetch_one(
        "ev_reporting",
        """
        SELECT * FROM dq_check_results
        WHERE RunID = %s AND ResultID = %s
        """,
        (run_id, result_id),
    )
    if not result:
        flash("Check result not found.", "error")
        return redirect(url_for("run_details", run_id=run_id))

    rows = result.get("SampleFailingRows") or []
    if isinstance(rows, str):
        rows = json.loads(rows)
    return render_template("failures.html", result=result, rows=rows)


@app.post("/actions/run-checks")
def run_checks_action():
    try:
        run_checks()
        flash("Data-quality checks completed.", "success")
    except Exception as exc:
        flash(f"Checks failed: {exc}", "error")
    return redirect(url_for("overview"))


@app.post("/actions/inject-defects")
def inject_defects_action():
    try:
        message = inject_defects()
        flash(message, "success")
    except Exception as exc:
        flash(f"Could not inject defects: {exc}", "error")
    return redirect(url_for("overview"))


@app.get("/actions/download-report")
def download_report():
    run = fetch_one(
        "ev_reporting",
        "SELECT * FROM dq_runs ORDER BY RunDate DESC, RunID DESC LIMIT 1",
    )
    if not run:
        flash("Run checks before downloading a report.", "error")
        return redirect(url_for("overview"))

    results = fetch_all(
        "ev_reporting",
        "SELECT * FROM dq_check_results WHERE RunID = %s ORDER BY ResultID",
        (run["RunID"],),
    )
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "DQ Results"
    sheet.append([
        "Check Name", "Dimension", "Table", "Result",
        "Bad Record Count", "Checked At",
    ])
    for result in results:
        sheet.append([
            result["CheckName"], result["Dimension"], result["TableTested"],
            result["Result"], result["BadRecordCount"], result["CheckedAt"],
        ])

    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name=f"dq_report_run_{run['RunID']}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


if __name__ == "__main__":
    app.run(debug=True)
