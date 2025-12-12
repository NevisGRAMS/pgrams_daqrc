import eventlet
eventlet.monkey_patch()  # patch standard library for concurrency

import json
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from threading import Thread
from time import sleep

from config_manager import ConfigManager
from datamon import CommCodes
from connection_interface import ConnectionInterface


app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")
"""
Handle the TPC configuration
"""
config_mgr = ConfigManager()

"""
  Make the TCP or MQTT connections. 
"""
conn_interface = ConnectionInterface(interface="TCP")
conn_interface.open_connections()
devices = conn_interface.get_device_names()

# Map GUI buttons to communication codes
command_map = {
    "START_STATUS": int(CommCodes.OrcStartComputerStatus),
    "STOP_STATUS": int(CommCodes.OrcStopComputerStatus),
    "START_ALL_DAQ": int(CommCodes.OrcBootAllDaq),
    "SHUTDOWN_ALL_DAQ": int(CommCodes.OrcShutdownAllDaq),
    "REBOOT_COMPUTER": int(CommCodes.OrcExecCpuRestart),
    "SHUTDOWN_COMPUTER": int(CommCodes.OrcExecCpuShutdown),
    "PCIE_DRIVER_INIT": int(CommCodes.OrcPcieInit),
    "START_MONITOR": int(CommCodes.OrcBootMonitor),
    "STOP_MONITOR": int(CommCodes.OrcShutdownMonitor),
    "RESET": int(CommCodes.ColResetRun),
    "CONFIGURE": int(CommCodes.ColConfigure),
    "START_RUN": int(CommCodes.ColStartRun),
    "STOP_RUN": int(CommCodes.ColStopRun),
    "MIN_METRIC": int(CommCodes.ColQueryLBData),
    "EVENT_METRIC": int(CommCodes.ColQueryEventData)
}

def stream_device():
    """Continuously read from a TCP connection and emit received commands."""
    while True:
        data = conn_interface.get_telemetry_data()
        if data is None:
            sleep(0.1)
            continue
        socketio.emit("command_response",
            {"device": data["name"], "timestamp": data["timestamp_sec"], "command": data["cmd"], "args": data["args"]}
        )
        eventlet.sleep(0.5)  # non-blocking sleep for eventlet

t = Thread(target=stream_device, daemon=True)
t.start()

def handle_command(device_name, command_name, value=None):
    print("-> ", device_name, command_name, value)
    args = []
    if value is not None:
        if device_name == "TPCMonitorCmd":
            args = [int(v) for v in value]
        else:
            args = [1] + config_mgr.serialize() if type(value) is dict else [int(value)]
    conn_interface.send_command(dev_name=device_name, command=command_map[command_name], args=args)

@app.route('/')
def index():
    return render_template('index_twocol_wconfig.html', devices=conn_interface.get_device_titles())

@socketio.on('load_config_file')
def on_load_config_file(data):
    path = data.get('path')
    sid = request.sid
    try:
        print("Loading config file: ", path)
        with open(path, 'r') as f:
            json_data = json.load(f)
        emit('config_loaded', json_data, room=sid)
    except Exception as e:
        emit('command_response', {'device': 'SERVER', 'command': 'ERROR', 'args': f'Failed to load file: {e}'}, room=sid)

@socketio.on('update_config')
def on_update_config(new_config):
    sid = request.sid
    config_mgr.update_from_dict(new_config)
    updated_dict = config_mgr.get_config()
    print("Updated config: ", updated_dict)
    emit("command_response", {'device': 'SERVER', 'command': 'INFO', 'args': f'Updated config {updated_dict}'}, room=sid)

@socketio.on('send_command')
def on_send_command(data):
    device_name = data.get('device')
    cmd_name = data.get('cmd')
    value = data.get('value')
    sid = request.sid
    if device_name in devices and cmd_name:
        handle_command(device_name=device_name, command_name=cmd_name, value=value)
    else:
        emit('command_response', {'device': device_name, 'command': 'ERROR', 'args': 'Invalid device or command'}, room=sid)

if __name__ == '__main__':
    # socketio.run(app, debug=True)
    socketio.run(app, host='0.0.0.0', port=5002, debug=True, use_reloader=False)

    # Stop the connections
    conn_interface.close_connections()
