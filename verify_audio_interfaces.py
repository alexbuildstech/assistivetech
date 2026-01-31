
import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

from audio_hrtf import HRTF_AudioController
from audio_module_multi import MultiAudioController

def verify_interfaces():
    required_methods = [
        "start_stream",
        "stop_stream",
        "pause_stream",
        "resume_stream"
    ]
    
    controllers = [
        ("HRTF", HRTF_AudioController),
        ("MultiAudio", MultiAudioController)
    ]
    
    all_ok = True
    for name, cls in controllers:
        print(f"Checking {name} Controller:")
        for method in required_methods:
            has_method = hasattr(cls, method)
            status = "✅" if has_method else "❌"
            print(f"  {status} {method}")
            if not has_method:
                all_ok = False
                
    if all_ok:
        print("\n🎉 All audio interfaces are unified!")
    else:
        print("\n❌ Interface mismatch detected!")
        sys.exit(1)

if __name__ == "__main__":
    verify_interfaces()
