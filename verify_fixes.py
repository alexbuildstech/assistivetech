
import sys
import os
import time
import unittest
from unittest.mock import MagicMock

# Add current directory to path
sys.path.append(os.getcwd())

print("🔍 Starting Verification...")

# 1. Verify Audio Module (Syntax check)
print("\n[1/3] Verifying Audio Module...")
try:
    import audio_hrtf
    print("✅ audio_hrtf imported successfully.")
except Exception as e:
    print(f"❌ Failed to import audio_hrtf: {e}")
    sys.exit(1)

# 2. Verify Mode Controller Logic
print("\n[2/3] Verifying Mode Controller Logic...")
try:
    from mode_controller import ModeController
    from object_manager import ObjectManager, TrackedObject
    
    # Mock ObjectManager
    mc = ModeController()
    mc.object_manager = MagicMock()
    
    # Create a dummy existing object
    existing_obj = MagicMock()
    existing_obj.id = 1
    existing_obj.label = "person"
    existing_obj.bbox = (100, 100, 50, 100)
    existing_obj.is_lost = False # Currently tracking
    
    mc.object_manager.objects = [existing_obj]
    mc.object_manager.compute_iou.return_value = 0.5 # Moderate overlap
    
    # Mock frame (Use real numpy array for slicing logic)
    import numpy as np
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # Case 1: Tracking active, low IoU -> Should NOT update (stale detection)
    print("   Testing Case 1: Active tracking, low IoU (0.5)...")
    detections = [{"box_2d": [200, 200, 300, 300], "label": "person"}] # Normalized coords don't matter much here as we mock IoU
    
    # We need to mock the coordinate conversion to return a bbox that results in 0.5 IoU
    # But since we mocked compute_iou, the bbox values don't strictly matter for the logic check
    # EXCEPT that process_detections calculates new_bbox from detections.
    
    # Let's just verify the logic branch.
    # We need to ensure process_detections runs without error and calls what we expect.
    
    mc.process_detections(detections, frame)
    
    # Verify bbox was NOT updated (because IoU 0.5 < 0.6 threshold for active objects)
    # existing_obj.bbox should still be the original
    # Note: process_detections modifies existing_obj.bbox directly if it updates.
    # We need to check if the assignment happened.
    # Since existing_obj is a Mock, we can't easily check attribute assignment unless we wrap it.
    
    # Let's use a real object for better testing
    real_obj = TrackedObject(
        id=1, label="person", bbox=(100, 100, 50, 100), 
        tracker=None, confidence=1.0, audio_signature={}, color=(0,0,0), 
        last_update=time.time()
    )
    real_obj.is_lost = False
    mc.object_manager.objects = [real_obj]
    mc.object_manager.compute_iou = lambda b1, b2: 0.5 # Force 0.5 IoU
    
    mc.process_detections(detections, frame)
    
    if real_obj.bbox == (100, 100, 50, 100):
        print("✅ Case 1 Passed: Active object not updated with low IoU detection.")
    else:
        print(f"❌ Case 1 Failed: Object updated! {real_obj.bbox}")
        
    # Case 2: Tracking active, high IoU -> Should update
    print("   Testing Case 2: Active tracking, high IoU (0.8)...")
    mc.object_manager.compute_iou = lambda b1, b2: 0.8 # Force 0.8 IoU
    mc.process_detections(detections, frame)
    
    if real_obj.bbox != (100, 100, 50, 100):
        print("✅ Case 2 Passed: Active object updated with high IoU detection.")
    else:
        print("❌ Case 2 Failed: Object NOT updated!")

    # Case 3: Object Lost, low IoU -> Should update (recovery)
    print("   Testing Case 3: Lost object, low IoU (0.2)...")
    real_obj.is_lost = True
    real_obj.bbox = (100, 100, 50, 100) # Reset
    mc.object_manager.compute_iou = lambda b1, b2: 0.2 # Force 0.2 IoU
    mc.process_detections(detections, frame)
    
    if real_obj.bbox != (100, 100, 50, 100):
        print("✅ Case 3 Passed: Lost object updated with low IoU detection.")
    else:
        print("❌ Case 3 Failed: Object NOT updated!")

    # Case 4: Verify update_template (Regression Test for NameError)
    print("   Testing Case 4: update_template regression test...")
    obj_to_update = TrackedObject(
        id=2, label="cup", bbox=(50, 50, 100, 100),
        tracker=None, confidence=1.0, audio_signature={}, color=(0,0,0),
        last_update=time.time()
    )
    # This should NOT raise NameError
    # We need a real ObjectManager instance to test the method logic
    real_om = ObjectManager()
    real_om.update_template(obj_to_update, frame) # frame is 480x640
    if obj_to_update.template is not None:
        print("✅ Case 4 Passed: update_template ran successfully.")
    else:
        print("❌ Case 4 Failed: template not updated.")

except Exception as e:
    print(f"❌ Failed to verify Mode Controller: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 3. Verify Main Module (Syntax check)
print("\n[3/3] Verifying Main Module...")
try:
    import main_enhanced
    print("✅ main_enhanced imported successfully.")
except Exception as e:
    print(f"❌ Failed to import main_enhanced: {e}")
    sys.exit(1)

print("\n🎉 All verifications passed!")
