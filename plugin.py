#!/usr/bin/env python
"""
Cupra Born
"""
"""
<plugin key="CupraBorn" name="Cupra Born" author="Joerek van Gaalen" version="1.0.0">
    <params>
        <param field="Username" label="WeConnect Username" width="200px" required="true"/>
        <param field="Password" label="WeConnect Password" width="200px" required="true" password="true"/>
        <param field="Mode1" label="Service (WeConnect or MyCupra)" width="100px" required="true" default="MyCupra"/>
        <param field="Mode2" label="Update Interval (seconds)" width="75px" required="true" default="60"/>
    </params>
</plugin>
"""

import Domoticz
from weconnect_cupra import weconnect_cupra
from weconnect_cupra.service import Service
from weconnect_cupra.api.cupra.elements.enums import UnlockPlugState, MaximumChargeCurrent
from weconnect_cupra.api.cupra.elements.charging_status import ChargingStatus
from weconnect_cupra.elements.control_operation import ControlOperation

# import json

def GetDomoDeviceInfo(DID):
    for x in Devices:
        if Devices[x].DeviceID == str(DID):
            return x
    return False

def FreeUnit():
    for x in range(1, 256):
        if x not in Devices:
            return x
    return len(Devices) + 1

class BasePlugin:
    enabled = False

    def __init__(self):
        self.weconnect = None

    def onStart(self):
        Domoticz.Log("Cupra Born Status Plugin started")

        # Initialize WeConnect client
        try:
            service = Service(Parameters["Mode1"])
            self.weconnect = weconnect_cupra.WeConnect(
                username=Parameters["Username"],
                password=Parameters["Password"],
                service=service,
                updateAfterLogin=False,
                loginOnInit=False
            )
            self.weconnect.login()
            Domoticz.Log("Successfully connected to WeConnect API")
        except Exception as e:
            Domoticz.Error(f"Failed to connect to WeConnect API: {e}")

        # Immediately update status after successful connection
        self.updateStatus()

        Domoticz.Heartbeat(int(Parameters["Mode2"]))

    def onStop(self):
        Domoticz.Log("Cupra Born Status Plugin stopped")

    def onHeartbeat(self):
        self.updateStatus()

    def createDevices(self, vin):
        device_definitions = [
            {"Name": "Charge", "TypeName": "Switch", "Switchtype": 0},
            {"Name": "Battery Level", "Type": 243, "Subtype": 6},
            {"Name": "Charging State", "TypeName": "Text"},
            {"Name": "Slow charge", "TypeName": "Switch", "Switchtype": 0},
            {"Name": "Auto Unlock Plug When Charged", "TypeName": "Switch"},
            {"Name": "Target SOC", "Type": 244, "Subtype": 62, "Switchtype": 18, "Options": {"LevelActions": "||||||||||", "LevelNames": "0|10|20|30|40|50|60|70|80|90|100", "LevelOffHidden": "false", "SelectorStyle": "1"}},
            {"Name": "Charge Power", "Type": 243, "Subtype": 31, "Options": {"Custom": "1;Watt"}},
            {"Name": "Cruising Range Electric", "TypeName": "Custom", "Options": {"Custom": "1;km"}},
            {"Name": "Plug Connection State", "TypeName": "Switch"},
            {"Name": "Plug Lock State", "TypeName": "Text"},
            {"Name": "External Power", "TypeName": "Text"},
            {"Name": "Climatisation State", "TypeName": "Text"},
            {"Name": "Climatisation", "TypeName": "Switch", "Switchtype": 0},
            {"Name": "Target Temperature", "Type": 242, "Subtype": 1, "Options":{'ValueStep':'0.5', ' ValueMin':'16', 'ValueMax':'30', 'ValueUnit':'°C'}},
            {"Name": "Remaining Charging Time", "TypeName": "Custom", "Options": {"Custom": "1;min"}},
            {"Name": "Charge Rate", "TypeName": "Custom", "Options": {"Custom": "1;km/h"}}
        ]

        for device in device_definitions:
            device_id = f"{vin}_{device['Name'].replace(' ', '_')}"
            if not GetDomoDeviceInfo(device_id):
                unit_id = FreeUnit()
                device_params = {
                    "Name": f"{vin} - {device['Name']}",
                    "Unit": unit_id,
                    "DeviceID": device_id
                }

                if "Type" in device:
                    device_params["Type"] = device["Type"]
                if "Subtype" in device:
                    device_params["Subtype"] = device["Subtype"]
                if "TypeName" in device:
                    device_params["TypeName"] = device["TypeName"]
                if "Switchtype" in device:
                    device_params["Switchtype"] = device["Switchtype"]
                if "Options" in device:
                    device_params["Options"] = device["Options"]

                Domoticz.Device(**device_params).Create()

    def updateStatus(self):
        if self.weconnect:
            try:
                self.weconnect.update()

                for vin, vehicle in self.weconnect.vehicles.items():

                    # vehicle_data = vehicle.toJSON()

                    # # Print the full vehicle data to console
                    # print(json.dumps(vehicle_data, indent=4))

                    # # Log the full vehicle data in Domoticz
                    # Domoticz.Log("Vehicle data: " + json.dumps(vehicle_data, indent=4))

                    self.createDevices(vin)
                    # Extract and log specific status data
                    battery_status = vehicle.domains['charging']['batteryStatus']
                    battery_level = battery_status.currentSOC_pct.value
                    charging_status = vehicle.domains['charging']['chargingStatus']
                    charging_state = charging_status.chargingState
                    charging_settings = vehicle.domains['charging']['chargingSettings']
                    max_charge_current_ac = charging_settings.maxChargeCurrentAC
                    auto_unlock_plug_when_charged = charging_settings.autoUnlockPlugWhenCharged
                    target_soc_pct = round(charging_settings.targetSOC_pct.value)
                    charge_power = charging_status.chargePower_kW.value * 1000
                    cruising_range_electric = battery_status.cruisingRangeElectric_km.value
                    remaining_charging_time = charging_status.remainingChargingTimeToComplete_min.value
                    charge_rate = charging_status.chargeRate_kmph.value
                    plug_status = vehicle.domains['charging']['plugStatus']
                    plug_connection_state = plug_status.plugConnectionState
                    plug_lock_state = plug_status.plugLockState
                    external_power = plug_status.externalPower
                    climatisation_status = vehicle.domains['climatisation']['climatisationStatus']
                    climatisation_state = climatisation_status.climatisationState
                    climatisation_settings = vehicle.domains['climatisation']['climatisationSettings']
                    target_temperature_c = climatisation_settings.targetTemperature_C.value

                    # Debug print all values to the console
                    # Domoticz.Log(f"VIN: {vin}")
                    # Domoticz.Log(f"Battery Level: {battery_level}%")
                    # Domoticz.Log(f"Charging State: {charging_state}")
                    # Domoticz.Log(f"Max Charge Current AC: {max_charge_current_ac}")
                    # Domoticz.Log(f"Auto Unlock Plug When Charged: {auto_unlock_plug_when_charged}")
                    # Domoticz.Log(f"Target SOC: {target_soc_pct}%")
                    # Domoticz.Log(f"Charge Power: {charge_power} Watts")
                    # Domoticz.Log(f"Cruising Range Electric: {cruising_range_electric} km")
                    # Domoticz.Log(f"Remaining Charging Time: {remaining_charging_time} minutes")
                    # Domoticz.Log(f"Charge Rate: {charge_rate} km/h")
                    # Domoticz.Log(f"Plug Connection State: {plug_connection_state}")
                    # Domoticz.Log(f"Plug Lock State: {plug_lock_state}")
                    # Domoticz.Log(f"External Power: {external_power}")
                    # Domoticz.Log(f"Climatisation State: {climatisation_state}")
                    # Domoticz.Log(f"Target Temperature: {target_temperature_c} °C")

                    # Update Domoticz devices
                    def update_device(device_id, nValue, sValue):
                        unit = GetDomoDeviceInfo(device_id)
                        if unit:
                            Devices[unit].Update(nValue=nValue, sValue=sValue)

                    update_device(f"{vin}_Battery_Level", nValue=int(battery_level), sValue=str(battery_level))
                    update_device(f"{vin}_Cruising_Range_Electric", nValue=0, sValue=str(cruising_range_electric))
                    if Devices[GetDomoDeviceInfo(f"{vin}_Charging_State")].sValue != str(charging_state):
                        update_device(f"{vin}_Charging_State", nValue=0, sValue=str(charging_state))
                        if Devices[GetDomoDeviceInfo(f"{vin}_Charge")].sValue != ('On' if str(charging_state) == 'charging' else 'Off'):
                            update_device(f"{vin}_Charge",
                                          nValue=1 if str(charging_state) == 'charging' else 0,
                                          sValue='On' if str(charging_state) == 'charging' else 'Off')
                    if Devices[GetDomoDeviceInfo(f"{vin}_Slow_charge")].sValue != ('On' if max_charge_current_ac == 'reduced' else 'Off'):
                        update_device(f"{vin}_Slow_charge",
                                      nValue=1 if max_charge_current_ac == 'reduced' else 0,
                                      sValue='On' if max_charge_current_ac == 'reduced' else 'Off')
                    if Devices[GetDomoDeviceInfo(f"{vin}_Auto_Unlock_Plug_When_Charged")].sValue != ('On' if str(auto_unlock_plug_when_charged) == 'permanent' else 'Off'):
                        update_device(f"{vin}_Auto_Unlock_Plug_When_Charged",
                                      nValue=1 if str(auto_unlock_plug_when_charged) == 'permanent' else 0,
                                      sValue='On' if str(auto_unlock_plug_when_charged) == 'permanent' else 'Off')
                    if Devices[GetDomoDeviceInfo(f"{vin}_Target_SOC")].sValue != str(target_soc_pct):
                        if int(target_soc_pct) == 0:
                            nv = 0
                        else:
                            nv = 2
                        update_device(f"{vin}_Target_SOC", nValue=nv, sValue=str(target_soc_pct))
                    if Devices[GetDomoDeviceInfo(f"{vin}_Charge_Power")].sValue != str(charge_power):
                        update_device(f"{vin}_Charge_Power", nValue=0, sValue=str(charge_power))
                    if Devices[GetDomoDeviceInfo(f"{vin}_Remaining_Charging_Time")].sValue != str(remaining_charging_time):
                        update_device(f"{vin}_Remaining_Charging_Time", nValue=0, sValue=str(remaining_charging_time))
                    if Devices[GetDomoDeviceInfo(f"{vin}_Charge_Rate")].sValue != str(charge_rate):
                        update_device(f"{vin}_Charge_Rate", nValue=0, sValue=str(charge_rate))
                    if Devices[GetDomoDeviceInfo(f"{vin}_Plug_Connection_State")].sValue != ('On' if str(plug_connection_state) == 'connected' else 'Off'):
                        update_device(f"{vin}_Plug_Connection_State",
                                      nValue=1 if str(plug_connection_state) == 'connected' else 0,
                                      sValue='On' if str(plug_connection_state) == 'connected' else 'Off')
                    if Devices[GetDomoDeviceInfo(f"{vin}_Plug_Lock_State")].sValue != str(plug_lock_state):
                        update_device(f"{vin}_Plug_Lock_State", nValue=0, sValue=str(plug_lock_state))
                    if Devices[GetDomoDeviceInfo(f"{vin}_External_Power")].sValue != str(external_power):
                        update_device(f"{vin}_External_Power", nValue=0, sValue=str(external_power))
                    if Devices[GetDomoDeviceInfo(f"{vin}_Climatisation_State")].sValue != str(climatisation_state):
                        update_device(f"{vin}_Climatisation_State", nValue=0, sValue=str(climatisation_state))
                        if Devices[GetDomoDeviceInfo(f"{vin}_Climatisation")].sValue != ('Off' if str(climatisation_state) == 'off' else 'On'):
                            update_device(f"{vin}_Climatisation",
                                          nValue=0 if str(climatisation_state) == 'off' else 1,
                                          sValue='Off' if str(climatisation_state) == 'off' else 'On')
                    if Devices[GetDomoDeviceInfo(f"{vin}_Target_Temperature")].sValue != str(target_temperature_c):
                        update_device(f"{vin}_Target_Temperature", nValue=0, sValue=str(target_temperature_c))

            except Exception as e:
                Domoticz.Error(f"Error updating car status: {e}")

    def onCommand(self, Unit, Command, Level, Hue):
        Domoticz.Log(f"onCommand called for Unit {Unit}: Command {Command}, Level {Level}")

        for vin, vehicle in self.weconnect.vehicles.items():
            device_id_charge = f"{vin}_Charge"
            device_id_soc = f"{vin}_Target_SOC"
            device_id_current = f"{vin}_Slow_charge"
            device_id_auto_unlock = f"{vin}_Auto_Unlock_Plug_When_Charged"
            device_id_climatisation = f"{vin}_Climatisation"
            device_id_target_temperature = f"{vin}_Target_Temperature"

            if GetDomoDeviceInfo(device_id_charge) == Unit:
                self.setCharge(vehicle, Unit, Command)
                break
            elif GetDomoDeviceInfo(device_id_soc) == Unit:
                self.setTargetSOC(vehicle, Unit, Level)
                break
            elif GetDomoDeviceInfo(device_id_current) == Unit:
                self.setMaxChargeCurrentAC(vehicle, Unit, Command)
                break
            elif GetDomoDeviceInfo(device_id_auto_unlock) == Unit:
                self.setAutoUnlockPlugWhenCharged(vehicle, Unit, Command)
                break
            elif GetDomoDeviceInfo(device_id_climatisation) == Unit:
                self.setClimatisation(vehicle, Unit, Command)
                break
            elif GetDomoDeviceInfo(device_id_target_temperature) == Unit:
                self.setTargetTemperature(vehicle, Unit, Level)
                break

    def setCharge(self, vehicle, Unit, Command):
        if vehicle.controls.chargingControl is not None and vehicle.controls.chargingControl.enabled:
            try:
                command = ControlOperation.START if Command == 'On' else ControlOperation.STOP
                vehicle.controls.chargingControl.value = ControlOperation(value=command)
                Domoticz.Log("Charging set successfully")
                # Update the device status in Domoticz
                # nValue = 1 if Command == 'On' else 0
                # Devices[Unit].Update(nValue=nValue, sValue=Command)
            except Exception as e:
                Domoticz.Error(f"Failed to enable charging: {e}")
        else:
            Domoticz.Error("Charging not supported or not enabled for this vehicle")

    def setTargetSOC(self, vehicle, Unit, Level):
        if 'charging' in vehicle.domains \
                and vehicle.domains['charging']["chargingSettings"].enabled \
                and vehicle.domains['charging']["chargingSettings"].targetSOC_pct.enabled:
            Domoticz.Log(f"Setting target SOC to {Level}%")
            try:
                vehicle.domains['charging']["chargingSettings"].targetSOC_pct.value = float(Level)
                Domoticz.Log("Target SOC set successfully")
                # Update the device status in Domoticz
                # Devices[Unit].Update(nValue=2, sValue=str(Level))
            except Exception as e:
                Domoticz.Error(f"Failed to set target SOC: {e}")
        else:
            Domoticz.Error("Target SOC settings not supported or not enabled for this vehicle")

    def setMaxChargeCurrentAC(self, vehicle, Unit, Command):
        if 'charging' in vehicle.domains \
                and vehicle.domains['charging']["chargingSettings"].enabled \
                and vehicle.domains['charging']["chargingSettings"].maxChargeCurrentAC.enabled:
            Domoticz.Log(f"Setting Max Charge Current AC to {'reduced' if Command == 'On' else 'maximum'} ({Command})")
            try:
                value = MaximumChargeCurrent.REDUCED if Command == 'On' else MaximumChargeCurrent.MAXIMUM
                vehicle.domains['charging']["chargingSettings"].maxChargeCurrentAC.value = value
                Domoticz.Log("Max Charge Current AC set successfully")
                # Update the device status in Domoticz
                # nValue = 1 if Command == 'On' else 0
                # Devices[Unit].Update(nValue=nValue, sValue=Command)
            except Exception as e:
                Domoticz.Error(f"Failed to set Max Charge Current AC: {e}")
        else:
            Domoticz.Error("Max Charge Current AC settings not supported or not enabled for this vehicle")

    def setAutoUnlockPlugWhenCharged(self, vehicle, Unit, Command):
        if 'charging' in vehicle.domains \
                and vehicle.domains['charging']["chargingSettings"].enabled \
                and vehicle.domains['charging']["chargingSettings"].autoUnlockPlugWhenCharged.enabled:
            Domoticz.Log(f"Setting Auto Unlock Plug When Charged to {'permanent' if Command == 'On' else 'off'}")
            try:
                value = UnlockPlugState.PERMANENT if Command == 'On' else UnlockPlugState.OFF
                vehicle.domains['charging']["chargingSettings"].autoUnlockPlugWhenCharged.value = value
                Domoticz.Log("Auto Unlock Plug When Charged set successfully")
                # Update the device status in Domoticz
                # nValue = 1 if Command == 'On' else 0
                # Devices[Unit].Update(nValue=nValue, sValue=Command)
            except Exception as e:
                Domoticz.Error(f"Failed to set Auto Unlock Plug When Charged: {e}")
        else:
            Domoticz.Error("Auto Unlock Plug When Charged settings not supported or not enabled for this vehicle")

    def setClimatisation(self, vehicle, Unit, Command):
        if vehicle.controls.climatizationControl is not None and vehicle.controls.climatizationControl.enabled:
            try:
                command = ControlOperation.START if Command == 'On' else ControlOperation.STOP
                vehicle.controls.climatizationControl.value = ControlOperation(value=command)
                Domoticz.Log("Climatisation set successfully")

                # Update the device status in Domoticz
                # nValue = 1 if Command == 'On' else 0
                # Devices[Unit].Update(nValue=nValue, sValue=Command)
            except Exception as e:
                Domoticz.Error(f"Failed to enable charging: {e}")
        else:
            Domoticz.Error("Charging not supported or not enabled for this vehicle")

    def setTargetTemperature(self, vehicle, Unit, Level):
        if Level > 10 and float(Level) != vehicle.domains["climatisation"]["climatisationSettings"].targetTemperatureInCelsius.value:
            try:
                vehicle.domains["climatisation"]["climatisationSettings"].targetTemperatureInCelsius.value = float(Level)
                Domoticz.Log("Climatisation temperature set successfully")
            except Exception as e:
                Domoticz.Error(f"Failed to set target temperature: {e}")
        else:
            Domoticz.Error("Target temperature not supported or not enabled for this vehicle")

global _plugin
_plugin = BasePlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

def onCommand(Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Hue)
