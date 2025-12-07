import sounddevice as sd
import numpy as np
import time

print("🎧 Audio Diagnostic Tool")
print("========================")

# 1. List Devices
print("\n📋 Available Audio Devices:")
try:
    print(sd.query_devices())
except Exception as e:
    print(f"❌ Error querying devices: {e}")

# 2. Get Default Device
try:
    default_device = sd.default.device
    print(f"\n👉 Default Device Indices: {default_device}")
    device_info = sd.query_devices(default_device[1], 'output')
    print(f"   Name: {device_info['name']}")
    print(f"   Channels: {device_info['max_output_channels']}")
    print(f"   Sample Rate: {device_info['default_samplerate']}")
except Exception as e:
    print(f"❌ Error getting default device: {e}")

# 3. Generate Test Tone
print("\n🎵 Generating Test Tone (440Hz Sine Wave)...")
fs = 44100
duration = 2.0  # seconds
t = np.linspace(0, duration, int(fs * duration), False)
tone = 0.5 * np.sin(2 * np.pi * 440 * t)  # 0.5 amplitude

# 4. Play Tone
print("▶️ Playing tone...")
try:
    sd.play(tone, fs)
    sd.wait()
    print("✅ Playback finished.")
except Exception as e:
    print(f"❌ Playback failed: {e}")

print("\nDid you hear the tone?")
