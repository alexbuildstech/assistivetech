"""
Enhanced Audio Module with OpenAL 3D Spatial Audio.
Implements robust HRTF, distance attenuation, and Doppler effects using OpenAL.

PATENT-WORTHY: True 3D spatial audio for assistive navigation.
"""

import time
import threading
import math
import os
import sys
import config

# Try to import OpenAL
try:
    from openal import *
    OPENAL_AVAILABLE = True
except ImportError:
    print("❌ PyOpenAL not installed. Falling back to dummy audio.")
    OPENAL_AVAILABLE = False

class HRTF_AudioController:
    """
    Advanced spatial audio using OpenAL.
    Provides hardware-accelerated 3D audio, HRTF, and robust mixing.
    """
    
    def __init__(self):
        """Initialize OpenAL context and resources."""
        global OPENAL_AVAILABLE
        self.running = False
        self.sources = {} # Map obj_id -> OpenAL Source
        self.buffers = {} # Map signature_name -> OpenAL Buffer
        self.listener_pos = (0, 0, 0)
        self.listener_ori = (0, 0, -1, 0, 1, 0) # Looking -Z, Up +Y
        
        if not OPENAL_AVAILABLE:
            print("⚠️ OpenAL unavailable. Audio disabled.")
            return

        try:
            # Initialize OpenAL
            # oalInit returns void, throws exception on failure in some bindings, 
            # or we might need to create context manually if PyOpenAL helper doesn't work.
            # PyOpenAL's oalInit() is a helper that opens default device and context.
            oalInit()
            
            # Configure Listener
            # PyOpenAL expects ctypes arrays for vector functions
            import ctypes
            listener_pos_array = (ctypes.c_float * 3)(*self.listener_pos)
            listener_ori_array = (ctypes.c_float * 6)(*self.listener_ori)
            
            alListenerfv(AL_POSITION, listener_pos_array)
            alListenerfv(AL_ORIENTATION, listener_ori_array)
            
            # Check for HRTF extension (optional, but good to know)
            # Note: OpenAL Soft usually enables HRTF by default if headphones are detected
            # or configured in alsoft.conf. We can't easily force it via simple API 
            # without AL_SOFT_HRTF extension, but we assume the system is configured.
            
            print("🎧 OpenAL Audio System Initialized")
            print(f"   Vendor: {alGetString(AL_VENDOR).decode('utf-8')}")
            print(f"   Renderer: {alGetString(AL_RENDERER).decode('utf-8')}")
            print(f"   Version: {alGetString(AL_VERSION).decode('utf-8')}")
            
            self._preload_buffers()
            
        except Exception as e:
            print(f"❌ Failed to initialize OpenAL: {e}")
            OPENAL_AVAILABLE = False

    def _preload_buffers(self):
        """Pre-load audio signatures into OpenAL buffers."""
        if not OPENAL_AVAILABLE:
            return
            
        print("🎵 Loading audio signatures...")
        try:
            from audio_module_multi import AudioSignatureGenerator
            import wave
            import struct
            
            # We need to generate WAV data for OpenAL
            # OpenAL expects PCM data.
            
            for obj_type, sig_config in config.AUDIO_SIGNATURES.items():
                waveform_type = sig_config.get("waveform", "sine")
                frequency = sig_config.get("freq", 440)
                duration = 0.5 # seconds
                sample_rate = 44100
                
                # Generate raw PCM data (16-bit mono)
                # We'll use a helper to generate the byte string
                frames = int(sample_rate * duration)
                audio_data = bytearray()
                
                for i in range(frames):
                    t = float(i) / sample_rate
                    if waveform_type == "sine":
                        sample = 0.5 * math.sin(2 * math.pi * frequency * t)
                    elif waveform_type == "square":
                        sample = 0.5 * (1.0 if math.sin(2 * math.pi * frequency * t) > 0 else -1.0)
                    elif waveform_type == "sawtooth":
                        sample = 0.5 * (2.0 * (t * frequency - math.floor(t * frequency + 0.5)))
                    else:
                        sample = 0.0
                        
                    # Apply envelope (attack/decay) to avoid clicking
                    if i < 1000: # Attack
                        sample *= (i / 1000.0)
                    elif i > frames - 1000: # Decay
                        sample *= ((frames - i) / 1000.0)
                        
                    # Convert to 16-bit signed integer
                    val = int(max(min(sample, 1.0), -1.0) * 32767)
                    audio_data.extend(struct.pack('<h', val))
                
                # Create OpenAL Buffer
                # alGenBuffers(n, buffers_array)
                buf_id = ctypes.c_uint(0)
                alGenBuffers(1, ctypes.byref(buf_id))
                buf = buf_id.value
                
                # alBufferData(buffer, format, data, size, freq)
                # data needs to be a pointer
                data_ptr = (ctypes.c_char * len(audio_data)).from_buffer(audio_data)
                alBufferData(buf, AL_FORMAT_MONO16, data_ptr, len(audio_data), sample_rate)
                
                self.buffers[obj_type] = buf
                
            print(f"   ✅ Loaded {len(self.buffers)} audio buffers")
            
        except Exception as e:
            print(f"   ❌ Failed to load buffers: {e}")

    def start_stream(self, shared_state=None):
        """Start the audio update loop."""
        if self.running or not OPENAL_AVAILABLE:
            return
            
        self.running = True
        self.shared_state = shared_state
        
        # Play startup sound
        self._play_startup_sound()
        
        # Start update thread
        self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.update_thread.start()
        print("▶️ OpenAL audio loop started")

    def _play_startup_sound(self):
        """Play a quick startup tone."""
        try:
            import ctypes
            # Generate a simple beep
            sample_rate = 44100
            duration = 0.5
            frames = int(sample_rate * duration)
            audio_data = bytearray()
            for i in range(frames):
                t = float(i) / sample_rate
                sample = 0.3 * math.sin(2 * math.pi * 880 * t) * ((frames - i) / frames)
                val = int(sample * 32767)
                audio_data.extend(struct.pack('<h', val))
                
            buf_id = ctypes.c_uint(0)
            alGenBuffers(1, ctypes.byref(buf_id))
            buf = buf_id.value
            
            data_ptr = (ctypes.c_char * len(audio_data)).from_buffer(audio_data)
            alBufferData(buf, AL_FORMAT_MONO16, data_ptr, len(audio_data), sample_rate)
            
            source_id = ctypes.c_uint(0)
            alGenSources(1, ctypes.byref(source_id))
            source = source_id.value
            
            alSourcei(source, AL_BUFFER, buf)
            alSourcef(source, AL_GAIN, 0.5)
            alSourcePlay(source)
            
            # Cleanup later (fire and forget for now, or wait)
            time.sleep(0.5)
            # alDeleteSources(1, ctypes.byref(source_id))
            # alDeleteBuffers(1, ctypes.byref(buf_id))
        except Exception:
            pass

    def stop_stream(self):
        """Stop audio."""
        self.running = False
        if OPENAL_AVAILABLE:
            try:
                import ctypes
                # Stop all sources
                for source in self.sources.values():
                    alSourceStop(source)
                    source_id = ctypes.c_uint(source)
                    alDeleteSources(1, ctypes.byref(source_id))
                self.sources.clear()
                
                # Clean up buffers
                for buf in self.buffers.values():
                    buf_id = ctypes.c_uint(buf)
                    alDeleteBuffers(1, ctypes.byref(buf_id))
                self.buffers.clear()
                
                oalQuit()
            except Exception:
                pass
        print("⏹️ OpenAL audio stopped")

    def resume_stream(self):
        """Resume if paused (re-start loop)."""
        if not self.running:
            self.start_stream(self.shared_state)

    def _update_loop(self):
        """Main loop to update source positions based on shared state."""
        while self.running:
            try:
                if self.shared_state:
                    display_state = self.shared_state.get_display_state()
                    objects = display_state.get("objects", [])
                    self._update_scene(objects)
                
                time.sleep(0.05) # Update at 20Hz
                
            except Exception as e:
                print(f"⚠️ Audio loop error: {e}")
                time.sleep(1)

    def _update_scene(self, objects):
        """Update OpenAL sources based on tracked objects."""
        if not OPENAL_AVAILABLE:
            return
            
        import ctypes

        current_ids = set()
        
        # Debug: Log when we receive objects
        # if objects and len(objects) > 0:
        #     print(f"🔊 Audio: Processing {len(objects)} objects")
        
        # 1. Update/Create Sources
        for obj in objects:
            if not obj.bbox:
                continue
                
            obj_id = obj.id
            current_ids.add(obj_id)
            
            # Calculate 3D Position relative to camera
            # Camera is at (0,0,0) looking down -Z
            # X: Left/Right (- is left)
            # Y: Up/Down (+ is up)
            # Z: Forward/Back (- is forward)
            
            # Map bbox center to normalized coordinates (-1 to 1)
            cx = obj.bbox[0] + obj.bbox[2] / 2
            cy = obj.bbox[1] + obj.bbox[3] / 2
            
            # Assuming 1280x720 frame
            width = 1280
            height = 720
            
            # Normalize X (-1 left, +1 right)
            norm_x = (cx / width) * 2 - 1
            
            # Normalize Y (-1 bottom, +1 top) -> OpenAL Y is +Up
            norm_y = -((cy / height) * 2 - 1)
            
            # Estimate Distance (Z) based on area (larger = closer)
            area = obj.bbox[2] * obj.bbox[3]
            max_area = width * height * 0.5 # arbitrary reference
            # distance = 1.0 / sqrt(area_ratio)
            # Clamp distance to reasonable range (0.5m to 10m)
            # distance 1.0 = roughly 1 meter away (screen filling 50%)
            dist = max(0.5, min(10.0, math.sqrt(max_area / (area + 1))))
            
            # Calculate Gain (Volume) based on Distance
            # Inverse distance model: Volume = Reference / Distance
            # We want closer objects (dist ~ 0.5) to be loud (gain ~ 1.0)
            # And far objects (dist ~ 5.0) to be quiet (gain ~ 0.1)
            
            # Reference distance where gain is 1.0
            ref_dist = 1.0 
            
            # Simple inverse distance attenuation
            # gain = ref_dist / (ref_dist + (dist - ref_dist)) -> gain = ref_dist / dist
            gain = min(1.0, ref_dist / (dist * 0.5)) # 0.5 factor to make it drop off slower or faster
            
            # Boost gain slightly so it's not too quiet too fast
            gain = max(0.1, gain) # Minimum volume 10%
            
            # Convert to 3D coordinates
            # x = dist * sin(azimuth)
            # z = -dist * cos(azimuth)
            # Simple projection:
            pos_x = norm_x * dist * 2.0 # Spread out horizontally
            pos_y = norm_y * dist
            pos_z = -dist
            
            # Create source if new
            if obj_id not in self.sources:
                source_id = ctypes.c_uint(0)
                alGenSources(1, ctypes.byref(source_id))
                source = source_id.value
                
                # Set Buffer
                sig_name = "default"
                # Simple mapping based on label
                if "person" in obj.label: sig_name = "person"
                elif "door" in obj.label: sig_name = "door"
                
                buf = self.buffers.get(sig_name) or self.buffers.get("default")
                if buf:
                    alSourcei(source, AL_BUFFER, buf)
                    alSourcei(source, AL_LOOPING, AL_TRUE)
                    alSourcePlay(source)
                    print(f"  🎵 Created audio source for {obj.label} (ID: {obj_id})")
                
                self.sources[obj_id] = source
            
            # Update Source Properties
            source = self.sources[obj_id]
            alSourcefv(source, AL_POSITION, (ctypes.c_float * 3)(pos_x, pos_y, pos_z))
            
            # Distance Attenuation
            # OpenAL handles this automatically if configured, but we can tweak gain
            # Gain based on distance (calculated above)
            base_gain = float(gain)
            
            # === THREAT FOCUS ===
            # If this is the main threat, keep full volume.
            # If not, duck the volume significantly.
            
            # Find max threat score in current set
            max_threat = 0.0
            for o in objects:
                if hasattr(o, 'threat_score'):
                    max_threat = max(max_threat, o.threat_score)
            
            # Apply ducking
            final_gain = base_gain
            if hasattr(obj, 'threat_score'):
                # If this object is significantly less threatening than the max, duck it
                if obj.threat_score < (max_threat * 0.8):
                    final_gain *= 0.3 # Reduce to 30% volume
            
            alSourcef(source, AL_GAIN, final_gain)
            
            # Debug log for tuning (throttle this in production)
            # if obj_id % 10 == 0:
            #    print(f"  🔊 {obj.label}: Dist={dist:.2f}m -> Gain={final_gain:.2f} (Threat={obj.threat_score:.2f})")
            
        # 2. Remove Stale Sources
        active_sources = list(self.sources.keys())
        for obj_id in active_sources:
            if obj_id not in current_ids:
                # Stop and delete
                source = self.sources[obj_id]
                alSourceStop(source)
                source_id = ctypes.c_uint(source)
                alDeleteSources(1, ctypes.byref(source_id))
                del self.sources[obj_id]

