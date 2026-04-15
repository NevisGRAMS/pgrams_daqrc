"""
MySQL database handler for pGRAMS TPC configuration logging.

Reads credentials from environment variables set by temp_setup_credentials.sh:
  TPC_DB_HOST_IP, TPC_DB_USER, TPC_DB_PASSWORD, TPC_DB_NAME
"""

import os
import mysql.connector


TABLE_NAME = "tpc_configs"

CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME,
    description VARCHAR(255),
    config_json TEXT,
    txt_file VARCHAR(255)
)
"""


class ConfigDB:
    """Thin wrapper around MySQL for logging TPC configurations."""

    def __init__(self):
        self.conn = mysql.connector.connect(
            host=os.getenv("TPC_DB_HOST_IP"),
            user=os.getenv("TPC_DB_USER"),
            password=os.getenv("TPC_DB_PASSWORD"),
            database=os.getenv("TPC_DB_NAME"),
        )
        self._ensure_table()
        print("ConfigDB: connected to database")

    def _ensure_table(self):
        cursor = self.conn.cursor()
        cursor.execute(CREATE_TABLE_SQL)
        self.conn.commit()
        cursor.close()

    def get_next_id(self):
        """Return the next auto-increment ID (current max + 1)."""
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT COALESCE(MAX(id), 0) + 1 FROM {TABLE_NAME}")
        next_id = cursor.fetchone()[0]
        cursor.close()
        return next_id

    def log_config(self, timestamp, description, config_json, txt_file):
        """Insert a configuration record."""
        cursor = self.conn.cursor()
        cursor.execute(
            f"INSERT INTO {TABLE_NAME} (timestamp, description, config_json, txt_file) "
            "VALUES (%s, %s, %s, %s)",
            (timestamp, description, config_json, txt_file),
        )
        self.conn.commit()
        cursor.close()

    def close(self):
        if self.conn and self.conn.is_connected():
            self.conn.close()
