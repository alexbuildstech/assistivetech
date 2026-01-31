
import sys
import os
import time
import numpy as np
from unittest.mock import MagicMock, patch
import io

# Add current directory to path
sys.path.append(os.getcwd())

import config
from vision_module import VisionController
from audio_module_multi import MultiAudioController
from voice_control import VoiceController

def test_vision_optimizations():
    print("Testing Vision Optimizations...")
    with patch('cv2.VideoCapture') as mock_cap:
        mock_cap.return_value.isOpened.return_value = True
        mock_cap.return_value.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        vc = VisionController()
    
    # Check if _extract_json exists and works
    raw_json = "```json\n[{\"box_2d\": [1,2,3,4], \"label\": \"test\"}]\n```"
    extracted = vc._extract_json(raw_json)
    if "box_2d" in extracted:
        print("✅ JSON Extraction (Markdown) passed.")
    else:
        print("❌ JSON Extraction (Markdown) failed.")
        
    direct_json = "[{\"box_2d\": [1,2,3,4], \"label\": \"test\"}]"
    extracted = vc._extract_json(direct_json)
    if extracted == direct_json:
        print("✅ JSON Extraction (Direct) passed.")
    else:
        print("❌ JSON Extraction (Direct) failed.")

    # Test BytesIO optimization using a patch to check if imencode is called
    with patch('cv2.imencode') as mock_imencode:
        mock_imencode.return_value = (True, np.array([1, 2, 3]))
        with patch.object(vc.gemini_client.models, 'generate_content') as mock_gen:
            mock_gen.return_value = MagicMock(text="[]")
            frame = np.zeros((100, 100, 3), dtype=np.uint8)
            vc._detect_object_with_gemini(frame)
            if mock_imencode.called:
                print("✅ Vision: BytesIO optimization used (imencode called).")
            else:
                print("❌ Vision: BytesIO optimization NOT used.")

def test_audio_vectorization():
    print("\nTesting Audio Vectorization...")
    ac = MultiAudioController()
    
    # Mock source data
    obj_id = 1
    ac.update_source(obj_id, azimuth=0, volume=0.5, signature_name="default")
    
    # We need to ensure we have a signature
    ac.signatures["default"] = np.random.rand(1000).astype(np.float32)
    
    # Time the callback
    outdata = np.zeros((1024, 2), dtype=np.float32)
    start_time = time.perf_counter()
    ac._audio_callback(outdata, 1024, None, None)
    end_time = time.perf_counter()
    
    print(f"   Audio callback took: {(end_time - start_time)*1000:.4f}ms")
    if np.any(outdata):
        print("✅ Audio: Mixing functional.")
    else:
        print("❌ Audio: Output is silent.")

def test_voice_async_transcription():
    print("\nTesting Voice Async Transcription...")
    vc = VoiceController()
    
    # Mock Groq client
    vc.groq_client = MagicMock()
    vc.groq_client.audio.transcriptions.create.return_value = MagicMock(text="Hello world")
    
    audio_data = b"dummy audio data"
    start_time = time.perf_counter()
    vc._transcribe_audio(audio_data)
    end_time = time.perf_counter()
    
    duration = (end_time - start_time) * 1000
    print(f"   _transcribe_audio call returned in: {duration:.4f}ms")
    
    if duration < 10.0:  # Should be very fast as it's async
        print("✅ Voice: Transcription is async.")
    else:
        print(f"❌ Voice: Transcription might be blocking (took {duration:.1f}ms).")
    
    # Wait for result
    if vc.transcription_ready.wait(timeout=2):
        print(f"   Transcribed: {vc.transcribed_text}")
    else:
        print("❌ Voice: Transcription result never arrived.")

if __name__ == "__main__":
    try:
        test_vision_optimizations()
        test_audio_vectorization()
        test_voice_async_transcription()
        print("\n🎉 Performance and Optimization Verification Complete!")
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()
