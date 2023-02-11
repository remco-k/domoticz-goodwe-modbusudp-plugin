#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# GoodWe ModbusUDP fixed at portnumber 8899
#
# Source:  https://github.com/remco-k/domoticz-goodwe-modbusudp-plugin
# Author:  Remco Kuijer
# License: Free. Use at your own risk.

"""
<plugin key="GoodWe_ModbusUDP" name="GoodWe ModbusUDP" author="Remco Kuijer" version="0.0.3" wikilink="https://github.com/remco-k/domoticz-goodwe-modbusudp-plugin/blob/master/README.md" externallink="https://github.com/remco-k/domoticz-goodwe-modbusudp-plugin">
   <description>
        <h2>GoodWe Modbus UDP plugin</h2><br/>
        <h3>Features</h3>
        <ul style="list-style-type:square">
            <li>Auto detect singlephase or 3 phase model</li>
            <li>Port number is fixed at 8899</li>
            <li>Supports inverter shutdown and (temporary) disconnect</li>
            <li>Reset power sensors to 0 if state is wait mode</li>
            <li>Auto detects the inverter family</li>
            <li>Setting the inverter family manually speeds up the connection time</li>
        </ul>
    </description>
    <params>
        <param field="Address" label="Inverter IP Address" width="150px" required="true" />
        <param field="Mode3" label="Inverter Family" width="100px" required="true" default="Auto" >
            <options>
                <option label="Auto" value="" default="true" />
                <option label="ET" value="ET" />
                <option label="EH" value="EH" />
                <option label="BT" value="BT" />
                <option label="BH" value="BH" />
                <option label="ES" value="ES" />
                <option label="EM" value="EM" />
                <option label="BP" value="BP" />
                <option label="DT" value="DT" />
                <option label="MS" value="MS" />
                <option label="NS" value="NS" />
                <option label="XS" value="XS" />
            </options>
        </param>
        <param field="Mode1" label="Add missing devices" width="100px" required="true" default="Yes" >
            <options>
                <option label="Yes" value="Yes" default="true" />
                <option label="No" value="No" />
            </options>
        </param>
        <param field="Mode2" label="Interval" width="100px" required="true" default="5" >
            <options>
                <option label="1  second"  value="1" />                
                <option label="5  seconds" value="5" default="true" />
                <option label="10 seconds" value="10" />
                <option label="20 seconds" value="20" />
                <option label="30 seconds" value="30" />
                <option label="60 seconds" value="60" />
                <option label="120 seconds" value="120" />
                <option label="240 seconds" value="240" />
            </options>
        </param>
        <param field="Mode5" label="Log level" width="100px">
            <options>
                <option label="Normal" value="Normal" default="true" />
                <option label="Extra" value="Extra"/>
                <option label="Debug" value="Debug"/>
            </options>
        </param>
    </params>
</plugin>
"""

if __name__ == '__main__': # for local debugging purposes without the Domoticz framework, this gets emulated in a very simple fashion.
    import sys
    sys.path.append('../domoticz-goodwe-modbusudp-plugin-tester/')    
    from Domoticz import * 
else:
    import Domoticz
import goodwe
from enum import IntEnum
from pymodbus.exceptions import ConnectionException
import time
import asyncio

class Column(IntEnum):
    MODBUSNAME      = 0
    DISPLAYNAME     = 1
    TYPE            = 2
    SUBTYPE         = 3
    SWITCHTYPE      = 4
    OPTIONS         = 5
    FORMAT          = 6
    PREPEND_IDNUM   = 7
    RST0WAIT        = 8 
    FOR3PHASEMODEL  = 9
    IDNUM = 10

class DType(IntEnum): 
    General=243 #F3
    Usage=248   #F8

class DGeneralSubType:
    Temperature=5 #5
    Percentage=6 #6
    Voltage=8 #8
    Text=19  #13
    Current=23 #17
    Electric=29 #1D
    CustomSensor=31 #1F

class DUsageSubType:
    Electric=1

class DSwitchType:
    General=0 
    EnergyGenerated=4

THREEPHASE_SERIES = [ "ET","BT","DT" ] # All models in these series are 3-phase models, so we can skip our 3 phase model detection.

