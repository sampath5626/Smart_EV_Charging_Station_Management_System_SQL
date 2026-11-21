import argparse
import os
from datetime import datetime

import mysql.connector
from dotenv import load_dotenv


load_dotenv()


SOURCE_QUERY = """
SELECT
    cs.SessionID,
    cs.BookingID,
    cs.UserID,
    u.FullName AS CustomerName,
    cs.VehicleID,
    v.Make AS VehicleMake,
    v.Model AS VehicleModel,
    cs.ChargerID,
    c.ChargerCode,
    c.StationID,
    s.StationName,
    cs.StartTime AS SessionStartTime,
    cs.EndTime AS SessionEndTime,
    TIMESTAMPDIFF(MINUTE, cs.StartTime, cs.EndTime) AS SessionDurationMinutes,
    cs.EstimatedCompletionTime,
    cs.EnergyDeliveredKWh,
    cs.Status AS SessionStatus,
    p.PaymentID,
    p.Amount AS PaymentAmount,
    p.PaymentStatus,
    p.TransactionDate,
    t.TariffID,
    t.PricePerKWh
FROM ChargingSessions cs
JOIN Users u ON u.UserID = cs.UserID
JOIN EVVehicles v ON v.VehicleID = cs.VehicleID
JOIN Chargers c ON c.ChargerID = cs.ChargerID
JOIN ChargingStations s ON s.StationID = c.StationID
LEFT JOIN Payments p ON p.SessionID = cs.SessionID
LEFT JOIN UserMemberships um
    ON um.UserID = cs.UserID
   AND um.Status = 'Active'
   AND DATE(cs.StartTime) BETWEEN um.StartDate AND um.EndDate
LEFT JOIN Tariffs t
    ON t.TariffID = (
        SELECT Candidate.TariffID
        FROM Tariffs Candidate
        WHERE Candidate.ChargerID = cs.ChargerID
          AND Candidate.PlanID = um.PlanID
          AND DATE(cs.StartTime) BETWEEN Candidate.EffectiveFrom AND Candidate.EffectiveTo
        ORDER BY Candidate.EffectiveFrom DESC
        LIMIT 1
    )
"""


DAILY_REVENUE_QUERY = """
INSERT INTO daily_station_revenue
(
    StationID, StationName, RevenueDate, SuccessfulPaymentCount,
    RevenueAmount, EnergyDeliveredKWh
)
SELECT
    StationID,
    StationName,
    DATE(SessionStartTime),
    SUM(CASE WHEN PaymentStatus = 'Success' THEN 1 ELSE 0 END),
    ROUND(SUM(CASE WHEN PaymentStatus = 'Success' THEN COALESCE(PaymentAmount, 0) ELSE 0 END), 2),
    ROUND(SUM(COALESCE(EnergyDeliveredKWh, 0)), 3)
FROM fact_charging_sessions
WHERE SessionStartTime IS NOT NULL
GROUP BY StationID, StationName, DATE(SessionStartTime)
"""


DAILY_UTILIZATION_SOURCE_QUERY = """
SELECT
    c.ChargerID,
    c.ChargerCode,
    c.StationID,
    DATE(b.StartTime) AS UtilizationDate,
    COUNT(b.BookingID) AS ActiveBookingCount,
    SUM(TIMESTAMPDIFF(MINUTE, b.StartTime, b.EndTime)) AS BookedMinutes,
    1440 AS AvailableMinutes,
    ROUND(
        SUM(TIMESTAMPDIFF(MINUTE, b.StartTime, b.EndTime)) * 100.0 / 1440,
        2
    ) AS UtilizationPercent
FROM Chargers c
JOIN Bookings b
  ON b.ChargerID = c.ChargerID
 AND b.Status NOT IN ('Cancelled', 'NoShow')
WHERE b.StartTime IS NOT NULL
  AND b.EndTime IS NOT NULL
GROUP BY c.ChargerID, c.ChargerCode, c.StationID, DATE(b.StartTime)
"""


