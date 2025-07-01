#!/usr/bin/env python
"""
Cupra Born
"""
"""
<plugin key="CupraBorn" name="Cupra Born" author="Joerek van Gaalen" version="2.0.0">
    <params>
        <param field="Username" label="WeConnect Username" width="200px" required="true"/>
        <param field="Password" label="WeConnect Password" width="200px" required="true" password="true"/>
        <param field="Mode1" label="Service (WeConnect or MyCupra)" width="100px" required="true" default="MyCupra"/>
        <param field="Mode2" label="Update Interval (seconds)" width="75px" required="true" default="300"/>
        <param field="Mode3" label="Max Retries" width="75px" required="true" default="3"/>
        <param field="Mode4" label="Rate Limit Delay (seconds)" width="75px" required="true" default="2"/>
        <param field="Mode5" label="Debug Level" width="75px" required="true" default="Normal">
            <options>
                <option label="Normal" value="Normal"/>
                <option label="Verbose" value="Verbose"/>
                <option label="Debug" value="Debug"/>
            </options>
        </param>
    </params>
</plugin>
"""

import Domoticz
import time
import threading
import queue
from datetime import datetime, timedelta
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

class RateLimiter:
    def __init__(self, min_interval=2.0):
        self.min_interval = min_interval
        self.last_request_time = 0
        self.lock = threading.Lock()
    
    def wait_if_needed(self):
        with self.lock:
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            if time_since_last < self.min_interval:
                sleep_time = self.min_interval - time_since_last
                time.sleep(sleep_time)
            self.last_request_time = time.time()

