import os

import mysql.connector
from dotenv import load_dotenv


load_dotenv()


def get_db(database=None):
    prefix = "TARGET" if database == "ev_reporting" else "SOURCE"
    return mysql.connector.connect(
        host=os.getenv(f"{prefix}_HOST", os.getenv("MYSQL_HOST", "127.0.0.1")),
        port=int(os.getenv(f"{prefix}_PORT", os.getenv("MYSQL_PORT", "3306"))),
        user=os.getenv(f"{prefix}_USER", os.getenv("MYSQL_USER", "root")),
        password=os.getenv(f"{prefix}_PASSWORD", os.getenv("MYSQL_PASSWORD", "")),
        database=database,
        autocommit=False,
    )
