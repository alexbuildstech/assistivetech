"""
Hardware Interface Module for Assistive Navigation.
Handles communication with Arduino Mega 2560 and external sensors (Pressure, etc.).
"""

import serial
import threading
import time
import config

class HardwareInterface:
    def __init__(self):
        """Initialize hardware interface."""
        self.serial_port = config.SERIAL_PORT
        self.baud_rate = config.SERIAL_BAUD
        self.connection = None
        self.is_connected = False
        self.running = False
        self.thread = None
        
        # Sensor Data Store
        self.sensor_data = {
            "pressure": 0,
            "battery_voltage": 0.0,
            "last_update": 0
        }
        self.data_lock = threading.Lock()
        
        # Connect immediately
        self.connect()
        
    def connect(self):
        """Attempt to connect to the Serial device."""
        if not config.ENABLE_HARDWARE:
            print("[HARDWARE] Hardware disabled in config.")
            return False
            
        try:
            self.connection = serial.Serial(
                self.serial_port, 
                self.baud_rate, 
                timeout=1
            )
            self.is_connected = True
            print(f"[HARDWARE] Connected to Arduino at {self.serial_port}")
            self.start_reading()
            return True
        except serial.SerialException as e:
            print(f"[HARDWARE] Connection failed: {e}")
            self.is_connected = False
            return False

    def start_reading(self):
        """Start the background reading thread."""
        self.running = True
        self.thread = threading.Thread(target=self._read_worker, daemon=True)
        self.thread.start()
        
    def stop(self):
        """Stop hardware interface."""
        self.running = False
        if self.connection:
            self.connection.close()
            
    def _read_worker(self):
        """Worker thread for reading serial data."""
        while self.running and self.is_connected:
            try:
                if self.connection.in_waiting > 0:
                    line = self.connection.readline().decode('utf-8').strip()
                    self._parse_line(line)
                else:
                    time.sleep(0.01)
            except Exception as e:
                print(f"[HARDWARE] Read error: {e}")
                self.is_connected = False
                # Simple reconnect logic could go here
                time.sleep(2)
                
    def _parse_line(self, line):
        """
        Parse raw serial line.
        Expected formats:
        - "PRESSURE:512"
        - "BATTERY:12.4"
        """
        try:
            if ":" in line:
                key, value = line.split(":", 1)
                
                with self.data_lock:
                    if key == "PRESSURE":
                        self.sensor_data["pressure"] = int(value)
                    elif key == "BATTERY":
                        self.sensor_data["battery_voltage"] = float(value)
                    
                    self.sensor_data["last_update"] = time.time()
                    
        except ValueError:
            pass # Malformed line

    def get_pressure(self):
        """Get the latest pressure reading."""
        with self.data_lock:
            return self.sensor_data["pressure"]
            
    def send_feedback(self, intensity=0):
        """Send haptic/motor command to Arduino."""
        if self.is_connected:
            try:
                msg = f"HAPTIC:{intensity}\n"
                self.connection.write(msg.encode('utf-8'))
            except Exception as e:
                print(f"[HARDWARE] Write error: {e}")

# Dummy interface for when hardware is missing/disabled
class DummyHardwareInterface:
    def get_pressure(self): return 0
    def send_feedback(self, i): pass
    def stop(self): pass
