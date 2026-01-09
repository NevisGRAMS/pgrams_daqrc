This code allows the pGRAMS DAQ to be controlled by direct TCP connections from the DAQ processes.

This depends on two repositories, 
* [networking](https://github.com/NevisNeutrinos/networking) for TCP server connections to the DAQ processes and decoding the eGRAMS packets.
* [PGramsCommCodec](https://github.com/NevisNeutrinos/PGramsCommCodec) for decoding the word array into a python dictionary.

The conda dependancies are 
```
conda install -c conda-forge flask flask-socketio eventlet 
```

## Link & Database Credentials

To operate the program uses an MQTT link to receive metrics and optionally send commands. Additionally,
if running in `hub_emulator` mode (aka `fake_hub`) the IP address of the host machine must be specified.
A template script `temp_setup_credentials.sh` is provided in the root directory, a copy can be made and the relevant details added.
Thereafter `source <your_script_name.sh> will then provide the credentails for all the connections.

The low-bandwidth metrics can be saved to a MySQL database for storage and display by Grafana. The password for the 
database can also be set in the credential script.
