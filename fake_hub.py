from network_module import IOContext, TCPConnection, Command
from threading import Thread
from time import sleep

"""
  Multiple TCP connections in place of the Hub Computer for now
"""
class FakeHub:

    def __init__(self, ip_addr, device_dict, queue=None, send_queue=None):
        # The connections and their ports
        self.ip_addr = ip_addr
        self.device_dict = device_dict

        # The queue which holds data from all streams
        self.queue = queue
        self.send_queue = send_queue

        self.io_context = None
        self.devices = {}
        self.connections_open = False


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
            t = Thread(target=self.serial_stream_device, args=(device_name,), daemon=True)
            t.start()
        # Thread to send commands
        t2 = Thread(target=self.send_commands, daemon=True)
        t2.start()

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
                self.queue.put({"dev": device_name, "cmd_packet": cmd})
            sleep(0.5)

    def send_commands(self):
        while True:
            while not self.send_queue.empty():
                command = self.send_queue.get()
                cmd = Command(command["cmd"], len(command["args"]))
                cmd.arguments = command["args"]
                self.devices[command["dev"]].write_send_buffer(cmd)
                sleep(0.1)
            sleep(0.2)
