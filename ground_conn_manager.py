from fake_hub import FakeHub
from mqtt_link import MqttLink


class GroundConnectionManager:
    def __init__(self, fake_hub):

        if fake_hub:
            self.link = FakeHub()
            self.link.start_connection()
        else:
            self.link = MqttLink()
            self.link.start_connection()

