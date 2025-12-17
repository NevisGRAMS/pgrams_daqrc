import json

from connections.fake_hub import FakeHub
from connections.mqtt_link import MqttLink
from slow_controls.grafana_link import GrafanaLink
from slow_controls.mysql_link import MysqlLink
from datamon import DaqCompMonitor, TpcReadoutMonitor, LowBwTpcMonitor, CommCodes
from datamon import TpcMonitorChargeEvent, TpcMonitorLightEvent
from data_monitoring.test_web import ChannelMonitorWeb

from threading import Thread
from queue import Queue
import numpy as np
from time import time, sleep


class ConnectionInterface:
    def __init__(self, interface):

        self.ip_addr = "10.44.45.96"
        if interface not in ["TCP", "MQTT"]:
            raise ValueError(f"Invalid interface {interface}")

        self.mqtt_broker_address = "localhost"
        self.mqtt_broker_port = 1883

        self.serialized_data_queue = Queue()
        # Queues to hold the received messages streams
        self.deserial_queue = Queue()
        self.send_queue = Queue()

        # Start the Grafana link
        self.grafana_link = GrafanaLink(mqtt_broker_addr=self.mqtt_broker_address, mqtt_port=self.mqtt_broker_port)

        try:
            self.db_link = MysqlLink()
            self.device_to_db_table = {
                "DaemonStat": self.db_link.database_tables["orch_metrics"],
                "TPCReadoutStat": self.db_link.database_tables["tpc_metrics"],
            }
        except Exception as e:
            print(f"Failed to connect to MySQL database with exception: {e}")
            self.db_link = None
            self.device_to_db_table = {}

        self.device_dict = {
            "DaemonStat": 50020,
            "DaemonCmd": 50021,
            "TPCReadoutStat": 50022,
            "TPCReadoutCmd": 50023,
            "TPCMonitorStat": 50024,
            "TPCMonitorCmd": 50025,
        }

        print(f"Connecting to {interface}..")
        metric_topic = "rc/pgrams_metric_stream"
        command_topic = "rc/pgrams_command_stream"
        self.interface = FakeHub(ip_addr=self.ip_addr, device_dict=self.device_dict,
                                 mqtt_broker_addr=self.mqtt_broker_address, mqtt_port=self.mqtt_broker_port,
                                 metric_topic=metric_topic, command_topic=command_topic)

        MqttLink(mqtt_broker_addr=self.mqtt_broker_address, mqtt_port=self.mqtt_broker_port,
                 metric_topic=metric_topic, command_topic=command_topic,
                 queue=self.serialized_data_queue, send_queue=self.send_queue)

        self.deserializers = {
            "DaemonStat": {0x0: DaqCompMonitor()},
            "TPCReadoutStat": {0x0: TpcReadoutMonitor()},
            "TPCMonitorStat": {0x4001: LowBwTpcMonitor(),
                               0x4002: TpcMonitorChargeEvent(),
                               0x4003: TpcMonitorLightEvent()}
        }

        self.device_title = [
                {'name': device_name, 'title': device_name + " [" + str(self.device_dict[device_name]) + "]"}
                 for device_name in self.device_dict
        ]

        # Start gui
        self.monitor = ChannelMonitorWeb()
        self.monitor.run()

        # Start the streaming
        t = Thread(target=self.deserialize_telemetry_args, daemon=True)
        t.start()
        print("Reached end of connection class")

    def send_command(self, dev_name, command, args):
        print("Cmd on queue", hex(command))
        self.send_queue.put({"dev": dev_name, "cmd": command, "args": args})

    def get_device_names(self):
        return list(self.device_dict.keys())

    def get_device_titles(self):
        return self.device_title

    def close_connections(self):
        self.interface.shutdown_connections()

    def open_connections(self):
        self.interface.start_connection()

    def get_telemetry_data(self):
        return self.deserial_queue.get() if not self.deserial_queue.empty() else None

    def clear_queue(self):
        num_elements = 0
        while not self.deserial_queue.empty():
            self.deserial_queue.get()
            num_elements += 1
        print("Cleared " + str(num_elements) + " elements from queue..")

    @staticmethod
    def convert_metric_dict(metric_dict):
        for k, v in metric_dict.items():
            if type(v) is np.ndarray:
                metric_dict[k] = v.tolist()
        return metric_dict

    def deserialize_telemetry(self, device, command, data):
        if device in list(self.deserializers.keys()) and len(data) > 0:
            if len(self.deserializers[device].keys()) == 1:
                dev_deserializer = self.deserializers[device][0]
            else:
                dev_deserializer = self.deserializers[device][command]
            dev_deserializer.deserialize(data)
            return self.convert_metric_dict(dev_deserializer.get_metric_dict())
        return data

    def display_samples(self, samples, channel, is_charge):
        self.monitor.update_samples(sample=samples, channel=channel, is_charge=is_charge)

    def display_data(self, data):
        print("Updating TPC metrics..")
        self.monitor.update_data(data["charge_baseline"], data["charge_rms"], data["charge_avg_num_hits"], 
                                 data["light_baseline"], data["light_rms"], data["light_avg_num_hits"])

    def deserialize_telemetry_args(self):
        print("Starting telemetry stream deserialization..")
        while True:
            if not self.serialized_data_queue.empty():
                telem = self.serialized_data_queue.get()
                deserialized_data = self.deserialize_telemetry(device=telem["dev"], command=telem["cmd_packet"].command,
                                                               data=telem["cmd_packet"].arguments)
                # Send data to Grafana
                self.grafana_link.send_mqtt_message(telem["dev"], deserialized_data)
                if self.db_link is not None and telem["dev"] in list(self.device_to_db_table.keys()):
                    print(telem["dev"])
                    self.db_link.write_to_database(metrics=deserialized_data, table=self.device_to_db_table[telem["dev"]])
                if telem["dev"] == "TPCMonitorStat":
                    if telem["cmd_packet"].command == 0x4001:
                        self.display_data(deserialized_data)
                    elif telem["cmd_packet"].command == 0x4002:
                        self.display_samples(deserialized_data["charge_samples"], deserialized_data["channel_number"], is_charge=True)
                    elif telem["cmd_packet"].command == 0x4003:
                        self.display_samples(deserialized_data["light_samples"], deserialized_data["channel_number"], is_charge=False)

                # Update webpage with raw metrics
                self.deserial_queue.put({'name': telem["dev"], 'timestamp_sec': time(),
                                               "cmd": telem["cmd_packet"].command, 'args': deserialized_data})
            sleep(0.1)
