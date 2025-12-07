import sys
import time
import threading
import cv2
import config
from shared_state import SharedGameState
from vision_module import VisionController
from audio_hrtf import HRTF_AudioController
from voice_control import VoiceController

def test_audio():
    print("\n🎧 Testing Audio...")
    try:
        audio = HRTF_AudioController()
        audio.start_stream()
        print("✅ Audio started. You should hear a startup sound.")
        time.sleep(2)
        audio.stop_stream()
        print("✅ Audio stopped.")
    except Exception as e:
        print(f"❌ Audio failed: {e}")

def test_camera():
    print("\n📷 Testing Camera...")
    try:
        vision = VisionController()
        ret, frame = vision.read_frame()
        if ret and frame is not None:
            print(f"✅ Frame captured: {frame.shape}")
        else:
            print("❌ Failed to capture frame")
        vision.release()
    except Exception as e:
        print(f"❌ Camera failed: {e}")

def test_voice():
    print("\n🎤 Testing Voice (Recording)...")
    try:
        voice = VoiceController()
        print("   Press Enter to start recording...")
        input()
        voice.start_recording()
        print("   Recording... Press Enter to stop.")
        input()
        text = voice.stop_recording()
        print(f"✅ Transcription: {text}")
    except Exception as e:
        print(f"❌ Voice failed: {e}")

def main():
    print("🚀 Nova Interactive Test Suite")
    print("1. Test Audio (Startup Sound)")
    print("2. Test Camera (Capture Frame)")
    print("3. Test Voice (Record & Transcribe)")
    print("4. Exit")
    
    while True:
        choice = input("\nSelect option (1-4): ")
        if choice == '1':
            test_audio()
        elif choice == '2':
            test_camera()
        elif choice == '3':
            test_voice()
        elif choice == '4':
            break
        else:
            print("Invalid choice")

if __name__ == "__main__":
    main()
