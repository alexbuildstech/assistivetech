import time
from voice_control import VoiceController

def test_voice_auto():
    print("\n🎤 Testing Voice (Auto-Recording 5s)...")
    try:
        voice = VoiceController()
        print("   Starting recording in 1s...")
        time.sleep(1)
        voice.start_recording()
        print("   🔴 Recording... Say something!")
        time.sleep(5)
        print("   ⏹️ Stopping...")
        text = voice.stop_recording()
        print(f"✅ Transcription: {text}")
    except Exception as e:
        print(f"❌ Voice failed: {e}")

if __name__ == "__main__":
    test_voice_auto()
