
import sys
import os
import time
import asyncio
import threading

# Add current directory to path
sys.path.append(os.getcwd())

from voice_control import VoiceController

def measure_ttfw():
    print("🚀 Measuring Time To First Word (TTFW)...")
    vc = VoiceController()
    
    test_text = "This is a speed test for Nova's new streaming engine. It should start speaking almost immediately."
    
    start_time = time.time()
    
    print("📢 Sending text to speak()...")
    # This will use asyncio.run internally
    vc.speak(test_text, async_mode=False) 
    
    end_time = time.time()
    print(f"\n⏱️ Total streaming duration: {end_time - start_time:.2f}s")

if __name__ == "__main__":
    measure_ttfw()
