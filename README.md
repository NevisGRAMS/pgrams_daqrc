This code allows the pGRAMS DAQ to be controlled by direct TCP connections from the DAQ processes.

This depends on two repositories, 
* [networking](https://github.com/NevisNeutrinos/networking) for TCP server connections to the DAQ processes and decoding the eGRAMS packets.
* [PGramsCommCodec](https://github.com/NevisNeutrinos/PGramsCommCodec) for decoding the word array into a python dictionary.

It is recommened to create a virtual environment to install the dependancies. You can use either `conda` or `venv` with `conda` or `pip`
package managers, respectively.
```
conda create --name <your_venv>
conda activate <your_venv>
or
python3 -m venv .<your_venv>
source .<your_venv>/bin/activate
```

The dependancies can be installed using conda or pip like,
```
conda install -c conda-forge flask flask-socketio eventlet
or
pip install flask flask-socketio eventlet
```

Additionally the python bindings in `networking` and `PGramsCodec` must be compiled and installed in your _**virtual environment**_. 

* networking: `cd extern && pip install .`
* PGramsCodec: `pip install .`


## Link & Database Credentials

To operate the program uses an MQTT link to receive metrics and optionally send commands. Additionally,
if running in `hub_emulator` mode (aka `fake_hub`) the IP address of the host machine must be specified.
A template script `temp_setup_credentials.sh` is provided in the root directory, a copy can be made and the relevant details added.
Thereafter `source <your_script_name.sh> will then provide the credentails for all the connections.

The low-bandwidth metrics can be saved to a MySQL database for storage and display by Grafana. The password for the 
database can also be set in the credential script.
