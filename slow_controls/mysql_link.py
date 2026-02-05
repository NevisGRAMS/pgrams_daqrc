import mysql.connector
import json
import os

class MysqlLink:
    def __init__(self):
        self.orch_db_name = "orchestrator_metrics"
        self.tpc_db_name = "tpc_metrics"
        self.database_tables = [self.orch_db_name, self.tpc_db_name]
        self.database_conn = self.connect_to_database()

        for table in self.database_tables:
            self.check_tables(table_name=table)


    def connect_to_database(self):
        return mysql.connector.connect(
            host=os.getenv("TPC_DB_HOST_IP"),
            user=os.getenv("TPC_DB_USER"),
            password=os.getenv("TPC_DB_PASSWORD"),
            database=os.getenv("TPC_DB_NAME"),
        )
    print("Connected to database!")

    def check_tables(self, table_name):
        """ Validate the tables"""
        cursor = self.database_conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS """ + table_name + """ (
            id INT AUTO_INCREMENT PRIMARY KEY,
            data_json JSON,
            ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        self.database_conn.commit()
        print(f"Validated database table {table_name}..")

    def test_orchestartor_write(self):
        test_dict = {"error_bit_word":0,"last_command":0,"last_command_status":0,"daq_bit_word":0,
                     "tpc_disk":177,"tof_disk":177,"sys_disk":177,"cpu_usage":3,"memory_usage":11,
                     "disk_temp":54,"cpu_temp":[37,35,37,37,34,36]}
        jstr = json.dumps(test_dict)

        cursor = self.database_conn.cursor()
        cursor.execute(
            "INSERT INTO " + self.orch_db_name + " (data_json) VALUES (%s)",
            (jstr,)
        )
        self.database_conn.commit()

    def test_tpc_write(self):
        test_dict = {"num_files": 24, "num_events": 120237, "run_number": 0, 
                     "board_status": [1277165312, 2146859028, 2146861076, 2146859028, 2146861076, 0], 
                     "last_command": 0, "num_dma_loops": 105334, "readout_state": 3, 
                     "avg_event_size": 56945, "error_bit_word": 0, "num_end_markers": 120237, 
                     "num_events_rate": 0.0, "received_mbytes": 27385, "num_start_markers": 120238, 
                     "num_dma_loops_rate": 0.0, "last_command_status": 57005, "num_rw_buffer_overflow": 0}
        jstr = json.dumps(test_dict)
                                                                                                   
        cursor = self.database_conn.cursor()
        cursor.execute(
            "INSERT INTO " + self.tpc_db_name + " (data_json) VALUES (%s)",
            (jstr,)
        )
        self.database_conn.commit()

    def write_to_database(self, metrics, table):
        if table not in self.database_tables:
            print(f"Unknown table {table}! \n Available tables are: {self.database_tables}")
            raise KeyError
            return
        print(metrics)
        cursor = self.database_conn.cursor()
        cursor.execute(
            "INSERT INTO " + table + " (data_json) VALUES (%s)",
            (json.dumps(metrics),)
        )
        self.database_conn.commit()
