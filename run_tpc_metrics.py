import threading
from connections.connection_interface import ConnectionInterface

"""
Flight version.
Run TPC metrics only without any GUI interface.
"""

if __name__ == '__main__':
    """
      Make the TCP or MQTT connections. 
    """
    conn_interface = ConnectionInterface(interface="TCP")
    using_fake_hub = conn_interface.get_is_fake_hub()
    if using_fake_hub:
        conn_interface.open_connections()

    exit_event = threading.Event()
    print("ctrl+c to exit..")
    try:
        exit_event.wait()
    except KeyboardInterrupt:
        print("Received a stop signal, shutting down..")

    # Stop the connections
    if using_fake_hub:
        conn_interface.close_connections()
