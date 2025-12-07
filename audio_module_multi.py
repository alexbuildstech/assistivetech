"""
Enhanced Audio Controller with Multi-Object Support.
Generates unique audio signatures for different object types.
"""

import numpy as np
import sounddevice as sd
import threading
import config
from typing import List, Dict

class AudioSignatureGenerator:
    """Generates unique audio waveforms for different object types."""
    
    @staticmethod
    def generate_waveform(waveform_type, frequency, duration, sample_rate):
        """
        Generate a waveform of given type.
        
        Args:
            waveform_type: "sine", "square", "sawtooth", "pulse"
            frequency: Frequency in Hz
            duration: Duration in seconds
            sample_rate: Sample rate in Hz
        
        Returns:
            numpy array of audio samples
        """
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        
        if waveform_type == "sine":
            wave = np.sin(2 * np.pi * frequency * t)
        
        elif waveform_type == "square":
            wave = np.sign(np.sin(2 * np.pi * frequency * t))
        
        elif waveform_type == "sawtooth":
            wave = 2 * (t * frequency - np.floor(0.5 + t * frequency))
        
        elif waveform_type == "pulse":
            # Heartbeat-like pulse
            pulse_freq = frequency / 60  # Convert BPM to Hz
            wave = np.zeros_like(t)
            pulse_indices = (t * pulse_freq) % 1.0 < 0.1
            wave[pulse_indices] = np.sin(2 * np.pi * 10 * t[pulse_indices])
        
        else:
            wave = np.sin(2 * np.pi * frequency * t)
        
        # Normalize
        if wave.max() > 0:
            wave = wave / wave.max()
        
        # Apply fade in/out
        fade_samples = int(0.01 * sample_rate)
        if len(wave) > 2 * fade_samples:
            wave[:fade_samples] *= np.linspace(0, 1, fade_samples)
            wave[-fade_samples:] *= np.linspace(1, 0, fade_samples)
        
        return wave.astype(np.float32)


class MultiAudioController:
    """
    Advanced audio controller supporting multiple simultaneous spatial audio sources.
    Each source can have a unique audio signature.
    """
    
    def __init__(self):
        """Initialize multi-audio controller."""
        self.sample_rate = config.SAMPLE_RATE
        self.buffer_size = config.AUDIO_BUFFER_SIZE
        
        # Audio signatures cache
        self.signatures = {}
        self._preload_signatures()
        
        # Active audio sources: {object_id: {azimuth, volume, signature_name, position}}
        self.sources = {}
        self.sources_lock = threading.Lock()
        
        #Streaming
        self.stream = None
        self.running = False
        
        print(f"🔊 Multi-AudioController initialized | Sample Rate: {self.sample_rate} Hz")
    
    def _preload_signatures(self):
        """Pre-generate audio signatures for all object types."""
        for obj_type, sig_config in config.AUDIO_SIGNATURES.items():
            waveform_type = sig_config.get("waveform", "sine")
            frequency = sig_config.get("freq", 440)
            
            # Generate 0.5 second signature
            signature = AudioSignatureGenerator.generate_waveform(
                waveform_type, frequency, 0.5, self.sample_rate
            )
            
            self.signatures[obj_type] = signature
            print(f"  ♪ Loaded signature: {obj_type} ({waveform_type} @ {frequency} Hz)")
    
    def _audio_callback(self, outdata, frames, time_info, status):
        """
        Callback for sounddevice stream - mixes multiple audio sources.
        """
        if status:
            print(f"Audio stream status: {status}")
        
        # Initialize output buffer
        left_channel = np.zeros(frames, dtype=np.float32)
        right_channel = np.zeros(frames, dtype=np.float32)
        
        # Mix all active sources
        with self.sources_lock:
            for obj_id, source_data in self.sources.items():
                azimuth = source_data.get("azimuth", 0)
                volume = source_data.get("volume", 0.5)
                signature_name = source_data.get("signature", "default")
                position = source_data.get("position", 0)
                
                # Get signature
                signature = self.signatures.get(signature_name, self.signatures["default"])
                
                # Calculate stereo pan
                pan = np.clip(azimuth / config.MAX_AZIMUTH_DEGREES, -1.0, 1.0)
                angle = (pan + 1.0) * np.pi / 4
                left_gain = np.cos(angle) * volume
                right_gain = np.sin(angle) * volume
                
                # Sample from signature (looping)
                samples = np.zeros(frames, dtype=np.float32)
                n_sig_samples = len(signature)
                
                for i in range(frames):
                    samples[i] = signature[position % n_sig_samples]
                    position += 1
                
                # Update position for next callback
                source_data["position"] = position
                
                # Mix into channels
                left_channel += samples * left_gain
                right_channel += samples * right_gain
        
        # Normalize to prevent clipping
        max_val = max(np.abs(left_channel).max(), np.abs(right_channel).max())
        if max_val > 1.0:
            left_channel /= max_val
            right_channel /= max_val
        
        # Output stereo
        outdata[:, 0] = left_channel
        outdata[:, 1] = right_channel
    
    def start(self):
        """Start the audio stream."""
        if self.running:
            print("⚠️ Audio stream already running.")
            return
        
        try:
            self.stream = sd.OutputStream(
                samplerate=self.sample_rate,
                channels=2,
                blocksize=self.buffer_size,
                callback=self._audio_callback
            )
            self.stream.start()
            self.running = True
            print("▶️ Multi-audio stream started.")
        
        except Exception as e:
            print(f"❌ Failed to start audio stream: {e}")
    
    def stop(self):
        """Stop the audio stream."""
        if not self.running:
            return
        
        try:
            self.stream.stop()
            self.stream.close()
            self.running = False
            print("⏹️ Multi-audio stream stopped.")
        
        except Exception as e:
            print(f"❌ Error stopping audio stream: {e}")
    
    def update_source(self, obj_id, azimuth, volume, signature_name="default"):
        """
        Update or add an audio source.
        
        Args:
            obj_id: Unique object identifier
            azimuth: Horizontal angle in degrees
            volume: Volume level 0.0-1.0
            signature_name: Audio signature type
        """
        with self.sources_lock:
            if obj_id not in self.sources:
                self.sources[obj_id] = {"position": 0}
            
            self.sources[obj_id].update({
                "azimuth": np.clip(azimuth, -config.MAX_AZIMUTH_DEGREES, config.MAX_AZIMUTH_DEGREES),
                "volume": np.clip(volume, 0.0, 1.0),
                "signature": signature_name
            })
    
    def remove_source(self, obj_id):
        """Remove an audio source."""
        with self.sources_lock:
            if obj_id in self.sources:
                del self.sources[obj_id]
    
    def clear_sources(self):
        """Clear all audio sources."""
        with self.sources_lock:
            self.sources.clear()
    
    # Backward compatibility
    def update_position(self, azimuth, elevation, volume):
        """Legacy single-object interface."""
        self.update_source(0, azimuth, volume, "phone")
