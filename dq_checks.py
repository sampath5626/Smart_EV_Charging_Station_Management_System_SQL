import json

from db import get_db


CHECKS = [
    ("Source session completeness", "Completeness", "ChargingSessions"),
    ("Target session uniqueness", "Uniqueness", "fact_charging_sessions"),
    ("Negative or invalid session values", "Validity", "fact_charging_sessions"),
    ("Source-target session consistency", "Consistency", "ChargingSessions"),
    ("Charging session referential integrity", "Referential Integrity", "fact_charging_sessions"),
    ("Latest load timeliness", "Timeliness", "fact_charging_sessions"),
]


def run_query(connection, sql, params=None):
    cursor = connection.cursor(dictionary=True)
    cursor.execute(sql, params or ())
    rows = cursor.fetchall()
    cursor.close()
    return rows


def run_checks():
    source = get_db("Smart_EV_Charging_System")
    target = get_db("ev_reporting")

    try:
        results = []

        missing = run_query(
            source,
            """
            SELECT cs.SessionID
            FROM ChargingSessions cs
            LEFT JOIN ev_reporting.fact_charging_sessions fact
              ON fact.SessionID = cs.SessionID
            WHERE fact.SessionID IS NULL
            LIMIT 20
            """,
        )
        results.append(make_result(CHECKS[0], len(missing), missing))

        duplicates = run_query(
            target,
            """
            SELECT SessionID, COUNT(*) AS DuplicateCount
            FROM fact_charging_sessions
            GROUP BY SessionID
            HAVING COUNT(*) > 1
            LIMIT 20
            """,
        )
        results.append(make_result(CHECKS[1], len(duplicates), duplicates))

        invalid = run_query(
            target,
            """
            SELECT SessionID, EnergyDeliveredKWh, SessionDurationMinutes
            FROM fact_charging_sessions
            WHERE EnergyDeliveredKWh < 0
               OR SessionEndTime IS NOT NULL
              AND SessionEndTime < SessionStartTime
               OR SessionDurationMinutes < 0
            LIMIT 20
            """,
        )
        results.append(make_result(CHECKS[2], len(invalid), invalid))

        mismatch = run_query(
            source,
            """
            SELECT COUNT(*) AS BadRecordCount
            FROM (
                SELECT COUNT(*) AS SourceCount
                FROM ChargingSessions
                UNION ALL
                SELECT COUNT(*) AS SourceCount
                FROM ev_reporting.fact_charging_sessions
            ) counts
            HAVING MAX(SourceCount) <> MIN(SourceCount)
            """,
        )
        count = mismatch[0]["BadRecordCount"] if mismatch else 0
        results.append(make_result(CHECKS[3], count, mismatch))

        broken = run_query(
            target,
            """
            SELECT fact.SessionID
            FROM fact_charging_sessions fact
            WHERE fact.UserID IS NULL
               OR fact.ChargerID IS NULL
               OR fact.StationID IS NULL
            LIMIT 20
            """,
        )
        results.append(make_result(CHECKS[4], len(broken), broken))

        stale = run_query(
            target,
            """
            SELECT MAX(LoadedAt) AS LatestLoad
            FROM fact_charging_sessions
            WHERE LoadedAt < NOW() - INTERVAL 24 HOUR
            """,
        )
        stale_count = 1 if stale and stale[0]["LatestLoad"] is not None else 0
        results.append(make_result(CHECKS[5], stale_count, stale))

        save_run(results)
        return results
    finally:
        source.close()
        target.close()


def make_result(check, bad_count, rows):
    name, dimension, table_name = check
    return {
        "CheckName": name,
        "Dimension": dimension,
        "TableTested": table_name,
        "Result": "Failed" if bad_count else "Passed",
        "BadRecordCount": bad_count,
        "SampleFailingRows": rows[:20],
    }


def save_run(results):
    target = get_db("ev_reporting")
    cursor = target.cursor()

    try:
        passed = sum(result["Result"] == "Passed" for result in results)
        failed = len(results) - passed
        cursor.execute(
            """
            INSERT INTO dq_runs
            (TotalChecks, PassedChecks, FailedChecks, Status)
            VALUES (%s, %s, %s, %s)
            """,
            (len(results), passed, failed, "Failed" if failed else "Passed"),
        )
        run_id = cursor.lastrowid

        for result in results:
            cursor.execute(
                """
                INSERT INTO dq_check_results
                (RunID, CheckName, Dimension, TableTested, Result,
                 BadRecordCount, SampleFailingRows)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    run_id,
                    result["CheckName"],
                    result["Dimension"],
                    result["TableTested"],
                    result["Result"],
                    result["BadRecordCount"],
                    json.dumps(result["SampleFailingRows"], default=str),
                ),
            )
        target.commit()
        return run_id
    except Exception:
        target.rollback()
        raise
    finally:
        target.close()
