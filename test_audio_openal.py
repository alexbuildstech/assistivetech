import time
import sys
import os

def test_openal():
    print("🧪 Testing OpenAL Audio Controller...")
    
    try:
        # Mock config
        import config
        config.AUDIO_SIGNATURES = {"test": {"waveform": "sine", "freq": 440}}
        
        from audio_hrtf import HRTF_AudioController, OPENAL_AVAILABLE
        
        if not OPENAL_AVAILABLE:
            print("❌ OpenAL not available (Import failed)")
            sys.exit(1)
            
        controller = HRTF_AudioController()
        
        if not controller.running and not controller.sources:
             # Just init check
             pass
             
        print("✅ OpenAL Initialized")
        
        # Start stream
        controller.start_stream()
        print("✅ Stream started")
        
        # Add a source (simulate object)
        class MockObject:
            def __init__(self, id, x, y, w, h, label):
                self.id = id
                self.bbox = (x, y, w, h)
                self.label = label
                
        # Object 1: Left
        obj1 = MockObject(1, 0, 300, 100, 100, "person")
        controller._update_scene([obj1])
        print("✅ Added source 1 (Left)")
        time.sleep(1)
        
        # Object 1: Move Right
        obj1.bbox = (1000, 300, 100, 100)
        controller._update_scene([obj1])
        print("✅ Moved source 1 (Right)")
        time.sleep(1)
        
        # Stop
        controller.stop_stream()
        print("✅ Stream stopped")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    test_openal()
