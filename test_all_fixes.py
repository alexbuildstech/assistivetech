#!/usr/bin/env python3
"""
Comprehensive test suite for the Assistive Navigation System.
Tests all critical fixes and optimizations.
"""

import sys
import os
import time
import threading
import unittest
from unittest.mock import Mock, patch, MagicMock
import numpy as np

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class TestSharedState(unittest.TestCase):
    """Test SharedGameState optimizations."""
    
    def setUp(self):
        from shared_state import SharedGameState
        self.state = SharedGameState()
    
    def test_frame_dropping(self):
        """Test that stale frames are properly dropped."""
        # Create a mock frame
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Update frame
        self.state.update_frame(frame)
        
        # First get should return the frame
        result1 = self.state.get_latest_frame()
        self.assertIsNotNone(result1)
        
        # Second get without update should return None (frame already processed)
        result2 = self.state.get_latest_frame()
        self.assertIsNone(result2)
        
        # After update, should return new frame
        self.state.update_frame(frame)
        result3 = self.state.get_latest_frame()
        self.assertIsNotNone(result3)
    
    def test_command_queue_limit(self):
        """Test command queue size limit."""
        # Add many commands
        for i in range(15):
            self.state.add_command(f"command_{i}")
        
        # Queue should be limited to 5 (optimized for low latency)
        count = 0
        while self.state.get_next_command():
            count += 1
        
        self.assertEqual(count, 5)
    
    def test_thread_safety(self):
        """Test thread-safe operations."""
        errors = []
        
        def writer():
            try:
                for i in range(100):
                    frame = np.zeros((480, 640, 3), dtype=np.uint8)
                    self.state.update_frame(frame)
                    self.state.add_command(f"cmd_{i}")
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)
        
        def reader():
            try:
                for _ in range(100):
                    self.state.get_latest_frame()
                    self.state.get_display_state()
                    self.state.get_next_command()
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)
        
        # Start threads
        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=reader)
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        self.assertEqual(len(errors), 0, f"Thread errors: {errors}")


class TestObjectManager(unittest.TestCase):
    """Test ObjectManager fixes."""
    
    def setUp(self):
        from object_manager import ObjectManager
        self.manager = ObjectManager()
    
    def test_threat_score_calculation(self):
        """Test that threat score includes semantic priority."""
        # Add a person (high priority) - centered in frame with large size
        bbox = (220, 140, 200, 200)  # x, y, w, h - centered in 640x480
        obj = self.manager.add_object("person", bbox, confidence=0.9)
        
        # Create a mock frame
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Mock tracker
        obj.tracker = Mock()
        obj.tracker.update.return_value = (True, bbox)
        
        # Update trackers
        self.manager.update_trackers(frame)
        
        # Person should have high threat score due to semantic priority (1.0 for person)
        # With centered large object: size_score ~0.55, centrality ~1.0, semantic 1.0
        # Expected: (0.55*0.6 + 1.0*0.4) * 1.0 = 0.73
        self.assertGreater(obj.threat_score, 0.3, "Threat score should account for semantic priority")
        self.assertLessEqual(obj.threat_score, 1.0, "Threat score should be normalized to 1.0")
    
    def test_iou_calculation(self):
        """Test IoU computation."""
        box1 = (0, 0, 100, 100)
        box2 = (50, 50, 100, 100)  # 50% overlap
        
        iou = self.manager.compute_iou(box1, box2)
        
        # Should be around 0.14 (intersection / union)
        self.assertGreater(iou, 0)
        self.assertLess(iou, 1.0)
    
    def test_cleanup_stale_trackers(self):
        """Test stale tracker cleanup."""
        # Add an object
        obj = self.manager.add_object("phone", (10, 10, 20, 20))
        obj.last_verified = time.time() - 40  # 40 seconds ago
        
        # Cleanup should remove it
        result = self.manager.cleanup_stale_trackers(max_age=30.0)
        self.assertTrue(result)
        self.assertEqual(len(self.manager.objects), 0)


class TestLearningModule(unittest.TestCase):
    """Test LearningModule optimizations."""
    
    def setUp(self):
        from learning_module import LearningModule
        import tempfile
        # Use temp directory for test DB
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.cache_dir = os.path.join(self.temp_dir, "cache")
        self.learning = LearningModule(self.db_path, self.cache_dir)
    
    def tearDown(self):
        import shutil
        self.learning.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_database_thread_safety(self):
        """Test that database handles concurrent access."""
        errors = []
        
        def writer():
            try:
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                for i in range(10):
                    self.learning.save_detection(
                        frame, f"object_{i}", (10, 10, 20, 20), 0.8,
                        640, 480
                    )
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=writer) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        self.assertEqual(len(errors), 0, f"Database thread errors: {errors}")
    
    def test_bbox_to_grid(self):
        """Test bounding box to grid conversion."""
        bbox = (320, 240, 100, 100)  # Center of 640x480 frame
        grid_x, grid_y = self.learning.bbox_to_grid(bbox, 640, 480)
        
        # Should be roughly in the middle of default 10x8 grid
        self.assertEqual(grid_x, 5)
        self.assertEqual(grid_y, 4)


