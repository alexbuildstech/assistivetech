print("--- RUNNING THE DEFINITIVE, LIBRARY-COMPLIANT VERSION ---")

import sounddevice as sd
import numpy as np
import soundfile as sf
import time
import slab

# --- Configuration ---
AUDIO_FILE_PATH = 'soothing.wav'
BUFFER_SIZE = 1024
ROTATION_SPEED = 15
ELEVATION_OSCILLATION_SPEED = 0.2
MAX_ELEVATION = 40

# --- Real-time Audio Processor Class ---
class RealtimeSpatialize:
    def __init__(self, audio_file_path):
        # Load the HRTF data. This object is a collection of filters.
        self.hrtf = slab.HRTF.kemar()
        samplerate = self.hrtf.samplerate
        
        # Load and prepare the audio file.
        try:
            sound_data, original_sr = sf.read(audio_file_path, dtype='float32')
        except FileNotFoundError:
            print(f"Error: Audio file not found at '{audio_file_path}'")
            exit()
        except Exception as e:
            print(f"Error reading sound file: {e}")
            exit()

        sound_obj = slab.Sound(sound_data, samplerate=original_sr)

        # Resample and convert to mono if necessary.
        if original_sr != samplerate:
            print(f"Resampling audio from {original_sr} Hz to {samplerate} Hz...")
            sound_obj = sound_obj.resample(samplerate)
        
        if sound_obj.n_channels > 1:
            self.mono_sound_data = sound_obj.channel(0).data.flatten()
        else:
            self.mono_sound_data = sound_obj.data.flatten()

        if len(self.mono_sound_data) == 0:
            print("CRITICAL ERROR: Audio file loaded but contains no data.")
            exit()

        self.samplerate = samplerate
        self.azimuth = 0.0
        self.elevation = 0.0
        self.current_frame = 0

    def set_position(self, azimuth, elevation):
        self.azimuth = azimuth
        self.elevation = elevation

    def audio_callback(self, outdata, frames, time, status):
        if status:
            print(status)
        try:
            # 1. Get the next chunk of mono audio.
            sound_len = len(self.mono_sound_data)
            indices = (self.current_frame + np.arange(frames)) % sound_len
            chunk_mono_data = self.mono_sound_data[indices]
            self.current_frame = (self.current_frame + frames) % sound_len
            
            chunk_sound_obj = slab.Sound(chunk_mono_data, samplerate=self.samplerate)

            # 2. --- THE CORRECT METHOD ---
            # Use the library's built-in function to find the index of the closest source.
            # This replaces the manual nearest-neighbor calculation.
            closest_source_index = self.hrtf.cone_sources(self.azimuth, self.elevation)[0]
            
            # 3. Select the specific filter from the HRTF bank using the found index.
            fir_filter = self.hrtf[closest_source_index]
            
            # 4. Apply that filter to the sound chunk.
            filtered_chunk = fir_filter.apply(chunk_sound_obj)
            
            # 5. Write the resulting stereo data to the output buffer.
            output_len = min(frames, filtered_chunk.n_samples)
            outdata[:output_len] = filtered_chunk.data[:output_len, :]
            
            if output_len < frames:
                outdata[output_len:] = 0

        except Exception as e:
            print(f"\n--- EXCEPTION IN CALLBACK: {e} ---")
            outdata.fill(0)

def main():
    processor = RealtimeSpatialize(AUDIO_FILE_PATH)

    print("Starting continuous 3D audio experience...")
    print("Wear headphones for the best effect.")
    print("Press Ctrl+C to exit.")

    try:
        with sd.OutputStream(
            samplerate=processor.samplerate,
            blocksize=BUFFER_SIZE,
            channels=2,
            callback=processor.audio_callback
        ) as stream:
            start_time = time.time()
            while stream.active:
                elapsed_time = time.time() - start_time
                azimuth = (elapsed_time * ROTATION_SPEED) % 360
                elevation = MAX_ELEVATION * np.sin(elapsed_time * ELEVATION_OSCILLATION_SPEED)
                processor.set_position(azimuth, elevation)
                print(f"Azimuth: {azimuth:5.1f}°, Elevation: {elevation:5.1f}°   ", end='\r')
                time.sleep(0.02)

    except KeyboardInterrupt:
        print("\nStopping audio stream. Goodbye!")
    except Exception as e:
        print(f"\nAn error occurred: {e}")

if __name__ == '__main__':
    main()