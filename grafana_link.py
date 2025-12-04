import paho.mqtt.client as mqtt
import json

class GrafanaLink:
    def __init__(self):

        self.broker_address = "localhost" # Replace with your broker address
        self.port = 1883
        self.topic = {"DaemonStat": "metrics/daemon",
                      "TPCReadoutStat": "metrics/tpc_readout"}

        self.client = None
        # Start the client connection
        self.start_client()

        # Since Grafana does not calcuate rates from time series and we do not yet
        # have a database we have to calcuate rates on our own
        self.polling_interval = 2 # seconds
        self.prev_counts = {"num_events": 0,
                            "num_dma_loops": 0}


    def start_client(self):
        self.client = mqtt.Client(client_id="MetricPublisher") # Unique client ID
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
            print(f"Published '{message}' to topic '{self.topic[msg_source]}'")
