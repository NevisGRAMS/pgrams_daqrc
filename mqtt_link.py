from threading import Thread
import paho.mqtt.client as mqtt
from time import sleep
import json

from network_module import TCPProtocol, Command

class MqttLink:
    def __init__(self, mqtt_broker_addr, mqtt_port, metric_topic, command_topic, queue=None, send_queue=None):

        # Just a class for deserialize method
        self.tcp_protocol = TCPProtocol(0x0, 0)

        # The queue which holds data from all streams
        self.queue = queue
        self.send_queue = send_queue

        self.metric_client = None
        self.command_client = None
        self.broker_address = mqtt_broker_addr
        self.port = mqtt_port
        self.metric_topic = metric_topic
        self.command_topic = command_topic
        # Start MQTT link
        self.start_client()


    @staticmethod
    def on_subscribe(client, userdata, mid, granted_qos):
        print("Subscribed: " + str(mid) + " " + str(granted_qos))

    def on_connect(self, client, userdata, flags, rc):
        print("Connected with result code", rc)
        self.metric_client.subscribe(self.metric_topic)

    def start_client(self):
        # For metrics SUB
        self.metric_client = mqtt.Client(client_id="MetricSub")
        self.metric_client.on_connect = self.on_connect
        self.metric_client.on_message = self.on_message
        self.metric_client.connect(self.broker_address, self.port)
        self.metric_client.loop_start()
        # For commands PUB
        self.command_client = mqtt.Client(client_id="CommandPub")  # Unique client ID
        self.command_client.connect(self.broker_address, self.port)
        t2 = Thread(target=self.send_commands, daemon=True)
        t2.start()

    def start_connection(self):
        pass

    def shutdown_connections(self):
        pass

    def clear_queues(self):
        for queue in self.queue:
            num_elements = 0
            while not self.queue[queue].empty():
                self.queue[queue].get()
                num_elements += 1
            print("Cleared " + str(num_elements) + " elements from queue " + queue)

    def on_message(self, client, userdata, msg):
        """Continuously read from a TCP connection and emit received commands."""
        payload = json.loads(msg.payload.decode("utf-8"))
        cmd_packet = self.tcp_protocol.deserialize(payload["data"]) # returns a `Command`
        self.queue.put({"dev": payload["device"], "cmd_packet": cmd_packet})
        sleep(0.5)

    def send_commands(self):
        while True:
            while not self.send_queue.empty():
                command = self.send_queue.get()
                tcp = TCPProtocol(command["cmd"], len(command["args"]))
                tcp.arguments = command["args"]
                msg = {"device": command["dev"], "data": tcp.serialize()}
                self.command_client.publish(self.command_topic, json.dumps(msg))
                sleep(0.1)
            sleep(0.2)