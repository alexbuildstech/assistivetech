import sys
import os
import numpy as np

def test_syntax():
    print("Testing syntax of main_enhanced.py...")
    try:
        import main_enhanced
        print("✅ main_enhanced.py imported successfully (Syntax OK)")
    except ImportError:
        # It might fail to import dependencies, but we care about SyntaxError
        pass
    except SyntaxError as e:
        print(f"❌ SyntaxError in main_enhanced.py: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"⚠️ Import error (expected if dependencies missing): {e}")

def test_audio_ola():
    print("\nTesting Audio Overlap-Add Logic...")
    try:
        from audio_hrtf import HRTF_AudioController
        
        # Mock config
        import config
        config.AUDIO_SIGNATURES = {"test": {"waveform": "sine", "freq": 440}}
        
        controller = HRTF_AudioController()
        
        # Add a source
        controller.update_source("obj1", 0, 0, 1.0, "test")
        
        # Generate a few chunks
        chunk1 = controller._generate_audio_chunk(2048)
        print(f"✅ Chunk 1 generated. Shape: {chunk1.shape}, Max: {np.max(np.abs(chunk1))}")
        
        chunk2 = controller._generate_audio_chunk(2048)
        print(f"✅ Chunk 2 generated. Shape: {chunk2.shape}")
        
        if controller.tails:
            print(f"✅ Tail buffer active (OLA working). Tails: {len(controller.tails)}")
        else:
            print("⚠️ No tail buffer found (OLA might not be active or needed for this signal)")
            
    except Exception as e:
        print(f"❌ Audio test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    test_syntax()
    test_audio_ola()
