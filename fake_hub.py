from network_module import IOContext, TCPConnection, TCPProtocol, Command
from threading import Thread
from time import sleep
import paho.mqtt.client as mqtt
import json

"""
  Multiple TCP connections in place of the Hub Computer for now
"""
class FakeHub:

    def __init__(self, ip_addr, mqtt_broker_addr, mqtt_port, device_dict, metric_topic, command_topic):
        # The connections and their ports
        self.ip_addr = ip_addr
        self.device_dict = device_dict
        self.emulate_hub = True

        # Class to serialize code and args, since we only want the serialize method,
        # just init with meaningless command and no args
        self.tcp_protocol = TCPProtocol(0x0, 0)

        self.io_context = None
        self.devices = {}
        self.connections_open = False

        self.metric_client = None
        self.command_client = None
        if self.emulate_hub:
            self.broker_address = mqtt_broker_addr
            self.port = mqtt_port
            self.metric_topic = metric_topic
            self.command_topic = command_topic
            # Start MQTT link
            self.start_client()

    def start_client(self):
        # For metrics PUB
        self.metric_client = mqtt.Client(client_id="MetricPub") # Unique client ID
        self.metric_client.connect(self.broker_address, self.port)
        # For commands SUB
        self.command_client = mqtt.Client(client_id="CommandSub")
        self.command_client.on_connect = self.on_connect
        self.command_client.on_message = self.on_message #self.rc_to_daq
        self.command_client.connect(self.broker_address, self.port)
        self.command_client.loop_start()
        print("Started fake_hub clients")

    def on_connect(self, client, userdata, flags, rc):
        print("Connected with result code", rc)
        self.command_client.subscribe(self.command_topic)

    def get_devices(self):
        if not self.connections_open:
            raise ConnectionError("No connections open..")
        return self.devices

    def start_connection(self):
        # Start the ASIO IO context and start the servers
        self.io_context = IOContext()
        self.devices = {device_name: TCPConnection(self.io_context, self.ip_addr, self.device_dict[device_name],
                                              True, device_name.endswith("Cmd"), device_name.endswith("Stat")) # <server> <heartbeat> <monitor>
                                    for device_name in self.device_dict
                   }
        self.devices["DaemonStat"].run_ctx(self.io_context)
        self.connections_open = True
        for device_name in self.devices:
            print("Opening device " + device_name + "..")
            t = Thread(target=self.serial_stream_device, args=(device_name,), daemon=True)
            t.start()

    def shutdown_connections(self):
        # Stop the connections
        for device_name in self.devices:
            print("Stopping connection " + device_name + "..")
            self.devices[device_name].stop_ctx(self.io_context)
        print("Closed all server TCP/IP connections...")
        self.connections_open = False

    def serial_stream_device(self, device_name):
        """Continuously read from a TCP connection and emit received commands."""
        tcp_conn = self.devices[device_name]
        while self.connections_open:
            cmd_list = tcp_conn.read_recv_buffer(1000)
            for cmd in cmd_list:
                self.daq_to_rc(device_name, cmd)
            sleep(0.5)

    def daq_to_rc(self, device, command):
        # Receive metric packet from TCP and convert to binary
        tcp_protocol = TCPProtocol(command.command, len(command.arguments))
        tcp_protocol.arguments = command.arguments
        serialized = tcp_protocol.serialize() # returns list of bytes
        # Construct the json message and send on MQTT
        message = {"device": device, "cmd": int(command.command), "data": serialized}
        json_string = json.dumps(message)
        self.metric_client.publish(self.metric_topic, json_string)

    def on_message(self, client, userdata, msg):
        payload = json.loads(msg.payload.decode("utf-8"))
        deserialized_packet = self.tcp_protocol.deserialize(payload["data"])
        self.devices[payload["device"]].write_send_buffer(deserialized_packet)
        sleep(0.5)

