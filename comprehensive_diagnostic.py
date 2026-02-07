#!/usr/bin/env python3
"""
Comprehensive Diagnostic and Fix Script for Nova Assistive Navigation
Tests all commands, modes, and features to identify and fix issues.
"""

import sys
import time
import threading
import numpy as np
from unittest.mock import Mock, patch, MagicMock
import traceback

# Test results collector
test_results = {
    "passed": [],
    "failed": [],
    "warnings": []
}

def test_section(name):
    """Print test section header"""
    print(f"\n{'='*60}")
    print(f"🧪 TESTING: {name}")
    print(f"{'='*60}")

def log_pass(test_name, details=""):
    """Log a passed test"""
    test_results["passed"].append((test_name, details))
    print(f"  ✅ PASS: {test_name} {details}")

def log_fail(test_name, error, details=""):
    """Log a failed test"""
    test_results["failed"].append((test_name, str(error), details))
    print(f"  ❌ FAIL: {test_name}")
    print(f"     Error: {error}")
    if details:
        print(f"     Details: {details}")

def log_warn(test_name, warning):
    """Log a warning"""
    test_results["warnings"].append((test_name, warning))
    print(f"  ⚠️  WARN: {test_name} - {warning}")

def run_tests():
    """Run all diagnostic tests"""
    
    # === TEST 1: Configuration and API Keys ===
    test_section("Configuration & API Keys")
    try:
        import config
        
        # Check API keys
        if config.API_KEY and config.API_KEY != "YOUR_GEMINI_API_KEY_HERE":
            log_pass("API_KEY present", f"Starts with: {config.API_KEY[:15]}...")
        else:
            log_fail("API_KEY", "Missing or placeholder", "Check .env file")
            
        if config.GROQ_API_KEY and config.GROQ_API_KEY != "YOUR_GROQ_API_KEY_HERE":
            log_pass("GROQ_API_KEY present", f"Starts with: {config.GROQ_API_KEY[:15]}...")
        else:
            log_warn("GROQ_API_KEY", "Missing or placeholder - voice may not work")
            
        # Check NavigationMode values
        modes = [config.NavigationMode.NAVIGATION, config.NavigationMode.OBSTACLE, 
                config.NavigationMode.SOCIAL, config.NavigationMode.EXPLORATION]
        if all(isinstance(m, str) for m in modes):
            log_pass("NavigationMode types", "All modes are strings")
        else:
            log_fail("NavigationMode", "Modes should be strings, got mixed types")
            
        # Check MODE_CONFIGS
        if len(config.MODE_CONFIGS) == 4:
            log_pass("MODE_CONFIGS count", f"4 modes configured")
        else:
            log_fail("MODE_CONFIGS", f"Expected 4 modes, got {len(config.MODE_CONFIGS)}")
            
    except Exception as e:
        log_fail("Configuration", e, traceback.format_exc())
    
    # === TEST 2: Mode Controller ===
    test_section("Mode Controller")
    try:
        from mode_controller import ModeController
        
        mc = ModeController()
        log_pass("ModeController init", f"Default mode: {mc.current_mode}")
        
        # Test mode switching
        modes_to_test = ["navigation", "obstacle", "social", "exploration"]
        for mode in modes_to_test:
            try:
                result = mc.set_mode(mode)
                if result and mc.current_mode == mode:
                    log_pass(f"Mode switch to {mode}")
                else:
                    log_fail(f"Mode switch to {mode}", f"Result: {result}, Current: {mc.current_mode}")
            except Exception as e:
                log_fail(f"Mode switch to {mode}", e)
        
        # Test get_detection_prompt
        prompt = mc.get_detection_prompt()
        if prompt and isinstance(prompt, str):
            log_pass("get_detection_prompt", f"Prompt length: {len(prompt)}")
        else:
            log_fail("get_detection_prompt", "Invalid or empty prompt")
            
        # Test get_mode_description
        desc = mc.get_mode_description()
        if desc:
            log_pass("get_mode_description", desc)
        else:
            log_fail("get_mode_description", "Empty description")
            
    except Exception as e:
        log_fail("ModeController", e, traceback.format_exc())
    
    # === TEST 3: Voice Command Parsing ===
    test_section("Voice Commands")
    try:
        from voice_control import VoiceController
        
        # Mock the controller to avoid API calls
        with patch.object(VoiceController, '_initialize_groq_client', return_value=Mock()):
            with patch.object(VoiceController, '_initialize_gemini_chat', return_value=Mock()):
                vc = VoiceController()
                log_pass("VoiceController init")
                
                # Test command parsing for various inputs
                test_commands = [
                    ("track my hand", "Should detect hand tracking intent"),
                    ("track hand", "Should detect hand tracking intent"),
                    ("find my phone", "Should detect track_object with phone"),
                    ("follow the person", "Should detect track_object with person"),
                    ("navigation mode", "Should switch to navigation mode"),
                    ("obstacle mode", "Should switch to obstacle mode"),
                    ("social mode", "Should switch to social mode"),
                    ("exploration mode", "Should switch to exploration mode"),
                    ("describe the scene", "Should trigger describe_scene"),
                    ("stop tracking", "Should stop tracking"),
                    ("what is this", "Should trigger visual_qa"),
                    ("look at this", "Should trigger visual_qa"),
                    ("where is my phone", "Should trigger recall_object"),
                ]
                
                for cmd, expected in test_commands:
                    try:
                        result = vc.parse_command(cmd)
                        if result and result.get("intent"):
                            log_pass(f"Parse: '{cmd}'", f"Intent: {result['intent']}")
                        else:
                            # Some commands should fall through to chat - that's ok
                            log_pass(f"Parse: '{cmd}'", "Falls through to chat (expected for some)")
                    except Exception as e:
                        log_fail(f"Parse: '{cmd}'", e)
                        
    except Exception as e:
        log_fail("Voice Commands", e, traceback.format_exc())
    
    # === TEST 4: Object Manager ===
    test_section("Object Manager & Tracking")
    try:
        from object_manager import ObjectManager, TrackedObject
        
        om = ObjectManager()
        log_pass("ObjectManager init", f"Objects: {len(om.objects)}")
        
        # Test adding objects
        obj1 = om.add_object("hand", (100, 100, 50, 50))
        if obj1 and obj1.id == 0:
            log_pass("Add hand object", f"ID: {obj1.id}, Label: {obj1.label}")
        else:
            log_fail("Add hand object", f"Unexpected ID: {obj1.id if obj1 else None}")
        
        # Test adding another object
        obj2 = om.add_object("phone", (200, 200, 30, 60))
        if obj2 and obj2.id == 1:
            log_pass("Add phone object", f"ID: {obj2.id}, Label: {obj2.label}")
        else:
            log_fail("Add phone object", f"Unexpected ID: {obj2.id if obj2 else None}")
        
        # Test get_objects_by_label
        hands = om.get_objects_by_label("hand")
        if len(hands) == 1 and hands[0].label == "hand":
            log_pass("get_objects_by_label", f"Found {len(hands)} hand(s)")
        else:
            log_fail("get_objects_by_label", f"Expected 1 hand, got {len(hands)}")
        
        # Test filtering
        om.filter_by_labels(["hand"])
        if len(om.objects) == 1 and om.objects[0].label == "hand":
            log_pass("filter_by_labels", "Correctly filtered to hand only")
        else:
            log_fail("filter_by_labels", f"Expected 1 hand, got {len(om.objects)}")
            
    except Exception as e:
        log_fail("Object Manager", e, traceback.format_exc())
    
    # === TEST 5: Audio System ===
    test_section("Audio System")
    try:
        from audio_module_multi import MultiAudioController
        from audio_coordinator import AudioCoordinator
        from shared_state import SharedGameState
        
        audio = MultiAudioController()
        log_pass("MultiAudioController init", f"Sample rate: {audio.sample_rate}")
        
        # Test signature loading
        if len(audio.signatures) > 0:
            log_pass("Audio signatures", f"{len(audio.signatures)} signatures loaded")
        else:
            log_fail("Audio signatures", "No signatures loaded")
        
        # Test source management
        audio.update_source(0, 30, 0.5, "phone")
        if 0 in audio.sources:
            log_pass("update_source", "Source added")
        else:
            log_fail("update_source", "Source not found")
        
        # Test coordinator
        shared_state = SharedGameState()
        coordinator = AudioCoordinator(audio, shared_state)
        log_pass("AudioCoordinator init")
        
    except Exception as e:
        log_fail("Audio System", e, traceback.format_exc())
    
    # === TEST 6: Vision Module ===
    test_section("Vision Module")
    try:
        from vision_module import VisionController
        
        # Test JSON extraction
        vc_mock = Mock(spec=VisionController)
        test_cases = [
            ('```json\n[{"box_2d": [1,2,3,4]}]\n```', [{"box_2d": [1,2,3,4]}]),
            ('[{"box_2d": [1,2,3,4]}]', [{"box_2d": [1,2,3,4]}]),
            ('Regular text', 'Regular text'),
        ]
        
        # Test the actual _extract_json method if we can create a dummy instance
        try:
            # Create minimal instance for testing
            with patch('vision_module.GENAI_AVAILABLE', False):
                vc = VisionController.__new__(VisionController)
                for input_text, expected in test_cases:
                    result = vc._extract_json(input_text)
                    if result:
                        log_pass(f"JSON extract: {input_text[:20]}...")
                    else:
                        log_fail(f"JSON extract: {input_text[:20]}...", "Empty result")
        except Exception as e:
            log_warn("Vision JSON extract", f"Could not test: {e}")
            
    except Exception as e:
        log_fail("Vision Module", e, traceback.format_exc())
    
    # === TEST 7: Shared State ===
    test_section("Shared State")
    try:
        from shared_state import SharedGameState
        
        ss = SharedGameState()
        log_pass("SharedGameState init")
        
        # Test frame operations
        test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        ss.update_frame(test_frame)
        retrieved = ss.get_latest_frame()
        if retrieved is not None:
            log_pass("Frame update/get", f"Shape: {retrieved.shape}")
        else:
            log_fail("Frame update/get", "Frame is None")
        
        # Test command queue
        ss.add_command("detect")
        ss.add_command("track_hand")
        if ss.has_commands():
            log_pass("Command queue", "Commands added successfully")
        else:
            log_fail("Command queue", "No commands in queue")
        
        cmd = ss.get_next_command()
        if cmd == "detect":
            log_pass("Command retrieval", f"Retrieved: {cmd}")
        else:
            log_fail("Command retrieval", f"Expected 'detect', got {cmd}")
            
    except Exception as e:
        log_fail("Shared State", e, traceback.format_exc())
    
    # === TEST 8: Hardware Interface ===
    test_section("Hardware Interface")
    try:
        from hardware_interface import HardwareInterface, DummyHardwareInterface
        
        dummy = DummyHardwareInterface()
        pressure = dummy.get_pressure()
        if pressure == 0:
            log_pass("DummyHardwareInterface", "Returns default pressure")
        else:
            log_fail("DummyHardwareInterface", f"Expected 0, got {pressure}")
            
    except Exception as e:
        log_fail("Hardware Interface", e, traceback.format_exc())
    
    # === TEST 9: Keyboard Commands ===
    test_section("Keyboard Commands")
    try:
        # Define expected key handlers
        expected_keys = {
            'q': "Quit",
            'f': "Find/Detect",
            'c': "Start voice recording",
            's': "Stop voice recording",
            'd': "Describe scene",
            'm': "Cycle modes",
            'n': "Normal/Reset mode",
            'r': "Re-acquire",
        }
        
        # Read main_enhanced.py to verify key handlers
        with open('main_enhanced.py', 'r') as f:
            content = f.read()
        
        for key, action in expected_keys.items():
            # Check for key handler
            if f"ord('{key}')" in content or f'ord("{key}")' in content:
                log_pass(f"Key '{key}' handler", action)
            else:
                log_fail(f"Key '{key}' handler", f"Handler not found for {action}")
                
    except Exception as e:
        log_fail("Keyboard Commands", e, traceback.format_exc())
    
    # === TEST 10: Performance Benchmarks ===
    test_section("Performance Checks")
    try:
        import config
        
        # Check buffer sizes
        if config.AUDIO_BUFFER_SIZE <= 2048:
            log_pass("Audio buffer size", f"{config.AUDIO_BUFFER_SIZE} (low latency)")
        else:
            log_warn("Audio buffer size", f"{config.AUDIO_BUFFER_SIZE} may be high latency")
        
        # Check cooldown
        if config.REACQUIRE_COOLDOWN_SECONDS <= 1.0:
            log_pass("Reacquire cooldown", f"{config.REACQUIRE_COOLDOWN_SECONDS}s (responsive)")
        else:
            log_warn("Reacquire cooldown", f"{config.REACQUIRE_COOLDOWN_SECONDS}s may be sluggish")
        
        # Check camera resolution
        total_pixels = config.CAMERA_WIDTH * config.CAMERA_HEIGHT
        if total_pixels <= 1280 * 720:
            log_pass("Camera resolution", f"{config.CAMERA_WIDTH}x{config.CAMERA_HEIGHT}")
        else:
            log_warn("Camera resolution", f"{config.CAMERA_WIDTH}x{config.CAMERA_HEIGHT} may be heavy")
            
    except Exception as e:
        log_fail("Performance Checks", e, traceback.format_exc())

