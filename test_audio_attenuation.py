
import math
import unittest
from dataclasses import dataclass

# Mock classes to simulate the environment
@dataclass
class MockObject:
    id: int
    label: str
    bbox: tuple  # (x, y, w, h)

class MockAudioController:
    def __init__(self):
        self.sources = {}
        self.gains = {} # Store gains for verification

    def _update_scene(self, objects):
        # Re-implementing the logic from audio_hrtf.py for testing purposes
        # or ideally, we would import it if it was a pure function.
        # Since it's embedded in the class and uses OpenAL, we'll extract the logic here
        # to verify the math is correct.
        
        width = 1280
        height = 720
        max_area = width * height * 0.5
        
        results = {}

        for obj in objects:
            area = obj.bbox[2] * obj.bbox[3]
            
            # The logic from audio_hrtf.py
            dist = max(0.5, min(10.0, math.sqrt(max_area / (area + 1))))
            
            ref_dist = 1.0 
            gain = min(1.0, ref_dist / (dist * 0.5))
            gain = max(0.1, gain)
            
            results[obj.id] = {
                "dist": dist,
                "gain": gain,
                "label": obj.label
            }
            
        return results

class TestAudioAttenuation(unittest.TestCase):
    def test_attenuation(self):
        controller = MockAudioController()
        
        # Define objects at different "distances" (sizes)
        # Frame is 1280x720 = 921,600 pixels
        
        # 1. Very Close (Large BBox) - e.g. 600x600 = 360,000
        obj_close = MockObject(1, "Close Object", (0, 0, 600, 600))
        
        # 2. Medium Distance - e.g. 200x200 = 40,000
        obj_med = MockObject(2, "Medium Object", (0, 0, 200, 200))
        
        # 3. Far Distance - e.g. 50x50 = 2,500
        obj_far = MockObject(3, "Far Object", (0, 0, 50, 50))
        
        results = controller._update_scene([obj_close, obj_med, obj_far])
        
        print("\n--- Audio Attenuation Test Results ---")
        for obj_id, res in results.items():
            print(f"Object {obj_id} ({res['label']}): Dist={res['dist']:.2f}, Gain={res['gain']:.2f}")
            
        # Assertions
        # Closer object should have higher gain
        self.assertGreater(results[1]['gain'], results[2]['gain'], "Close object should be louder than medium object")
        self.assertGreater(results[2]['gain'], results[3]['gain'], "Medium object should be louder than far object")
        
        # Check specific values (approximate)
        # Close object should be near max gain (1.0)
        self.assertAlmostEqual(results[1]['gain'], 1.0, delta=0.2)
        
        # Far object should be near min gain (0.1)
        self.assertAlmostEqual(results[3]['gain'], 0.1, delta=0.2)

if __name__ == '__main__':
    unittest.main()