INVERTER_PARAMS = [
#   MODBUSNAME,     DISPLAY_NAME,         TYPE,           SUBTYPE,                      SWITCHTYPE,                  OPTIONS,              FORMAT,        PREPEND_IDNUM, RST0WAIT FOR3PHASEMODEL, IDNUM
    ["vpv1",        "PV1 Voltage",        DType.General,  DGeneralSubType.Voltage,      DSwitchType.General,         {},                   "{:.2f}",      None,           True,   False,           1 ], # PV1 Voltage = 127.1 V
    ["ppv1",        "PV1 Power",          DType.Usage,    DUsageSubType.Electric,       DSwitchType.General,         {},                   "{:.2f}",      None,           True,   False,           2 ], # PV1 Power = 407 W
    ["ppv",         "PV Power",           DType.Usage,    DUsageSubType.Electric,       DSwitchType.General,         {},                   "{:.2f}",      None,           True,   False,           4 ], # PV Power = 389 W
    ["work_mode",   "Status code",        DType.General,  DGeneralSubType.Text,         DSwitchType.General,         {},                   "{}",          None,           False,  False,           5 ], # Work Mode Code = 1
    ["e_total",     "Total Generation",   DType.General,  DGeneralSubType.Electric,     DSwitchType.EnergyGenerated, {},                   "{};{}",       4,              False,  False,           6 ], # Total PV Generation = 7.8 kWh
    ["ipv1",        "PV1 Current",        DType.General,  DGeneralSubType.Current,      DSwitchType.General,         {},                   "{:.2f}",      None,           True,   False,           7 ], # PV1 Current = 3.2 A
    ["vpv2",        "PV2 Voltage",        DType.General,  DGeneralSubType.Voltage,      DSwitchType.General,         {},                   "{:.2f}",      None,           True,   False,           8 ], # PV2 Voltage = 127.1 V
    ["ipv2",        "PV2 Current",        DType.General,  DGeneralSubType.Current,      DSwitchType.General,         {},                   "{:.2f}",      None,           True,   False,           9 ], # PV2 Current = 3.2 A
    ["ppv2",        "PV2 Power",          DType.Usage,    DUsageSubType.Electric,       DSwitchType.General,         {},                   "{:.2f}",      None,           True,   False,           10 ],# PV2 Power = 407 W
    ["vline1",      "Grid L1-L2 Voltage", DType.General,  DGeneralSubType.Voltage,      DSwitchType.General,         {},                   "{:.2f}",      None,           False,  True,            11 ], # On-grid L1-L2 Voltage = -0.1 V
    ["vline2",      "Grid L2-L3 Voltage", DType.General,  DGeneralSubType.Voltage,      DSwitchType.General,         {},                   "{:.2f}",      None,           False,  True,            12 ], # On-grid L2-L3 Voltage = -0.1 V
    ["vline3",      "Grid L3-L1 Voltage", DType.General,  DGeneralSubType.Voltage,      DSwitchType.General,         {},                   "{:.2f}",      None,           False,  True,            13 ], # On-grid L3-L1 Voltage = -0.1 V
    ["vgrid1",      "Grid L1 Voltage",    DType.General,  DGeneralSubType.Voltage,      DSwitchType.General,         {},                   "{:.2f}",      None,           False,  False,           14 ], # On-grid L1 Voltage = 236.7 V
    ["vgrid2",      "Grid L2 Voltage",    DType.General,  DGeneralSubType.Voltage,      DSwitchType.General,         {},                   "{:.2f}",      None,           False,  True,            15 ], # On-grid L2 Voltage = -0.1 V
    ["vgrid3",      "Grid L3 Voltage",    DType.General,  DGeneralSubType.Voltage,      DSwitchType.General,         {},                   "{:.2f}",      None,           False,  True,            16 ], # On-grid L3 Voltage = -0.1 V
    ["work_mode_label","Status",          DType.General,  DGeneralSubType.Text,         DSwitchType.General,         {},                   "{}",          None,           False,  False,           17 ], # Work Mode = Normal
    ["igrid1",      "L1 Current",         DType.General,  DGeneralSubType.Current,      DSwitchType.General,         {},                   "{:.2f}",      None,           True,   False,           18 ], # L1 Current = 1.7 A
    ["igrid2",      "L2 Current",         DType.General,  DGeneralSubType.Current,      DSwitchType.General,         {},                   "{:.2f}",      None,           True,   True,            19 ], # L2 Current = 0 A
    ["igrid3",      "L3 Current",         DType.General,  DGeneralSubType.Current,      DSwitchType.General,         {},                   "{:.2f}",      None,           True,   True,            20 ], # L3 Current = 0 A
    ["fgrid1",      "L1 Frequency",       DType.General,  DGeneralSubType.CustomSensor, DSwitchType.General,         {"Custom": "1;Hz"},   "{:.2f}",      None,           False,  False,           21 ], # L1 Frequency = 49.99 Hz
    ["fgrid2",      "L2 Frequency",       DType.General,  DGeneralSubType.CustomSensor, DSwitchType.General,         {"Custom": "1;Hz"},   "{:.2f}",      None,           False,  True,            22 ], # L2 Frequency = 0 Hz
    ["fgrid3",      "L3 Frequency",       DType.General,  DGeneralSubType.CustomSensor, DSwitchType.General,         {"Custom": "1;Hz"},   "{:.2f}",      None,           False,  True,            23 ], # L3 Frequency = 0 Hz
    ["pgrid1",      "L1 Power",           DType.Usage,    DUsageSubType.Electric,       DSwitchType.General,         {},                   "{:.2f}",      None,           True,   False,           24 ], # L1 Power = 402 W
    ["pgrid2",      "L2 Power",           DType.Usage,    DUsageSubType.Electric,       DSwitchType.General,         {},                   "{:.2f}",      None,           True,   True,            25 ], # L2 Power = 0 W
    ["pgrid3",      "L3 Power",           DType.Usage,    DUsageSubType.Electric,       DSwitchType.General,         {},                   "{:.2f}",      None,           True,   True,            26 ], # L3 Power = 0 W
    ["error_codes", "Error code",         DType.General,  DGeneralSubType.CustomSensor, DSwitchType.General,         {},                   "{:.2f}",      None,           False,  False,           27 ], # Error code
    ["warning_code", "Warning code",      DType.General,  DGeneralSubType.CustomSensor, DSwitchType.General,         {},                   "{:.2f}",      None,           False,  False,           28 ], # Warning code
    ["temperature", "Temperature",        DType.General,  DGeneralSubType.Temperature,  DSwitchType.General,         {},                   "{:.2f}",      None,           False,  False,           29 ], # Temperature
    ["vbus",        "Bus Voltage",        DType.General,  DGeneralSubType.Voltage,      DSwitchType.General,         {},                   "{:.2f}",      None,           True,   False,           30 ], # Bus Voltage = 377.8 V
    ["vnbus",       "NBus Voltage",       DType.General,  DGeneralSubType.Voltage,      DSwitchType.General,         {},                   "{:.2f}",      None,           True,   True,            31 ], # NBus Voltage = -0.1 V
    ["e_day",       "Today's Generation", DType.General,  DGeneralSubType.Electric,     DSwitchType.EnergyGenerated, {},                   "{};{}",       4,              False,  False,           32 ], # Today's PV Generation = 0.9 kWh
    ["h_total",     "Total hours",        DType.General,  DGeneralSubType.CustomSensor, DSwitchType.General,         {"Custom": "1;h"},    "{:.2f}",      None,           False,  False,           33 ], # Hours Total = 29 h
    ["funbit",      "FunBit",             DType.General,  DGeneralSubType.CustomSensor, DSwitchType.General,         {},                   "{:.2f}",      None,           False,  False,           34 ], # FunBit=336
    ["timestamp",   "Time",               DType.General,  DGeneralSubType.Text,         DSwitchType.General,         {},                   "{}",          None,           False,  False,           3   ] # Timestamp = 2022-06-06 11:23:49 
]

