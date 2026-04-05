"""
Hardware Interface Module for Assistive Navigation.
Handles communication with Arduino Mega 2560 and external sensors (Pressure, etc.).
"""

try:
    import serial
    SerialException = serial.SerialException
except ImportError:
    serial = None
    SerialException = None

import threading
import time
import config


class HardwareInterface:
    def __init__(self):
        self.serial_port = config.SERIAL_PORT
        self.baud_rate = config.SERIAL_BAUD
        self.connection = None
        self.is_connected = False
        self.running = False
        self.thread = None
        self.sensor_data = {"pressure": 0, "battery_voltage": 0.0, "last_update": 0}
        self.data_lock = threading.Lock()
        self.connect()

    def connect(self):
        if not config.ENABLE_HARDWARE:
            print("[HARDWARE] Hardware disabled in config.")
            return False
        if serial is None:
            print("[HARDWARE] pyserial not installed. Hardware features unavailable.")
            self.is_connected = False
            self.connection = None
            return False
        try:
            self.connection = serial.Serial(self.serial_port, self.baud_rate, timeout=1)
            self.is_connected = True
            print(f"[HARDWARE] Connected to Arduino at {self.serial_port}")
            self.start_reading()
            return True
        except SerialException as e:
            print(f"[HARDWARE] Connection failed: {e}")
            self.is_connected = False
            self.connection = None
            return False
        except Exception as e:
            print(f"[HARDWARE] Unexpected connection error: {e}")
            self.is_connected = False
            self.connection = None
            return False

    def start_reading(self):
        if self.thread and self.thread.is_alive():
            return
        self.running = True
        self.thread = threading.Thread(target=self._read_worker, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        self.is_connected = False
        if self.connection:
            try:
                self.connection.close()
            except Exception:
                pass
            self.connection = None
        if self.thread and self.thread.is_alive() and self.thread is not threading.current_thread():
            self.thread.join(timeout=1.0)

    def _read_worker(self):
        while self.running and self.is_connected and self.connection:
            try:
                if self.connection.in_waiting > 0:
                    line = self.connection.readline().decode("utf-8", errors="ignore").strip()
                    self._parse_line(line)
                else:
                    time.sleep(0.01)
            except Exception as e:
                print(f"[HARDWARE] Read error: {e}")
                self.is_connected = False
                self.running = False
                if self.connection:
                    try:
                        self.connection.close()
                    except Exception:
                        pass
                    self.connection = None
                break

    def __del__(self):
        try:
            self.stop()
        except Exception:
            pass

    def _parse_line(self, line):
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
            pass

    def get_pressure(self):
        with self.data_lock:
            return self.sensor_data["pressure"]

    def send_feedback(self, intensity=0):
        if self.is_connected:
            try:
                msg = f"HAPTIC:{intensity}\n"
                self.connection.write(msg.encode("utf-8"))
            except Exception as e:
                print(f"[HARDWARE] Write error: {e}")


class DummyHardwareInterface:
    def get_pressure(self): return 0
    def send_feedback(self, i): pass
    def stop(self): pass