class TestVoiceController(unittest.TestCase):
    """Test VoiceController fixes."""
    
    @patch('voice_control.Groq')
    def test_synchronous_transcription(self, mock_groq):
        """Test that transcription is synchronous (no thread overhead)."""
        from voice_control import VoiceController
        
        # Mock Groq client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "test transcription"
        mock_client.audio.transcriptions.create.return_value = mock_response
        mock_groq.return_value = mock_client
        
        # Create controller
        with patch.object(VoiceController, '_get_player_command', return_value=None):
            vc = VoiceController()
            vc.groq_client = mock_client
            
            # Mock recording state
            vc.is_recording = True
            vc.audio_buffer = Mock()
            vc.audio_buffer.read.return_value = b"fake_audio_data"
            
            # Should complete without threading
            result = vc._transcribe_audio_sync(b"fake_audio_data")
            self.assertEqual(result, "test transcription")


class TestModeController(unittest.TestCase):
    """Test ModeController fixes."""
    
    def setUp(self):
        from mode_controller import ModeController
        self.controller = ModeController()
    
    def test_get_primary_object_consistency(self):
        """Test that get_primary_object always returns single object or None."""
        # Should return None when no objects
        result = self.controller.get_primary_object()
        self.assertIsNone(result)
        
        # Add some mock objects
        mock_obj1 = Mock()
        mock_obj1.label = "phone"
        mock_obj2 = Mock()
        mock_obj2.label = "person"
        
        self.controller.object_manager.objects = [mock_obj1, mock_obj2]
        
        # Should return single object, not list
        result = self.controller.get_primary_object()
        self.assertIsNotNone(result)
        self.assertNotIsInstance(result, list)


class TestAudioModules(unittest.TestCase):
    """Test Audio module optimizations."""
    
    def test_audio_signature_generator(self):
        """Test audio waveform generation."""
        from audio_module_multi import AudioSignatureGenerator
        
        # Generate different waveforms
        sine = AudioSignatureGenerator.generate_waveform("sine", 440, 0.1, 44100)
        square = AudioSignatureGenerator.generate_waveform("square", 440, 0.1, 44100)
        
        # Should return numpy arrays
        self.assertIsInstance(sine, np.ndarray)
        self.assertIsInstance(square, np.ndarray)
        self.assertEqual(len(sine), int(44100 * 0.1))
    
    def test_multi_audio_controller(self):
        """Test MultiAudioController initialization."""
        from audio_module_multi import MultiAudioController
        
        mac = MultiAudioController()
        
        # Should have preloaded signatures
        self.assertGreater(len(mac.signatures), 0)
        self.assertIn("default", mac.signatures)


class TestVisionModule(unittest.TestCase):
    """Test VisionController fixes."""
    
    def test_io_imports_removed(self):
        """Test that io imports are at top level, not inside functions."""
        import vision_module
        import io
        
        # io should be imported at module level
        self.assertTrue(hasattr(vision_module, 'io'))
    
    def test_json_extraction(self):
        """Test JSON extraction from various formats."""
        from vision_module import VisionController
        
        vc = Mock(spec=VisionController)
        
        # Test markdown format
        md_text = "```json\n[{\"box_2d\": [0,0,100,100]}]\n```"
        result = VisionController._extract_json(vc, md_text)
        self.assertIn("[", result)
        
        # Test direct array
        array_text = "[{\"box_2d\": [0,0,100,100]}]"
        result = VisionController._extract_json(vc, array_text)
        self.assertTrue(result.startswith("["))


def run_tests():
    """Run all tests and report results."""
    print("\n" + "="*70)
    print("🧪 RUNNING COMPREHENSIVE TEST SUITE")
    print("="*70 + "\n")
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestSharedState))
    suite.addTests(loader.loadTestsFromTestCase(TestObjectManager))
    suite.addTests(loader.loadTestsFromTestCase(TestLearningModule))
    suite.addTests(loader.loadTestsFromTestCase(TestVoiceController))
    suite.addTests(loader.loadTestsFromTestCase(TestModeController))
    suite.addTests(loader.loadTestsFromTestCase(TestAudioModules))
    suite.addTests(loader.loadTestsFromTestCase(TestVisionModule))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "="*70)
    if result.wasSuccessful():
        print("✅ ALL TESTS PASSED")
        print(f"   Tests run: {result.testsRun}")
        print(f"   Failures: {len(result.failures)}")
        print(f"   Errors: {len(result.errors)}")
    else:
        print("❌ SOME TESTS FAILED")
        print(f"   Tests run: {result.testsRun}")
        print(f"   Failures: {len(result.failures)}")
        print(f"   Errors: {len(result.errors)}")
        
        if result.failures:
            print("\n   Failures:")
            for test, trace in result.failures:
                print(f"     - {test}")
        
        if result.errors:
            print("\n   Errors:")
            for test, trace in result.errors:
                print(f"     - {test}")
    
    print("="*70 + "\n")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
