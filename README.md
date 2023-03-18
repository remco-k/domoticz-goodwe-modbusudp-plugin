# Domoticz GoodWe Modbus UDP plugin

A Domoticz plugin that connects to GoodWe inverters over LAN or WLAN via UDP that supports Modbus.

The plugin uses a goodwe library from https://pypi.org/project/goodwe/ (https://github.com/marcelblijleven/goodwe) to communicate with the inverter.

## Features
* Auto detect singlephase or 3 phase model
* Port number is fixed at 8899
* Supports inverter shutdown and (temporary) disconnect
* Reset power sensors to 0 if state is wait mode
* Auto detects the inverter family
* Setting the inverter family manually speeds up the connection time

## Requirements
For XS inverter is firmware 1.xx.14 or higher required. Other GoodWe inverter model series (ET, EH, BT, BH, ES, EM, BP, DT, MS, NS) might work as well. This software is currently in a beta stage.


## Download and install requirements:


### Linux
Install the Goodwe Modbus UDP plugin:

``` shell
cd domoticz/plugins
git clone https://github.com/remco-k/domoticz-goodwe-modbusudp-plugin.git
```
* Note: Some Domoticz installation have other plugin paths (such as `domoticz/userdata/plugins`).

Install required dependencies:
``` shell
cd domoticz/plugins/domoticz-goodwe-modbusudp-plugin
sudo pip3 install -r requirements.txt
```

### Windows
Install the Goodwe Modbus UDP plugin:

``` shell
cd domoticz/plugins
git clone https://github.com/remco-k/domoticz-goodwe-modbusudp-plugin.git
```
* Note: Some Domoticz installation have other plugin paths (such as `domoticz/userdata/plugins`).
* Note: You must create the `plugins` path.

Install required dependencies by starting a command prompt with administrator rights:
``` shell
cd domoticz/plugins/domoticz-goodwe-modbusudp-plugin
"C:\Program Files (x86)\Python310-32\python.exe" -m pip install -r requirements.txt
```
* Note: Replace the path `C:\Program Files (x86)\Python310-32\` with the path where you have installed 32-bit Python.

## After installation
Restart your Domoticz, and add the hardware via Setup->Hardware and select Type: "GoodWe ModbusUDP", enter a name and IP address and optionally select the inverter family for a faster connection time. Set the interval to your needs and then press the "Add" button.
Then all of the inverter sensors should now be visible in "Utility" and "Temperature".

## Inverters reported to work with this plugin
* GW1000-XS Wifi
* GW3600T-DS Wifi
* GW3600D-NS
* GW10K-ET
