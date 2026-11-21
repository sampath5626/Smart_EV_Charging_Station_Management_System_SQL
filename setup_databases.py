import os
from pathlib import Path

import mysql.connector


PASSWORD = os.getenv("MYSQL_PASSWORD", "")
HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
PORT = int(os.getenv("MYSQL_PORT", "3306"))
USER = os.getenv("MYSQL_USER", "root")


def apply_sql_file(connection, file_name):
    sql_text = Path(file_name).read_text(encoding="utf-8")
    cursor = connection.cursor()

    for statement in sql_text.split(";"):
        statement = statement.strip()
        if statement:
            cursor.execute(statement)

    cursor.close()
    connection.commit()
    print(f"{file_name}: applied")


def main():
    connection = mysql.connector.connect(
        host=HOST,
        port=PORT,
        user=USER,
        password=PASSWORD,
        autocommit=False,
    )

    try:
        apply_sql_file(connection, "sql/target_schema.sql")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
