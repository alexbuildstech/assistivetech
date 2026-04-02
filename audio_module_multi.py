"""
Enhanced Audio Controller with Multi-Object Support - ULTRA LOW LATENCY VERSION.
Generates unique audio signatures for different object types.
Optimized for real-time performance with minimal allocations.
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
        """
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        
        if waveform_type == "sine":
            wave = np.sin(2 * np.pi * frequency * t)
        elif waveform_type == "square":
            wave = np.sign(np.sin(2 * np.pi * frequency * t))
        elif waveform_type == "sawtooth":
            wave = 2 * (t * frequency - np.floor(0.5 + t * frequency))
        elif waveform_type == "pulse":
            pulse_freq = frequency / 60
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
    Ultra-low latency audio controller supporting multiple simultaneous spatial audio sources.
    Optimized for real-time with pre-allocated buffers and minimal lock contention.
    """
    
    def __init__(self):
        """Initialize multi-audio controller."""
        self.sample_rate = config.SAMPLE_RATE
        self.buffer_size = config.AUDIO_BUFFER_SIZE
        
        # Audio signatures cache
        self.signatures = {}
        self._preload_signatures()
        
        # Active audio sources
        self.sources = {}
        self.sources_lock = threading.RLock()  # Reentrant for safety
        
        # Pre-allocated output buffers (avoid repeated allocations in callback)
        self._left_buffer = np.zeros(self.buffer_size, dtype=np.float32)
        self._right_buffer = np.zeros(self.buffer_size, dtype=np.float32)
        self._index_buffer = np.zeros(self.buffer_size, dtype=np.int32)
        
        # Stream
        self.stream = None
        self.running = False
        
        print(f"[AUDIO] Multi-AudioController initialized | Sample Rate: {self.sample_rate} Hz")
    
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
            print(f"  [AUDIO] Loaded signature: {obj_type} ({waveform_type} @ {frequency} Hz)")
    
    def _audio_callback(self, outdata, frames, time_info, status):
        """
        Ultra-low latency audio callback - minimal allocations, vectorized operations.
        """
        if status:
            print(f"Audio stream status: {status}")
        
        # Reset pre-allocated buffers (fast)
        self._left_buffer[:frames] = 0
        self._right_buffer[:frames] = 0
        
        # Quick check if any sources active (avoid lock if none)
        if not self.sources:
            outdata[:frames, 0] = self._left_buffer[:frames]
            outdata[:frames, 1] = self._right_buffer[:frames]
            return
        
        # Copy sources to local for lock-free processing
        with self.sources_lock:
            active_sources = list(self.sources.items())
        
        max_val = 0.0
        
        # Process each source
        for obj_id, source_data in active_sources:
            azimuth = source_data.get("azimuth", 0)
            volume = source_data.get("volume", 0.5)
            signature_name = source_data.get("signature", "default")
            position = source_data.get("position", 0)
            
            # Get signature
            signature = self.signatures.get(signature_name, self.signatures["default"])
            n_sig_samples = len(signature)
            
            # Vectorized sample extraction using pre-allocated index buffer
            # Create indices efficiently
            end_pos = position + frames
            if end_pos <= n_sig_samples:
                self._index_buffer[:frames] = np.arange(position, end_pos, dtype=np.int32)
            else:
                part1_len = n_sig_samples - position
                self._index_buffer[:part1_len] = np.arange(position, n_sig_samples, dtype=np.int32)
                self._index_buffer[part1_len:frames] = np.arange(0, frames - part1_len, dtype=np.int32)
            samples = signature[self._index_buffer[:frames]]
            
            # Update position (defer lock until after processing)
            new_position = int((position + frames) % n_sig_samples)
            source_data["position"] = new_position
            
            # Calculate stereo pan (optimized)
            pan = max(-1.0, min(1.0, azimuth / config.MAX_AZIMUTH_DEGREES))
            angle = (pan + 1.0) * 0.785398  # pi/4
            left_gain = np.cos(angle) * volume
            right_gain = np.sin(angle) * volume
            
            # Mix into buffers
            self._left_buffer[:frames] += samples * left_gain
            self._right_buffer[:frames] += samples * right_gain
            
            # Track max for normalization
            max_val = max(max_val, np.abs(self._left_buffer[:frames]).max(),
                         np.abs(self._right_buffer[:frames]).max())
        
        # Normalize if needed (single pass)
        if max_val > 1.0:
            self._left_buffer[:frames] /= max_val
            self._right_buffer[:frames] /= max_val
        
        # Output stereo (direct assignment)
        outdata[:frames, 0] = self._left_buffer[:frames]
        outdata[:frames, 1] = self._right_buffer[:frames]
    
    def start_stream(self, shared_state=None):
        """Start the audio stream."""
        if self.running:
            return True

        self.shared_state = shared_state

        try:
            # Use smaller buffer for lower latency
            buffer_size = min(512, self.buffer_size)  # Ultra-low latency

            self.stream = sd.OutputStream(
                samplerate=self.sample_rate,
                channels=2,
                blocksize=buffer_size,
                callback=self._audio_callback,
                latency='low'  # Explicit low latency mode
            )
            self.stream.start()
            self.running = True
            print(f"[AUDIO] Multi-audio stream started (buffer={buffer_size}, latency=low)")
            return True

        except Exception as e:
            self.stream = None
            self.running = False
            print(f"[ERROR] Failed to start audio stream: {e}")
            return False
    
    def pause_stream(self):
        """Pause the audio stream."""
        self.stop_stream()
        print("[AUDIO] Multi-audio stream paused.")

    def resume_stream(self):
        """Resume the audio stream."""
        if self.start_stream(self.shared_state):
            print("[AUDIO] Multi-audio stream resumed.")

    def stop_stream(self):
        """Stop the audio stream."""
        if not self.running:
            return
        
        try:
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None
            self.running = False
            print("[AUDIO] Multi-audio stream stopped.")
        
        except Exception as e:
            print(f"[ERROR] Error stopping audio stream: {e}")
    
    def update_source(self, obj_id, azimuth, volume, signature_name="default"):
        """Update or add an audio source."""
        with self.sources_lock:
            if obj_id not in self.sources:
                self.sources[obj_id] = {"position": 0}
            
            self.sources[obj_id].update({
                "azimuth": max(-config.MAX_AZIMUTH_DEGREES, 
                              min(config.MAX_AZIMUTH_DEGREES, azimuth)),
                "volume": max(0.0, min(1.0, volume)),
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
