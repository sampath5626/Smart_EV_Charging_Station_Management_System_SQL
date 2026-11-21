import io
import json
import os

from flask import Flask, flash, redirect, render_template, send_file, url_for
from openpyxl import Workbook

from db import get_db
from dq_checks import run_checks
from inject_defects import inject_defects


app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "ev-data-quality-demo")


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
    return render_template("overview.html", latest=latest, dimensions=dimensions)


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
