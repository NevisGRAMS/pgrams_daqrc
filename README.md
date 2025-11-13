This code allows the pGRAMS DAQ to be controlled by direct TCP connections from the DAQ processes.

This depends on two repositories, 
* [networking](https://github.com/NevisNeutrinos/networking) for TCP server connections to the DAQ processes and decoding the eGRAMS packets.
* [PGramsCommCodec](https://github.com/NevisNeutrinos/PGramsCommCodec) for decoding the word array into a python dictionary.

The conda dependancies are 
```
conda install -c conda-forge flask flask-socketio eventlet 
```
