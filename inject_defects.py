from db import get_db


def inject_defects():
    target = get_db("ev_reporting")
    cursor = target.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            UPDATE fact_charging_sessions
            SET EnergyDeliveredKWh = -1
            WHERE SessionID = (
                SELECT SessionID FROM (
                    SELECT SessionID
                    FROM fact_charging_sessions
                    WHERE EnergyDeliveredKWh >= 0
                    ORDER BY SessionID
                    LIMIT 1
                ) selected
            )
            """
        )
        cursor.execute(
            """
            DELETE FROM fact_charging_sessions
            WHERE SessionID = (
                SELECT SessionID FROM (
                    SELECT SessionID
                    FROM fact_charging_sessions
                    WHERE SessionStatus = 'Completed'
                    ORDER BY SessionID DESC
                    LIMIT 1
                ) selected
            )
            """
        )
        target.commit()
        return "Injected a negative energy value and deleted one completed session."
    finally:
        cursor.close()
        target.close()
