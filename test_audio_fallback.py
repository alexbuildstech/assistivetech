
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add current directory to path
sys.path.append(os.getcwd())

import config

def test_audio_fallback_logic():
    print("Testing Audio Fallback Logic...")
    
    # Mock config
    config.ENABLE_HRTF = True
    
    # CASE 1: HRTF Available
    with patch('audio_hrtf.HRTF_AudioController') as mock_hrtf:
        mock_instance = MagicMock()
        mock_instance.is_dummy = False
        mock_hrtf.return_value = mock_instance
        
        # Simulated main logic
        audio_controller = None
        try:
            from audio_hrtf import HRTF_AudioController
            audio_controller = HRTF_AudioController()
            if hasattr(audio_controller, 'is_dummy') and audio_controller.is_dummy:
                audio_controller = None
        except:
            audio_controller = None
            
        print(f"   HRTF Available Case: Result={type(audio_controller).__name__ if audio_controller else 'None'}")
        if audio_controller == mock_instance:
            print("   ✅ Case 1 Passed")
        else:
            print("   ❌ Case 1 Failed")

    # CASE 2: HRTF is Dummy
    with patch('audio_hrtf.HRTF_AudioController') as mock_hrtf:
        mock_instance = MagicMock()
        mock_instance.is_dummy = True
        mock_hrtf.return_value = mock_instance
        
        with patch('audio_module_multi.MultiAudioController') as mock_multi:
            mock_multi_instance = MagicMock()
            mock_multi.return_value = mock_multi_instance
            
            # Simulated main logic
            audio_controller = None
            try:
                import audio_hrtf
                audio_controller = audio_hrtf.HRTF_AudioController()
                if hasattr(audio_controller, 'is_dummy') and audio_controller.is_dummy:
                    audio_controller = None
            except:
                audio_controller = None
                
            if audio_controller is None:
                import audio_module_multi
                audio_controller = audio_module_multi.MultiAudioController()
            
            print(f"   HRTF Dummy Case: Result={type(audio_controller).__name__ if audio_controller else 'None'}")
            # Check if it's the mock object
            if audio_controller == mock_multi_instance:
                print("   ✅ Case 2 Passed")
            else:
                print(f"   ❌ Case 2 Failed: Got {audio_controller}")

if __name__ == "__main__":
    test_audio_fallback_logic()
    print("\n🎉 Audio Fallback Test Complete!")
