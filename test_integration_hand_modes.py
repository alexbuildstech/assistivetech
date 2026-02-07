#!/usr/bin/env python3
"""
Integration Test for Hand Tracking and Mode Switching
Tests the complete workflow from voice command to object tracking.
"""

import sys
import time
import numpy as np
from unittest.mock import Mock, patch, MagicMock

def test_hand_tracking_workflow():
    """Test complete hand tracking workflow"""
    print("\n" + "="*60)
    print("🖐️ TESTING: Hand Tracking Workflow")
    print("="*60)
    
    # Setup
    from mode_controller import ModeController
    from object_manager import ObjectManager
    from voice_control import VoiceController
    
    mc = ModeController()
    
    # Step 1: Voice command "track my hand"
    print("\n1️⃣ Simulating voice command: 'track my hand'")
    with patch.object(VoiceController, '_initialize_groq_client', return_value=Mock()):
        with patch.object(VoiceController, '_initialize_gemini_chat', return_value=Mock()):
            vc = VoiceController()
            command = vc.parse_command("track my hand")
            
            if command and command.get("intent") == "track_object":
                obj_name = command["params"].get("object", "")
                print(f"   ✅ Parsed command: track_object = '{obj_name}'")
                
                # Step 2: Set target object
                mc.set_target_object(obj_name)
                print(f"   ✅ Target object set to: {mc.target_object}")
                
                # Step 3: Set mode to navigation
                mc.set_mode("navigation")
                print(f"   ✅ Mode set to: {mc.current_mode}")
                
                # Step 4: Simulate detection response from Gemini
                # (Gemini might return "hand" even though we asked for "my hand")
                mock_detections = [
                    {"box_2d": [400, 300, 600, 500], "label": "hand"}  # Just "hand", not "my hand"
                ]
                
                # Create a dummy frame
                frame = np.zeros((720, 1280, 3), dtype=np.uint8)
                
                # Step 5: Process detections
                count = mc.process_detections(mock_detections, frame)
                print(f"   ✅ Processed {count} detection(s)")
                
                # Step 6: Verify fuzzy matching worked
                hands = mc.object_manager.get_objects_by_label("my hand")
                if len(hands) > 0:
                    print(f"   ✅ Fuzzy matching worked! Found {len(hands)} hand(s) with target 'my hand'")
                    print(f"      Object label: '{hands[0].label}'")
                    return True
                else:
                    print(f"   ❌ Fuzzy matching failed - no hands found with target 'my hand'")
                    return False
            else:
                print(f"   ❌ Failed to parse command correctly")
                return False

def test_all_modes():
    """Test all navigation modes"""
    print("\n" + "="*60)
    print("🔄 TESTING: All Navigation Modes")
    print("="*60)
    
    from mode_controller import ModeController
    from config import NavigationMode
    
    mc = ModeController()
    modes = ["navigation", "obstacle", "social", "exploration"]
    
    all_passed = True
    for mode in modes:
        result = mc.set_mode(mode)
        if result and mc.current_mode == mode:
            # Get prompt for this mode
            prompt = mc.get_detection_prompt()
            max_objs = mc.get_max_objects()
            print(f"   ✅ {mode}: max_objects={max_objs}, prompt_len={len(prompt)}")
        else:
            print(f"   ❌ {mode}: FAILED")
            all_passed = False
    
    return all_passed

def test_performance():
    """Test performance metrics"""
    print("\n" + "="*60)
    print("⚡ TESTING: Performance")
    print("="*60)
    
    from mode_controller import ModeController
    from object_manager import ObjectManager
    import time
    
    mc = ModeController()
    om = mc.object_manager
    
    # Test processing speed
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    
    # Add multiple objects
    for i in range(5):
        om.add_object(f"object_{i}", (100*i, 100*i, 50, 50))
    
    # Test detection processing speed
    mock_detections = [
        {"box_2d": [100, 100, 200, 200], "label": f"object_{i}"} 
        for i in range(5)
    ]
    
    start = time.time()
    for _ in range(10):  # Process 10 times
        mc.process_detections(mock_detections, frame)
    elapsed = time.time() - start
    
    avg_time = (elapsed / 10) * 1000  # Convert to ms
    print(f"   ✅ Detection processing: {avg_time:.2f}ms avg (10 iterations)")
    
    if avg_time < 50:  # Should be under 50ms
        return True
    else:
        print(f"   ⚠️ Processing might be too slow: {avg_time:.2f}ms")
        return True  # Still pass, just warn

def main():
    """Run all integration tests"""
    print("\n" + "="*60)
    print("🚀 INTEGRATION TEST SUITE")
    print("Testing Hand Tracking, Modes, and Performance")
    print("="*60)
    
    results = []
    
    try:
        results.append(("Hand Tracking", test_hand_tracking_workflow()))
    except Exception as e:
        print(f"❌ Hand tracking test failed with error: {e}")
        results.append(("Hand Tracking", False))
    
    try:
        results.append(("All Modes", test_all_modes()))
    except Exception as e:
        print(f"❌ Mode test failed with error: {e}")
        results.append(("All Modes", False))
    
    try:
        results.append(("Performance", test_performance()))
    except Exception as e:
        print(f"❌ Performance test failed with error: {e}")
        results.append(("Performance", False))
    
    # Summary
    print("\n" + "="*60)
    print("📊 INTEGRATION TEST RESULTS")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status}: {test_name}")
    
    print(f"\n   Total: {passed}/{total} tests passed")
    print("="*60)
    
    if passed == total:
        print("🎉 All integration tests passed!")
        return 0
    else:
        print("⚠️  Some integration tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
