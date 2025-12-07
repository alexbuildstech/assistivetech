
import unittest
import cv2
import numpy as np
import time
from dataclasses import dataclass
from typing import Optional

# Mock TrackedObject
@dataclass
class MockObject:
    id: int = 1
    template: Optional[np.ndarray] = None
    bbox: Optional[tuple] = None

class TestLocalRecovery(unittest.TestCase):
    def test_template_matching(self):
        # Create a synthetic image with random noise (to simulate texture)
        np.random.seed(42)
        frame = np.random.randint(0, 255, (500, 500, 3), dtype=np.uint8)
        
        # Create object and set template (exact crop from the noise)
        obj = MockObject()
        obj.template = frame[100:150, 100:150].copy()
        
        # Create a new frame with different noise
        current_frame = np.random.randint(0, 255, (500, 500, 3), dtype=np.uint8)
        
        # "Paste" the object at a new location (300, 300)
        current_frame[300:350, 300:350] = obj.template
        
        # Attempt recovery logic
        res = cv2.matchTemplate(current_frame, obj.template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        
        print(f"Match Confidence: {max_val:.2f}")
        print(f"Match Location: {max_loc}")
        
        self.assertGreater(max_val, 0.9, "Should match with very high confidence")
        self.assertEqual(max_loc, (300, 300), "Should find new location")

if __name__ == '__main__':
    unittest.main()
