
import unittest
import time
from dataclasses import dataclass
from typing import Optional

# Mock Configuration
THREAT_PRIORITIES = {
    "person": 1.0,
    "tree": 0.8,
    "stone": 0.2,
    "default": 0.3
}

# Mock Classes
@dataclass
class MockObject:
    id: int
    label: str
    bbox: tuple
    velocity: tuple = (0, 0)
    threat_score: float = 0.0
    is_lost: bool = False
    lost_time: Optional[float] = None

class TestThreatLogic(unittest.TestCase):
    def calculate_threat_score(self, obj, frame_width=1280, frame_height=720):
        # Re-implementing logic from object_manager.py for testing
        bbox = obj.bbox
        area = bbox[2] * bbox[3]
        frame_area = frame_width * frame_height
        size_score = min(1.0, area / (frame_area * 0.5))
        
        label_key = obj.label.lower().split(" ")[-1]
        semantic_score = THREAT_PRIORITIES.get(label_key, THREAT_PRIORITIES["default"])
        
        center_x = bbox[0] + bbox[2] / 2
        frame_center_x = frame_width / 2
        dist_from_center = abs(center_x - frame_center_x) / (frame_width / 2)
        centrality_score = 1.0 - min(1.0, dist_from_center)
        
        trajectory_score = 0.5
        if obj.velocity:
            vx, vy = obj.velocity
            moving_to_center = (center_x < frame_center_x and vx > 0) or (center_x > frame_center_x and vx < 0)
            if moving_to_center:
                trajectory_score = 1.0
        
        obj.threat_score = (
            (size_score * 0.4) + 
            (semantic_score * 0.4) + 
            (centrality_score * 0.1) +
            (trajectory_score * 0.1)
        )
        return obj.threat_score

    def test_semantic_priority(self):
        # Scenario: Small Stone (Close) vs Big Tree (Far)
        # Stone: 200x200 (Close-ish), Low Semantic
        stone = MockObject(1, "Small Stone", (500, 500, 200, 200))
        
        # Tree: 100x100 (Farther), High Semantic
        tree = MockObject(2, "Big Tree", (600, 300, 100, 100))
        
        score_stone = self.calculate_threat_score(stone)
        score_tree = self.calculate_threat_score(tree)
        
        print(f"\nStone Score: {score_stone:.3f}")
        print(f"Tree Score: {score_tree:.3f}")
        
        # Tree should be higher threat despite being smaller, because it's a TREE
        # Stone: Size=0.08, Sem=0.2 -> Score ~ 0.03 + 0.08 + ...
        # Tree: Size=0.02, Sem=0.8 -> Score ~ 0.008 + 0.32 + ...
        self.assertGreater(score_tree, score_stone, "Tree should be higher threat than stone")

    def test_fallback_timeout(self):
        # Scenario: Main threat lost for > 5 seconds
        obj = MockObject(1, "Person", (0,0,100,100))
        obj.is_lost = True
        obj.lost_time = time.time() - 6.0 # 6 seconds ago
        
        should_rescan = False
        elapsed = time.time() - obj.lost_time
        if obj.is_lost and elapsed > 5.0:
            should_rescan = True
            
        self.assertTrue(should_rescan, "Should trigger rescan after 5 seconds")

if __name__ == '__main__':
    unittest.main()