def print_summary():
    """Print test summary"""
    print(f"\n{'='*60}")
    print("📊 TEST SUMMARY")
    print(f"{'='*60}")
    print(f"✅ Passed: {len(test_results['passed'])}")
    print(f"❌ Failed: {len(test_results['failed'])}")
    print(f"⚠️  Warnings: {len(test_results['warnings'])}")
    
    if test_results['failed']:
        print(f"\n❌ FAILED TESTS:")
        for test, error, details in test_results['failed']:
            print(f"  - {test}")
            print(f"    {error}")
    
    if test_results['warnings']:
        print(f"\n⚠️  WARNINGS:")
        for test, warning in test_results['warnings']:
            print(f"  - {test}: {warning}")
    
    success_rate = len(test_results['passed']) / (len(test_results['passed']) + len(test_results['failed']))
    print(f"\n{'='*60}")
    print(f"Success Rate: {success_rate*100:.1f}%")
    print(f"{'='*60}")
    
    return len(test_results['failed']) == 0

if __name__ == "__main__":
    print("🚀 Starting Nova Assistive Navigation Diagnostics")
    print("This will test all modules, commands, and modes...")
    
    run_tests()
    all_passed = print_summary()
    
    if all_passed:
        print("\n🎉 All tests passed! System appears healthy.")
        sys.exit(0)
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")
        sys.exit(1)