# A time counter in milleconds that is guaranteed to go forward.
def millis(): 
    return int(time.monotonic() * 1000)

class BasePlugin:

    def __init__(self):
        self.inverter = None # holds the inverter communication class
        self.inverterIs3PhaseModel = True # Is the inverter singlephase or 3 phase?
        self.add_devices = False # Add devices automaticly

        # GoodWe inverters are likely to completely shutdown when the sun is gone. They will become unavailable after that.
        # We would like to retry to connect every now and then. lastconnectfailuretime holds the last known time when the connection was lost.
        # retrydelay (in msec) is the time we wait before retrying to connect to the inverter.
        # This also applies when the connection to the inverter is lost due to networking problems, such as the Wifi connection being unstable.
        # (GoodWe inverters are known to have a unstable Wifi plug)
        self.lastconnectfailuretime=None
        self.retrydelay=30000 # 30 seconds.

    def onStart(self):
        self.add_devices = bool(Parameters["Mode1"])
        Domoticz.Heartbeat(int(Parameters["Mode2"]))
        if Parameters["Mode5"] == "Debug":
            Domoticz.Debugging(1)
        else:
            Domoticz.Debugging(0)
        Domoticz.Debug(
            "onStart Address: {} Port: {}".format(
                Parameters["Address"],
                Parameters["Port"]
            )
        )

        self.connectToInverter()
        self.readFromInverter()

    def connectToInverter(self):
        self.inverter = None
        try:    
            famStr=Parameters["Mode3"]
            host=Parameters["Address"]
            if famStr=="":
                famStr="Auto. (Setting family to your inverters family spec, speeds up the wait time to connect)"
            Domoticz.Log(f"Connecting to inverter. Host: {host}, Port: 8899, Family: {famStr}.")
            self.inverter =  asyncio.run( goodwe.connect(host=host, family=Parameters["Mode3"], retries=3) )
        except goodwe.RequestFailedException as e:
            Domoticz.Error(f"Request failed: Cannot connect to inverter: {e.message}") 
            famStr=Parameters["Mode3"]
            if Parameters["Mode3"]!="":
                Domoticz.Error(f"If this problem persists, please check if your family model ({famStr}) is correct for your inverter and check your network connections.") 

        except ConnectionException as e:
            Domoticz.Error(f"Cannot connect to inverter: {e.string}") 
        
        if self.inverter!=None: 
            Domoticz.Log(f"Connected to inverter model: {self.inverter.model_name}")
        return self.inverter!=None

    def onHeartbeat(self):
        Domoticz.Debug("Heartbeat")
        if self.inverter:
            runtime_data = None
            try:
                runtime_data = asyncio.run( self.inverter.read_runtime_data() )
            except ConnectionException as e:
                runtime_data = None
                Domoticz.Log("Connection faillure")
            else:
                # Yaay! We have a working connection with the GoodWe inverter and have read some data from it.    
                if runtime_data:
                    updated = 0
                    device_count = 0
                    # Log all modbus values when enabled:
                    if "Mode5" in Parameters and Parameters["Mode5"] == "Extra":
                        for sensor in self.inverter.sensors():
                            if sensor.id_ in runtime_data:                        
                                Domoticz.Log(f"Modbus sensor '{sensor.id_}': \t\t {sensor.name} = {runtime_data[sensor.id_]} {sensor.unit}")

                    
                    for unit in INVERTER_PARAMS: # Iterate through our lookup table INVERTER_PARAMS
                        if unit[Column.IDNUM] in Devices: # Find the device in the Domoticz devices list
                            for sensor in self.inverter.sensors(): # Iterate and find the modbusname in the inverter.sensors
                                if sensor.id_==unit[Column.MODBUSNAME]:                        
                                    # Now we read the value and debuglog it.
                                    value = runtime_data[unit[Column.MODBUSNAME]]
                                    Domoticz.Debug(f"Processing '{sensor.id_}': Value {sensor.name} = {format(value)} {sensor.unit}.")
                                    
                                    if unit[Column.SWITCHTYPE]==DSwitchType.EnergyGenerated: # The value has been returned by the GoodWe library in kWh, but needs to be Wh for Domoticz
                                        value=value*1000.0
                                    
                                    if unit[Column.RST0WAIT]==True and value!=0 and runtime_data["work_mode"]==0: # 0=Wait mode, 1=Normal: ppv, ppv1, ppv2,.... and more values looks nice to be reset to 0 instead of leaving the last known value.
                                        # if wait mode, then force al current power generated 'DType.Usage' numbers to 0
                                        Domoticz.Debug(f"Wait mode is engaged, enforcing {sensor.name} from {format(value)} to 0 {sensor.unit}.")
                                        value=0

                                    # Store the value in Domoticz.
                                    # Some devices need multiple values, we will supply them.
                                    if unit[Column.PREPEND_IDNUM]:
                                        prepend = Devices[unit[Column.PREPEND_IDNUM]].sValue
                                        sValue = unit[Column.FORMAT].format(prepend, value)
                                    else:
                                        sValue = unit[Column.FORMAT].format(value)
                                    Domoticz.Debug("Update value = {}".format(sValue))

                                    # Store the value when changed.
                                    if sValue != Devices[unit[Column.IDNUM]].sValue:
                                        Devices[unit[Column.IDNUM]].Update(nValue=0, sValue=str(sValue), TimedOut=0)
                                        updated += 1

                                    device_count += 1
                        else:
                            # Suppress device not found logs for singlephase model, as these are expected to be not present
                            if unit[Column.FOR3PHASEMODEL]==False or self.inverterIs3PhaseModel==True:
                                Domoticz.Debug(f"Device '{unit[Column.MODBUSNAME]}' not found.")

                    Domoticz.Log("Updated {} values out of {}".format(updated, device_count))
                else:
                    Domoticz.Log("Inverter returned no information")

        # Try to contact the inverter
        else:
            self.readFromInverter()


    
    # Contact the inverter and find out if its a 3 phase or singlephase inverter    
    def readFromInverter(self):
        # Backoff from the inverter when it did not respond in the previous attempt to contact it.
        if self.lastconnectfailuretime==None or millis() - self.lastconnectfailuretime>self.retrydelay:
            runtime_data = None
            try:
                if self.inverter==None:
                    if self.connectToInverter()==False:
                         raise ConnectionException("Unable to contact inverter")
                runtime_data=asyncio.run( self.inverter.read_runtime_data() )
                if runtime_data==None:
                    raise ConnectionException("Unable read data from inverter")
                self.lastconnectfailuretime=None
            except ConnectionException as e:
                # There are multiple reasons why this may fail.
                # - The inverter is in sleepmode
                # - Perhaps the ip address or port are incorrect.
                # - The inverter may not be connected to the network,
                # - The inverter may be turned off.
                # - The inverter has a bad dhcpday.                
                # Try again in the future. Remember the time of the faillure.

                self.lastconnectfailuretime=millis()
                runtime_data = None

                Domoticz.Log("Connection Exception \"{}\" when trying to contact: {}:{}".format(e.string, Parameters["Address"], Parameters["Port"]))
                Domoticz.Log("Retrying to communicate with inverter after: {} sec.".format(self.retrydelay/1000.0))

            else:
                if runtime_data:
                    Domoticz.Log("Connection established with: {}:{}".format(Parameters["Address"], Parameters["Port"]))
 
                    # Find out if its a 3 phase or single phase model.
                    if self.inverter:
                        self.InverterIs3PhaseModel=False
                        # We have 2 ways of 3 phase determination: 
                        # 1: A fixed series list, named: THREEPHASE_SERIES 
                        # 2: Look into the modbus data for known 3 phase values and decide on that
                        # In the future we might add a 3rd way, by model name, if needed.
                        for iSerie in THREEPHASE_SERIES: # Iterate through our lookup table THREEPHASE_SERIES and see if the model name ends with our known 3 phase serie names
                            if self.inverter.model_name.endswith(f"-{iSerie}"):
                                self.InverterIs3PhaseModel=True
                                break
                        if self.InverterIs3PhaseModel==False:
                            for unit in INVERTER_PARAMS:
                                if unit[Column.FOR3PHASEMODEL]==True:
                                    if unit[Column.MODBUSNAME] in runtime_data.keys() and abs(runtime_data[unit[Column.MODBUSNAME]])>0.1:
                                        self.InverterIs3PhaseModel=True
                                        break

                        # Add devices if enabled and if needed.
                        if self.add_devices:
                            for sensor in self.inverter.sensors():
                                if sensor.id_ in runtime_data:                        
                                    if sensor.id_ not in Devices:
                                        for unit in INVERTER_PARAMS:
                                            if unit[Column.MODBUSNAME]==sensor.id_:
                                                value = runtime_data[unit[Column.MODBUSNAME]]

                                                # If the value is for the 3 phase model only and the inverter is single phase, then do not add the value to Domoticz as that would be useless and take up space that is just waste.
                                                if self.inverterIs3PhaseModel==False and unit[Column.FOR3PHASEMODEL]==True:
                                                    Domoticz.Debug(f"Single phase model detected. Not creating Domoticz device for {sensor.name} value {format(value)} {sensor.unit}.")
                                                    continue

                                                Domoticz.Device(
                                                    Unit=unit[Column.IDNUM],
                                                    Name=unit[Column.DISPLAYNAME],
                                                    Type=unit[Column.TYPE],
                                                    Subtype=unit[Column.SUBTYPE],
                                                    Switchtype=unit[Column.SWITCHTYPE],
                                                    Options=unit[Column.OPTIONS],
                                                    Used=1,
                                                ).Create()

                else:
                    Domoticz.Log("Connection established with: {}:{}. Inverter returned no information".format(Parameters["Address"], Parameters["Port"]))
                    Domoticz.Log("Retrying to communicate with inverter after: {}".format(millis() - self.lastconnectfailuretime + self.retrydelay))
        else:
            Domoticz.Log("Retrying to communicate with inverter after: {} sec.".format( (self.retrydelay - (millis() - self.lastconnectfailuretime)) / 1000.0))


# Instantiate the plugin and register the supported callbacks.
global _plugin
_plugin = BasePlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()




#DEBUG Domoticz plugin when developing offsite without Domoticz in place
if __name__ == '__main__':
    onStart()
    while (1):
        time.sleep(1)
        onHeartbeat()

