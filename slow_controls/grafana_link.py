import paho.mqtt.client as mqtt
import json
import os

class GrafanaLink:
    def __init__(self, mqtt_broker_addr, mqtt_port):

        self.broker_address = mqtt_broker_addr
        self.port = mqtt_port
        self.topic = {"DaemonStat": "metrics/daemon",
                      "TPCReadoutStat": "metrics/tpc_readout",
                      "TPCMonitorStat": "metrics/tpc_monitor"}

        self.client = None
        # Start the client connection
        self.start_client()

        # Since Grafana does not calculate rates from time series and we do not yet
        # have a database we have to calculate rates on our own
        self.polling_interval = 2 # seconds
        self.prev_counts = {"num_events": 0,
                            "num_dma_loops": 0}


    def start_client(self):
        self.client = mqtt.Client(client_id="GrafanaPub") # Unique client ID
        self.client.username_pw_set(os.getenv("MQTT_UN"), os.getenv("MQTT_PWD"))
        self.client.connect(self.broker_address, self.port)
        self.client.loop_start() # Start a background thread to handle network traffic

    def calculate_rate(self, message):
        for k in self.prev_counts.keys():
            if k in message.keys():
                message[k + "_rate"] = (message[k] - self.prev_counts[k]) / self.polling_interval
                self.prev_counts[k] = message[k]
        return message

    def send_mqtt_message(self, msg_source, message):
        if msg_source in self.topic.keys():
            message = self.calculate_rate(message)
            json_string = json.dumps(message)
            self.client.publish(self.topic[msg_source], json_string)
            #print(f"Published '{message}' to topic '{self.topic[msg_source]}'")
