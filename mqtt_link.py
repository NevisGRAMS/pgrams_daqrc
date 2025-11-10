from queue import Queue

class MqttLink:
    def __init__(self, mqtt_host, mqtt_port, queue=None, send_queue=None):
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        # Use MQTT, not yet implemented
        raise NotImplementedError("MQTT Link not yet implemented..")

        self.device_dict = {
            "MqttLink": self.mqtt_port
        }

        self.queues = {name: Queue() for name in self.device_dict}
        # The queue which holds data from all streams
        self.queue = queue

    def start_connection(self):
        pass

    def shutdown_connections(self):
        pass

    def clear_queues(self):
        for queue in self.queues:
            num_elements = 0
            while not self.queues[queue].empty():
                self.queues[queue].get()
                num_elements += 1
            print("Cleared " + str(num_elements) + " elements from queue " + queue)