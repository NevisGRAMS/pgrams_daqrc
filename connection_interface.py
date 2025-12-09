from fake_hub import FakeHub
from mqtt_link import MqttLink
from grafana_link import GrafanaLink
from datamon import DaqCompMonitor, TpcReadoutMonitor, LowBwTpcMonitor, CommCodes
from test_web import ChannelMonitorWeb

from threading import Thread
from queue import Queue
import numpy as np
from time import time, sleep


class ConnectionInterface:
    def __init__(self, interface):

        self.ip_addr = ""
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
            "DaemonStat": DaqCompMonitor(),
            "TPCReadoutStat": TpcReadoutMonitor(),
            "TPCMonitorStat": LowBwTpcMonitor()
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

    def deserialize_telemetry(self, device, data):
        if device in list(self.deserializers.keys()) and len(data) > 0:
            self.deserializers[device].deserialize(data)
            return self.convert_metric_dict(self.deserializers[device].get_metric_dict())
        return data

    def display_data(self, data):
        print("Updating TPC metrics..")
        self.monitor.update_data(data["charge_baseline"], data["charge_rms"], data["charge_avg_num_hits"], 
                                 data["light_baseline"], data["light_rms"], data["light_avg_num_hits"])

    def deserialize_telemetry_args(self):
        print("Starting telemetry stream deserialization..")
        while True:
            if not self.serialized_data_queue.empty():
                telem = self.serialized_data_queue.get()
                deserialized_data = self.deserialize_telemetry(device=telem["dev"], data=telem["cmd_packet"].arguments)
                # Send data to Grafana
                self.grafana_link.send_mqtt_message(telem["dev"], deserialized_data)
                if telem["dev"] == "TPCMonitorStat":
                    self.display_data(deserialized_data)
                # Update webpage with raw metrics
                self.deserial_queue.put({'name': telem["dev"], 'timestamp_sec': time(),
                                               "cmd": telem["cmd_packet"].command, 'args': deserialized_data})
            sleep(0.1)