class RetryHandler:
    def __init__(self, max_retries=3, base_delay=1.0, max_delay=60.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
    
    def execute_with_retry(self, func, *args, **kwargs):
        """Execute function with exponential backoff retry logic"""
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == self.max_retries:
                    raise e
                
                # Check if it's a rate limiting error
                if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
                    status_code = e.response.status_code
                    if status_code == 429:  # Too Many Requests
                        delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                        Domoticz.Log(f"Rate limited (HTTP 429), retrying in {delay} seconds... (attempt {attempt + 1}/{self.max_retries + 1})")
                        time.sleep(delay)
                        continue
                    elif status_code in [500, 502, 503, 504]:  # Server errors
                        delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                        Domoticz.Log(f"Server error (HTTP {status_code}), retrying in {delay} seconds... (attempt {attempt + 1}/{self.max_retries + 1})")
                        time.sleep(delay)
                        continue
                
                # For other errors, still retry with exponential backoff
                delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                Domoticz.Log(f"Error occurred: {str(e)}, retrying in {delay} seconds... (attempt {attempt + 1}/{self.max_retries + 1})")
                time.sleep(delay)
        
        raise Exception(f"Failed after {self.max_retries + 1} attempts")

class BasePlugin:
    enabled = False

    def __init__(self):
        self.weconnect = None
        self.worker_thread = None
        self.stop_event = threading.Event()
        self.command_queue = queue.Queue()
        self.rate_limiter = None
        self.retry_handler = None
        self.last_successful_update = None
        self.consecutive_failures = 0
        self.max_consecutive_failures = 5
        self.update_interval = 300  # Default 5 minutes
        self.debug_level = "Normal"

    def onStart(self):
        Domoticz.Log("Cupra Born Status Plugin v2.0.0 started")
        
        # Parse parameters
        self.update_interval = int(Parameters.get("Mode2", "300"))
        max_retries = int(Parameters.get("Mode3", "3"))
        rate_limit_delay = float(Parameters.get("Mode4", "2"))
        self.debug_level = Parameters.get("Mode5", "Normal")
        
        # Initialize rate limiter and retry handler
        self.rate_limiter = RateLimiter(min_interval=rate_limit_delay)
        self.retry_handler = RetryHandler(max_retries=max_retries)
        
        # Set debug level
        if self.debug_level == "Debug":
            Domoticz.Debugging(1)
        elif self.debug_level == "Verbose":
            Domoticz.Debugging(2)
        
        self.log_debug("Starting with parameters:")
        self.log_debug(f"Update interval: {self.update_interval} seconds")
        self.log_debug(f"Max retries: {max_retries}")
        self.log_debug(f"Rate limit delay: {rate_limit_delay} seconds")
        
        # Start worker thread
        self.stop_event.clear()
        self.worker_thread = threading.Thread(target=self.worker_loop, daemon=True)
        self.worker_thread.start()
        
        # Set heartbeat for monitoring
        Domoticz.Heartbeat(60)  # Check every minute

    def onStop(self):
        Domoticz.Log("Cupra Born Status Plugin stopping")
        
        # Signal worker thread to stop
        self.stop_event.set()
        
        # Wait for worker thread to finish
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=10)
            if self.worker_thread.is_alive():
                Domoticz.Error("Worker thread did not stop gracefully")
        
        Domoticz.Log("Cupra Born Status Plugin stopped")

    def onHeartbeat(self):
        # Monitor worker thread health
        if self.worker_thread and not self.worker_thread.is_alive():
            Domoticz.Error("Worker thread has ended unexpectedly, restarting...")
            self.restart_worker_thread()
        
        # Check for too many consecutive failures
        if self.consecutive_failures >= self.max_consecutive_failures:
            Domoticz.Error(f"Too many consecutive failures ({self.consecutive_failures}), restarting connection...")
            self.restart_connection()

    def log_debug(self, message):
        if self.debug_level in ["Debug", "Verbose"]:
            Domoticz.Log(f"DEBUG: {message}")

    def restart_worker_thread(self):
        """Restart the worker thread"""
        try:
            self.stop_event.set()
            if self.worker_thread and self.worker_thread.is_alive():
                self.worker_thread.join(timeout=5)
            
            self.stop_event.clear()
            self.worker_thread = threading.Thread(target=self.worker_loop, daemon=True)
            self.worker_thread.start()
            Domoticz.Log("Worker thread restarted successfully")
        except Exception as e:
            Domoticz.Error(f"Failed to restart worker thread: {e}")

    def restart_connection(self):
        """Restart the WeConnect connection"""
        try:
            self.weconnect = None
            self.consecutive_failures = 0
            Domoticz.Log("Connection restart initiated")
        except Exception as e:
            Domoticz.Error(f"Failed to restart connection: {e}")

    def worker_loop(self):
        """Main worker thread loop"""
        Domoticz.Log("Worker thread started")
        
        while not self.stop_event.is_set():
            try:
                # Initialize connection if needed
                if self.weconnect is None:
                    self.initialize_connection()
                
                # Process any pending commands
                self.process_commands()
                
                # Update status
                self.update_status()
                
                # Wait for next update or stop signal
                if self.stop_event.wait(timeout=self.update_interval):
                    break  # Stop signal received
                    
            except Exception as e:
                self.consecutive_failures += 1
                Domoticz.Error(f"Error in worker loop: {e}")
                
                # Wait before retrying
                retry_delay = min(30 * self.consecutive_failures, 300)  # Max 5 minutes
                self.log_debug(f"Waiting {retry_delay} seconds before retry...")
                if self.stop_event.wait(timeout=retry_delay):
                    break
        
        Domoticz.Log("Worker thread stopped")

    def initialize_connection(self):
        """Initialize WeConnect connection with retry logic"""
        try:
            def _connect():
                service = Service(Parameters["Mode1"])
                weconnect = weconnect_cupra.WeConnect(
                    username=Parameters["Username"],
                    password=Parameters["Password"],
                    service=service,
                    updateAfterLogin=False,
                    loginOnInit=False
                )
                
                # Apply rate limiting
                self.rate_limiter.wait_if_needed()
                weconnect.login()
                return weconnect
            
            self.weconnect = self.retry_handler.execute_with_retry(_connect)
            Domoticz.Log("Successfully connected to WeConnect API")
            self.consecutive_failures = 0
            
        except Exception as e:
            Domoticz.Error(f"Failed to initialize WeConnect connection: {e}")
            self.weconnect = None
            raise

    def process_commands(self):
        """Process any pending commands from the queue"""
        try:
            while not self.command_queue.empty():
                command = self.command_queue.get_nowait()
                self.execute_command(command)
                self.command_queue.task_done()
        except queue.Empty:
            pass
        except Exception as e:
            Domoticz.Error(f"Error processing commands: {e}")

    def execute_command(self, command):
        """Execute a vehicle command with retry logic"""
        try:
            def _execute():
                self.rate_limiter.wait_if_needed()
                return command()
            
            self.retry_handler.execute_with_retry(_execute)
            self.log_debug("Command executed successfully")
            
        except Exception as e:
            Domoticz.Error(f"Failed to execute command: {e}")

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

    def update_status(self):
        """Update vehicle status with improved error handling"""
        if not self.weconnect:
            self.log_debug("WeConnect not initialized, skipping update")
            return

        try:
            def _update():
                self.rate_limiter.wait_if_needed()
                self.weconnect.update()
            
            self.retry_handler.execute_with_retry(_update)
            
            for vin, vehicle in self.weconnect.vehicles.items():
                self.log_debug(f"Updating status for vehicle: {vin}")
                self.createDevices(vin)
                self.update_vehicle_data(vin, vehicle)
            
            self.last_successful_update = datetime.now()
            self.consecutive_failures = 0
            self.log_debug("Status update completed successfully")
            
        except Exception as e:
            self.consecutive_failures += 1
            Domoticz.Error(f"Error updating car status: {e}")
            
            # If we have too many failures, reset connection
            if self.consecutive_failures >= self.max_consecutive_failures:
                self.weconnect = None

    def update_vehicle_data(self, vin, vehicle):
        """Update individual vehicle data with error handling"""
        try:
            # Extract vehicle data with error handling for each field
            data = self.extract_vehicle_data(vehicle)
            
            # Update Domoticz devices
            self.update_devices(vin, data)
            
        except Exception as e:
            Domoticz.Error(f"Error updating vehicle data for {vin}: {e}")

    def extract_vehicle_data(self, vehicle):
        """Safely extract vehicle data with error handling"""
        data = {}
        
        try:
            # Battery status
            if 'charging' in vehicle.domains and 'batteryStatus' in vehicle.domains['charging']:
                battery_status = vehicle.domains['charging']['batteryStatus']
                data['battery_level'] = getattr(battery_status.currentSOC_pct, 'value', None)
                data['cruising_range_electric'] = getattr(battery_status.cruisingRangeElectric_km, 'value', None)
        except Exception as e:
            self.log_debug(f"Error extracting battery status: {e}")

        try:
            # Charging status
            if 'charging' in vehicle.domains and 'chargingStatus' in vehicle.domains['charging']:
                charging_status = vehicle.domains['charging']['chargingStatus']
                data['charging_state'] = getattr(charging_status, 'chargingState', None)
                data['charge_power'] = getattr(charging_status.chargePower_kW, 'value', 0) * 1000 if hasattr(charging_status, 'chargePower_kW') else 0
                data['remaining_charging_time'] = getattr(charging_status.remainingChargingTimeToComplete_min, 'value', None)
                data['charge_rate'] = getattr(charging_status.chargeRate_kmph, 'value', None)
        except Exception as e:
            self.log_debug(f"Error extracting charging status: {e}")

        try:
            # Charging settings
            if 'charging' in vehicle.domains and 'chargingSettings' in vehicle.domains['charging']:
                charging_settings = vehicle.domains['charging']['chargingSettings']
                data['max_charge_current_ac'] = getattr(charging_settings, 'maxChargeCurrentAC', None)
                data['auto_unlock_plug_when_charged'] = getattr(charging_settings, 'autoUnlockPlugWhenCharged', None)
                data['target_soc_pct'] = round(getattr(charging_settings.targetSOC_pct, 'value', 0))
        except Exception as e:
            self.log_debug(f"Error extracting charging settings: {e}")

        try:
            # Plug status
            if 'charging' in vehicle.domains and 'plugStatus' in vehicle.domains['charging']:
                plug_status = vehicle.domains['charging']['plugStatus']
                data['plug_connection_state'] = getattr(plug_status, 'plugConnectionState', None)
                data['plug_lock_state'] = getattr(plug_status, 'plugLockState', None)
                data['external_power'] = getattr(plug_status, 'externalPower', None)
        except Exception as e:
            self.log_debug(f"Error extracting plug status: {e}")

        try:
            # Climatisation status
            if 'climatisation' in vehicle.domains and 'climatisationStatus' in vehicle.domains['climatisation']:
                climatisation_status = vehicle.domains['climatisation']['climatisationStatus']
                data['climatisation_state'] = getattr(climatisation_status, 'climatisationState', None)
        except Exception as e:
            self.log_debug(f"Error extracting climatisation status: {e}")

        try:
            # Climatisation settings
            if 'climatisation' in vehicle.domains and 'climatisationSettings' in vehicle.domains['climatisation']:
                climatisation_settings = vehicle.domains['climatisation']['climatisationSettings']
                data['target_temperature_c'] = getattr(climatisation_settings.targetTemperature_C, 'value', None)
        except Exception as e:
            self.log_debug(f"Error extracting climatisation settings: {e}")

        return data

    def update_devices(self, vin, data):
        """Update Domoticz devices with extracted data"""
        def update_device(device_id, nValue, sValue):
            unit = GetDomoDeviceInfo(device_id)
            if unit:
                try:
                    Devices[unit].Update(nValue=nValue, sValue=sValue)
                except Exception as e:
                    self.log_debug(f"Error updating device {device_id}: {e}")

        # Update devices with safe value extraction
        if data.get('battery_level') is not None:
            update_device(f"{vin}_Battery_Level", int(data['battery_level']), str(data['battery_level']))

        if data.get('cruising_range_electric') is not None:
            update_device(f"{vin}_Cruising_Range_Electric", 0, str(data['cruising_range_electric']))

        if data.get('charging_state') is not None:
            current_state = Devices[GetDomoDeviceInfo(f"{vin}_Charging_State")].sValue if GetDomoDeviceInfo(f"{vin}_Charging_State") else ""
            if current_state != str(data['charging_state']):
                update_device(f"{vin}_Charging_State", 0, str(data['charging_state']))
                
                # Update charge switch based on charging state
                charge_on = str(data['charging_state']) == 'charging'
                current_charge = Devices[GetDomoDeviceInfo(f"{vin}_Charge")].sValue if GetDomoDeviceInfo(f"{vin}_Charge") else ""
                if current_charge != ('On' if charge_on else 'Off'):
                    update_device(f"{vin}_Charge", 1 if charge_on else 0, 'On' if charge_on else 'Off')

        # Continue with other device updates...
        if data.get('max_charge_current_ac') is not None:
            slow_charge = data['max_charge_current_ac'] == 'reduced'
            current_slow = Devices[GetDomoDeviceInfo(f"{vin}_Slow_charge")].sValue if GetDomoDeviceInfo(f"{vin}_Slow_charge") else ""
            if current_slow != ('On' if slow_charge else 'Off'):
                update_device(f"{vin}_Slow_charge", 1 if slow_charge else 0, 'On' if slow_charge else 'Off')

        if data.get('auto_unlock_plug_when_charged') is not None:
            auto_unlock = str(data['auto_unlock_plug_when_charged']) == 'permanent'
            current_unlock = Devices[GetDomoDeviceInfo(f"{vin}_Auto_Unlock_Plug_When_Charged")].sValue if GetDomoDeviceInfo(f"{vin}_Auto_Unlock_Plug_When_Charged") else ""
            if current_unlock != ('On' if auto_unlock else 'Off'):
                update_device(f"{vin}_Auto_Unlock_Plug_When_Charged", 1 if auto_unlock else 0, 'On' if auto_unlock else 'Off')

        if data.get('target_soc_pct') is not None:
            current_soc = Devices[GetDomoDeviceInfo(f"{vin}_Target_SOC")].sValue if GetDomoDeviceInfo(f"{vin}_Target_SOC") else ""
            if current_soc != str(data['target_soc_pct']):
                nv = 0 if int(data['target_soc_pct']) == 0 else 2
                update_device(f"{vin}_Target_SOC", nv, str(data['target_soc_pct']))

        if data.get('charge_power') is not None:
            current_power = Devices[GetDomoDeviceInfo(f"{vin}_Charge_Power")].sValue if GetDomoDeviceInfo(f"{vin}_Charge_Power") else ""
            if current_power != str(data['charge_power']):
                update_device(f"{vin}_Charge_Power", 0, str(data['charge_power']))

        if data.get('remaining_charging_time') is not None:
            current_time = Devices[GetDomoDeviceInfo(f"{vin}_Remaining_Charging_Time")].sValue if GetDomoDeviceInfo(f"{vin}_Remaining_Charging_Time") else ""
            if current_time != str(data['remaining_charging_time']):
                update_device(f"{vin}_Remaining_Charging_Time", 0, str(data['remaining_charging_time']))

        if data.get('charge_rate') is not None:
            current_rate = Devices[GetDomoDeviceInfo(f"{vin}_Charge_Rate")].sValue if GetDomoDeviceInfo(f"{vin}_Charge_Rate") else ""
            if current_rate != str(data['charge_rate']):
                update_device(f"{vin}_Charge_Rate", 0, str(data['charge_rate']))

        if data.get('plug_connection_state') is not None:
            plug_connected = str(data['plug_connection_state']) == 'connected'
            current_plug = Devices[GetDomoDeviceInfo(f"{vin}_Plug_Connection_State")].sValue if GetDomoDeviceInfo(f"{vin}_Plug_Connection_State") else ""
            if current_plug != ('On' if plug_connected else 'Off'):
                update_device(f"{vin}_Plug_Connection_State", 1 if plug_connected else 0, 'On' if plug_connected else 'Off')

        if data.get('plug_lock_state') is not None:
            current_lock = Devices[GetDomoDeviceInfo(f"{vin}_Plug_Lock_State")].sValue if GetDomoDeviceInfo(f"{vin}_Plug_Lock_State") else ""
            if current_lock != str(data['plug_lock_state']):
                update_device(f"{vin}_Plug_Lock_State", 0, str(data['plug_lock_state']))

        if data.get('external_power') is not None:
            current_power = Devices[GetDomoDeviceInfo(f"{vin}_External_Power")].sValue if GetDomoDeviceInfo(f"{vin}_External_Power") else ""
            if current_power != str(data['external_power']):
                update_device(f"{vin}_External_Power", 0, str(data['external_power']))

        if data.get('climatisation_state') is not None:
            current_clim_state = Devices[GetDomoDeviceInfo(f"{vin}_Climatisation_State")].sValue if GetDomoDeviceInfo(f"{vin}_Climatisation_State") else ""
            if current_clim_state != str(data['climatisation_state']):
                update_device(f"{vin}_Climatisation_State", 0, str(data['climatisation_state']))
                
                # Update climatisation switch
                clim_on = str(data['climatisation_state']) != 'off'
                current_clim = Devices[GetDomoDeviceInfo(f"{vin}_Climatisation")].sValue if GetDomoDeviceInfo(f"{vin}_Climatisation") else ""
                if current_clim != ('On' if clim_on else 'Off'):
                    update_device(f"{vin}_Climatisation", 1 if clim_on else 0, 'On' if clim_on else 'Off')

        if data.get('target_temperature_c') is not None:
            current_temp = Devices[GetDomoDeviceInfo(f"{vin}_Target_Temperature")].sValue if GetDomoDeviceInfo(f"{vin}_Target_Temperature") else ""
            if current_temp != str(data['target_temperature_c']):
                update_device(f"{vin}_Target_Temperature", 0, str(data['target_temperature_c']))

    def onCommand(self, Unit, Command, Level, Hue):
        Domoticz.Log(f"onCommand called for Unit {Unit}: Command {Command}, Level {Level}")

        # Queue the command for execution in the worker thread
        for vin, vehicle in (self.weconnect.vehicles.items() if self.weconnect else []):
            device_id_charge = f"{vin}_Charge"
            device_id_soc = f"{vin}_Target_SOC"
            device_id_current = f"{vin}_Slow_charge"
            device_id_auto_unlock = f"{vin}_Auto_Unlock_Plug_When_Charged"
            device_id_climatisation = f"{vin}_Climatisation"
            device_id_target_temperature = f"{vin}_Target_Temperature"

            if GetDomoDeviceInfo(device_id_charge) == Unit:
                self.command_queue.put(lambda: self.setCharge(vehicle, Unit, Command))
                break
            elif GetDomoDeviceInfo(device_id_soc) == Unit:
                self.command_queue.put(lambda: self.setTargetSOC(vehicle, Unit, Level))
                break
            elif GetDomoDeviceInfo(device_id_current) == Unit:
                self.command_queue.put(lambda: self.setMaxChargeCurrentAC(vehicle, Unit, Command))
                break
            elif GetDomoDeviceInfo(device_id_auto_unlock) == Unit:
                self.command_queue.put(lambda: self.setAutoUnlockPlugWhenCharged(vehicle, Unit, Command))
                break
            elif GetDomoDeviceInfo(device_id_climatisation) == Unit:
                self.command_queue.put(lambda: self.setClimatisation(vehicle, Unit, Command))
                break
            elif GetDomoDeviceInfo(device_id_target_temperature) == Unit:
                self.command_queue.put(lambda: self.setTargetTemperature(vehicle, Unit, Level))
                break

    def setCharge(self, vehicle, Unit, Command):
        if vehicle.controls.chargingControl is not None and vehicle.controls.chargingControl.enabled:
            try:
                command = ControlOperation.START if Command == 'On' else ControlOperation.STOP
                vehicle.controls.chargingControl.value = ControlOperation(value=command)
                Domoticz.Log("Charging set successfully")
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
            except Exception as e:
                Domoticz.Error(f"Failed to enable climatisation: {e}")
        else:
            Domoticz.Error("Climatisation not supported or not enabled for this vehicle")

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
