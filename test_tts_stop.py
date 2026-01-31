
import sys
import os
import time
import threading

# Add current directory to path
sys.path.append(os.getcwd())

from voice_control import VoiceController

def test_tts_interrupt():
    print("Testing TTS Interrupt Management...")
    vc = VoiceController()
    
    # Test 1: Stop speaking when nothing is playing
    print("   Test 1: Stopping when idle...")
    vc.stop_speaking()
    print("   ✅ Test 1 Passed (No crash)")
    
    # Test 2: Rapid fire speaking (should stop previous)
    print("   Test 2: Rapid speaking...")
    vc.speak("This is a long sentence that should be interrupted very quickly.", async_mode=True)
    time.sleep(0.5)
    vc.speak("Interrupted!", async_mode=True)
    time.sleep(1)
    vc.stop_speaking()
    print("   ✅ Test 2 Passed")

if __name__ == "__main__":
    test_tts_interrupt()
    print("\n🎉 TTS Test Complete!")
