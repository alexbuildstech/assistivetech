
import cv2
import numpy as np
import time
from object_manager import ObjectManager

def create_frame(x, y, w, h):
    """Create a black frame with a white square."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 255, 255), -1)
    return frame

def test_tracking():
    print("🧪 Testing Object Tracking Logic...")
    
    om = ObjectManager()
    
    # 1. Create initial frame
    x, y, w, h = 100, 100, 50, 50
    frame1 = create_frame(x, y, w, h)
    
    # 2. Add object and init tracker
    obj = om.add_object("test_box", (x, y, w, h))
    om.init_tracker(obj.id, frame1)
    
    if obj.tracker is None:
        print("❌ Failed to initialize tracker (missing opencv-contrib?)")
        # Try to force KCF if CSRT failed
        try:
            obj.tracker = cv2.TrackerKCF_create()
            obj.tracker.init(frame1, (x, y, w, h))
            print("⚠️ Forced KCF fallback")
        except:
            print("❌ Could not init any tracker")
            return

    print(f"📍 Initial BBox: {obj.bbox}")
    
    # 3. Simulate movement
    # Move 5 pixels right per frame for 10 frames
    for i in range(1, 11):
        new_x = x + (i * 5)
        frame_next = create_frame(new_x, y, w, h)
        
        # Update trackers
        tracked_objs = om.update_trackers(frame_next)
        
        if not tracked_objs:
            print(f"❌ Frame {i}: Tracking LOST!")
            break
            
        curr_bbox = obj.bbox
        print(f"Frame {i}: Pos {new_x} -> Tracked {curr_bbox[0]:.1f} | Diff: {abs(new_x - curr_bbox[0]):.1f}")
        
        # Check if tracking is working (allow small error)
        if abs(new_x - curr_bbox[0]) > 20:
            print("❌ Tracking lagging significantly!")
        elif abs(new_x - curr_bbox[0]) < 1.0 and i > 1:
             print("❌ Tracking FROZEN (not moving)!")
             
    print("✅ Test Complete")

if __name__ == "__main__":
    test_tracking()
