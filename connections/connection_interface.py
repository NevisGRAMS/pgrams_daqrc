import json
import os
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

        self.tmp_ctr = 0
        self.use_fake_hub = True
        self.ip_addr = os.getenv("FAKE_HUB_IP")
        if interface not in ["TCP", "MQTT"]:
            raise ValueError(f"Invalid interface {interface}")

        self.mqtt_broker_address = os.getenv("TPC_MQTT_IP") 
        self.mqtt_broker_port = int(os.getenv("TPC_MQTT_PORT")) 

        self.serialized_data_queue = Queue()
        # Queues to hold the received messages streams
        self.deserial_queue = Queue()
        self.send_queue = Queue()

        # Start the Grafana link
        self.grafana_link = GrafanaLink(mqtt_broker_addr=self.mqtt_broker_address, mqtt_port=self.mqtt_broker_port)

        try:
            self.db_link = MysqlLink()
            self.command_to_db_table = {
                int(CommCodes.OrcHardwareStatus): self.db_link.orch_db_name,
                int(CommCodes.ColHardwareStatus): self.db_link.tpc_db_name,
            }
        except Exception as e:
            print(f"Failed to connect to MySQL database with exception: {e}")
            self.db_link = None
            self.device_to_db_table = {}

        self.device_dict = {
            "DaemonStat": 50000,
            "DaemonCmd": 50001,
            "TPCReadoutStat": 50004,
            "TPCReadoutCmd": 50005,
            "TPCMonitorStat": 50002,
            "TPCMonitorCmd": 50003,
        }

        self.code_to_device = {
                0x3000: "DaemonStat",
                0x4000: "TPCReadoutStat"
                }

        print(f"Connecting to {interface}..")
        metric_topic = os.getenv("TPC_METRIC_TOPIC")
        #metric_topic = "rc/pgrams_metric_stream"
        command_topic = "rc/pgrams_command_stream"
        if self.use_fake_hub:
            self.interface = FakeHub(ip_addr=self.ip_addr, device_dict=self.device_dict,
                                     mqtt_broker_addr=self.mqtt_broker_address, mqtt_port=self.mqtt_broker_port,
                                     metric_topic=metric_topic, command_topic=command_topic)

        MqttLink(mqtt_broker_addr=self.mqtt_broker_address, mqtt_port=self.mqtt_broker_port,
                 metric_topic=metric_topic, command_topic=command_topic, use_fake_hub=self.use_fake_hub,
                 queue=self.serialized_data_queue, send_queue=self.send_queue)

        self.deserializers = {
            int(CommCodes.OrcHardwareStatus): DaqCompMonitor(),
            int(CommCodes.ColHardwareStatus): TpcReadoutMonitor(),
            0x4001: LowBwTpcMonitor(),
            0x4002: TpcMonitorChargeEvent(),
            0x4003: TpcMonitorLightEvent()
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

    def get_is_fake_hub(self):
        return self.use_fake_hub

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

    # def deserialize_telemetry(self, device, command, data):
    #     if device in list(self.deserializers.keys()) and len(data) > 0:
    #         if len(self.deserializers[device].keys()) == 1:
    #             dev_deserializer = self.deserializers[device][0]
    #         else:
    #             dev_deserializer = self.deserializers[device][command]
    #         dev_deserializer.deserialize(data)
    #         return self.convert_metric_dict(dev_deserializer.get_metric_dict())
    #     return data

    def deserialize_telemetry(self, command, data):
        if command in list(self.deserializers.keys()) and len(data) > 0:
            dev_deserializer = self.deserializers[command]
            dev_deserializer.deserialize(data)
            return self.convert_metric_dict(dev_deserializer.get_metric_dict())
        return data

    def display_samples(self, samples, channel, is_charge):
        self.monitor.update_samples(sample=samples, channel=channel, is_charge=is_charge)

    def display_data(self, data):
        print("Updating TPC metrics..")
        self.monitor.update_data(data["charge_baseline"], data["charge_rms"], data["charge_avg_num_hits"], 
                                 data["light_baseline"], data["light_rms"], data["light_avg_num_hits"])

    def data_monitor_handler(self, command, deserialized_data):
        if command == 0x4001:
            self.display_data(deserialized_data)
        elif command == 0x4002:
            if deserialized_data["channel_number"] != self.tmp_ctr or len(deserialized_data["charge_samples"]) != 256:
                print("--> ", deserialized_data["channel_number"], ":", len(deserialized_data["charge_samples"]))
            self.tmp_ctr += 1
            if deserialized_data["channel_number"] == 191: self.tmp_ctr = 0
            self.display_samples(deserialized_data["charge_samples"], deserialized_data["channel_number"], is_charge=True)
        elif command == 0x4003:
            print("--> ", deserialized_data["channel_number"], ":", len(deserialized_data["light_samples"]))
            self.display_samples(deserialized_data["light_samples"], deserialized_data["channel_number"], is_charge=False)

    def deserialize_telemetry_args(self):
        print("Starting telemetry stream deserialization..")
        while True:
            if not self.serialized_data_queue.empty():
                telem = self.serialized_data_queue.get()
                if not self.use_fake_hub:
                    command = telem["code"]
                    deserialized_data = self.deserialize_telemetry(command=command, data=telem["argv"])
                    if self.db_link is not None and command in list(self.command_to_db_table.keys()):
                        self.db_link.write_to_database(metrics=deserialized_data, table=self.command_to_db_table[command])
                    if command in [0x4001, 0x4002, 0x4003]:
                        self.data_monitor_handler(command=command, deserialized_data=deserialized_data)
                else:
                    deserialized_data = self.deserialize_telemetry(command=telem["cmd_packet"].command,
                                                                   data=telem["cmd_packet"].arguments)
                    # Send data to Grafana
                    self.grafana_link.send_mqtt_message(telem["dev"], deserialized_data)
                    
                    if telem["dev"] == "TPCMonitorStat":
                        self.data_monitor_handler(command=telem["cmd_packet"].command, deserialized_data=deserialized_data)

                    # Update webpage with raw metrics
                    self.deserial_queue.put({'name': telem["dev"], 'timestamp_sec': time(),
                                              "cmd": telem["cmd_packet"].command, 'args': deserialized_data})
            sleep(0.1)