def mysql_config(prefix, database):
    return {
        "host": os.getenv(f"{prefix}_HOST", os.getenv("MYSQL_HOST", "127.0.0.1")),
        "port": int(os.getenv(f"{prefix}_PORT", os.getenv("MYSQL_PORT", "3306"))),
        "user": os.getenv(f"{prefix}_USER", os.getenv("MYSQL_USER", "root")),
        "password": os.getenv(f"{prefix}_PASSWORD", os.getenv("MYSQL_PASSWORD", "")),
        "database": database,
        "autocommit": False,
    }


def load_full(source_db, target_db):
    source = mysql.connector.connect(**mysql_config("SOURCE", source_db))
    target = mysql.connector.connect(**mysql_config("TARGET", target_db))

    try:
        source_cursor = source.cursor(dictionary=True)
        target_cursor = target.cursor()

        source_cursor.execute(SOURCE_QUERY)
        rows = source_cursor.fetchall()

        target_cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        target_cursor.execute("TRUNCATE TABLE daily_slot_utilization")
        target_cursor.execute("TRUNCATE TABLE daily_station_revenue")
        target_cursor.execute("TRUNCATE TABLE fact_charging_sessions")
        target_cursor.execute("SET FOREIGN_KEY_CHECKS = 1")

        fact_insert = """
        INSERT INTO fact_charging_sessions (
            SessionID, BookingID, UserID, CustomerName, VehicleID,
            VehicleMake, VehicleModel, ChargerID, ChargerCode, StationID,
            StationName, SessionStartTime, SessionEndTime,
            SessionDurationMinutes, EstimatedCompletionTime,
            EnergyDeliveredKWh, SessionStatus, PaymentID, PaymentAmount,
            PaymentStatus, TransactionDate, TariffID, PricePerKWh,
            LoadedAt
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s
        )
        """

        loaded_at = datetime.now()
        for row in rows:
            target_cursor.execute(
                fact_insert,
                (
                    row["SessionID"], row["BookingID"], row["UserID"],
                    row["CustomerName"], row["VehicleID"], row["VehicleMake"],
                    row["VehicleModel"], row["ChargerID"], row["ChargerCode"],
                    row["StationID"], row["StationName"], row["SessionStartTime"],
                    row["SessionEndTime"], row["SessionDurationMinutes"],
                    row["EstimatedCompletionTime"], row["EnergyDeliveredKWh"],
                    row["SessionStatus"], row["PaymentID"], row["PaymentAmount"],
                    row["PaymentStatus"], row["TransactionDate"], row["TariffID"],
                    row["PricePerKWh"], loaded_at,
                ),
            )

        target_cursor.execute(DAILY_REVENUE_QUERY)

        source_cursor.execute(DAILY_UTILIZATION_SOURCE_QUERY)
        utilization_rows = source_cursor.fetchall()
        utilization_insert = """
        INSERT INTO daily_slot_utilization (
            ChargerID, ChargerCode, StationID, UtilizationDate,
            ActiveBookingCount, BookedMinutes, AvailableMinutes,
            UtilizationPercent
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        for row in utilization_rows:
            target_cursor.execute(
                utilization_insert,
                (
                    row["ChargerID"], row["ChargerCode"], row["StationID"],
                    row["UtilizationDate"], row["ActiveBookingCount"],
                    row["BookedMinutes"], row["AvailableMinutes"],
                    row["UtilizationPercent"],
                ),
            )
        target.commit()

        print(
            "ETL complete:",
            f"{len(rows)} charging sessions loaded",
            "at", loaded_at.isoformat(timespec="seconds"),
        )
    except Exception:
        target.rollback()
        raise
    finally:
        source.close()
        target.close()


def parse_args():
    parser = argparse.ArgumentParser(description="Load EV source data into ev_reporting.")
    parser.add_argument("--source-db", default="Smart_EV_Charging_System")
    parser.add_argument("--target-db", default="ev_reporting")
    return parser.parse_args()


if __name__ == "__main__":
    load_full(**vars(parse_args()))
