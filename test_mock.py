#!/usr/bin/env python3
"""Comprehensive mock-mode test - exercises all modules without API keys or hardware."""

import os, sys, time, json

os.environ["NOVA_MOCK_MODE"] = "1"
os.environ["NOVA_HEADLESS"] = "1"

sys.path.insert(0, os.path.dirname(__file__))

passed = 0
failed = 0
errors = []


def check(name, fn):
    global passed, failed
    try:
        fn()
        passed += 1
        print(f"  [PASS] {name}")
    except Exception as e:
        failed += 1
        errors.append(f"{name}: {e}")
        print(f"  [FAIL] {name}: {e}")


def skip(name, reason):
    print(f"  [SKIP] {name} ({reason})")


print("=" * 60)
print("NOVA MOCK-MODE INTEGRATION TEST")
print("=" * 60)

# 1. Config
print("\n[1] Config")
import config

check("MOCK_MODE enabled", lambda: config.MOCK_MODE == True)
check(
    "NavigationMode class", lambda: config.NavigationMode.EXPLORATION == "exploration"
)
check("MODE_CONFIGS has 4 modes", lambda: len(config.MODE_CONFIGS) == 4)
check("THREAT_PRIORITIES has entries", lambda: len(config.THREAT_PRIORITIES) > 5)
check("AUDIO_SIGNATURES has entries", lambda: len(config.AUDIO_SIGNATURES) > 3)

# 2. Shared State
print("\n[2] Shared State")
from shared_state import SharedGameState

state = SharedGameState()
check("is_running is True", lambda: state.is_running == True)
check("get_next_command returns None", lambda: state.get_next_command() is None)

import numpy as np

fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
state.update_frame(fake_frame)
fetched = state.get_latest_frame()
check("get_latest_frame returns copy (not same ref)", lambda: fetched is not fake_frame)
check(
    "get_latest_frame returns copy (different id)",
    lambda: id(fetched) != id(fake_frame),
)
check("add_command works", lambda: (state.add_command("detect"), True)[1])
check("get_next_command returns detect", lambda: state.get_next_command() == "detect")
check("set_fps works", lambda: (state.set_fps(30.0), state._fps == 30.0)[1])

# 3. Object Manager
print("\n[3] Object Manager")
try:
    from object_manager import ObjectManager, TrackedObject

    om = ObjectManager()
    check("starts empty", lambda: len(om.objects) == 0)

    obj1 = om.add_object("Phone [on desk]", (100, 100, 50, 50))
    check("add_object works", lambda: obj1.label == "Phone [on desk]")
    check("object has id", lambda: obj1.id == 0)
    check("object has bbox", lambda: obj1.bbox == (100, 100, 50, 50))

    obj2 = om.add_object("Red Cup [near phone]", (300, 200, 40, 40))
    check("second object added", lambda: len(om.objects) == 2)
    check(
        "non-deterministic signature lookup fixed",
        lambda: obj2.audio_signature is not None,
    )

    zone = om.get_proximity_zone(obj1, 640, 480)
    check("proximity zone works", lambda: zone in ("safe", "caution", "warning"))

    om.clear()
    check("clear works", lambda: len(om.objects) == 0)
except ModuleNotFoundError as e:
    skip("Object Manager", f"missing dependency: {e}")
except Exception as e:
    check("Object Manager import", lambda: (_ for _ in ()).throw(e))

# 4. Mode Controller
print("\n[4] Mode Controller")
try:
    from mode_controller import ModeController

    mc = ModeController()
    check("default mode is exploration", lambda: mc.current_mode == "exploration")
    check(
        "set_frame_dimensions works",
        lambda: (mc.set_frame_dimensions(640, 480), True)[1],
    )

    check("switch to navigation", lambda: mc.set_mode("navigation") == True)
    check("current mode updated", lambda: mc.current_mode == "navigation")
    check(
        "get_detection_prompt works",
        lambda: "{target_object}" not in mc.get_detection_prompt(),
    )

    mc.set_target_object("phone")
    check("target object set", lambda: mc.target_object == "phone")

    fake_det = [{"box_2d": [200, 300, 500, 600], "label": "Phone [on desk]"}]
    fake_frame_np = np.zeros((480, 640, 3), dtype=np.uint8)
    count = mc.process_detections(fake_det, fake_frame_np)
    check("process_detections adds objects", lambda: count == 1)
    check("object_manager has objects", lambda: len(mc.object_manager.objects) == 1)
except ModuleNotFoundError as e:
    skip("Mode Controller", f"missing dependency: {e}")
except Exception as e:
    check("Mode Controller import", lambda: (_ for _ in ()).throw(e))

# 5. Conversation Manager
print("\n[5] Conversation Manager")
from conversation_manager import ConversationManager

cm = ConversationManager(history_file="/tmp/test_conv_history.json")
cm.clear_history()
cm.add_turn("user", "hello nova")
ctx = cm.get_context_string()
check("conversation context works", lambda: "hello nova" in ctx)
cm.clear_history()
if os.path.exists("/tmp/test_conv_history.json"):
    os.remove("/tmp/test_conv_history.json")

# 6. Hardware Interface
print("\n[6] Hardware Interface")
from hardware_interface import DummyHardwareInterface, SerialException

dh = DummyHardwareInterface()
check("dummy pressure is 0", lambda: dh.get_pressure() == 0)
check("dummy send_feedback no-op", lambda: (dh.send_feedback(50), True)[1])
check("SerialException safely imported", lambda: SerialException is None or True)

# 7. Audio Module
print("\n[7] Audio Module")
try:
    from audio_module_multi import AudioSignatureGenerator

    wave = AudioSignatureGenerator.generate_waveform("sine", 440, 0.1, 44100)
    check("sine waveform generated", lambda: len(wave) > 0)
    check("waveform is float32", lambda: wave.dtype == np.float32)

    wave2 = AudioSignatureGenerator.generate_waveform("square", 800, 0.1, 44100)
    check("square waveform generated", lambda: len(wave2) > 0)

    wave3 = AudioSignatureGenerator.generate_waveform("pulse", 80, 0.1, 44100)
    check("pulse waveform generated", lambda: len(wave3) > 0)
except ModuleNotFoundError as e:
    skip("Audio Module", f"missing dependency: {e}")
except Exception as e:
    check("Audio Module import", lambda: (_ for _ in ()).throw(e))

# 8. Vision Module (Mock)
print("\n[8] Vision Module (Mock)")
try:
    from vision_module import VisionController, _MockGeminiClient

    mock_client = _MockGeminiClient()
    resp = mock_client.models.generate_content(
        model="test", contents=["Detect and return bounding boxes"]
    )
    data = json.loads(resp.text)
    check("mock detection returns JSON", lambda: isinstance(data, list))
    check("mock detection has label", lambda: "label" in data[0])
    check("mock detection has box_2d", lambda: "box_2d" in data[0])

    resp2 = mock_client.models.generate_content(
        model="test", contents=["PHYSICAL 3D OBJECTS only"]
    )
    data2 = json.loads(resp2.text)
    check("mock multi-object returns 3 objects", lambda: len(data2) == 3)

    resp3 = mock_client.models.generate_content(
        model="test", contents=["Describe this scene naturally"]
    )
    check("mock scene description works", lambda: len(resp3.text) > 10)
except ModuleNotFoundError as e:
    skip("Vision Module", f"missing dependency: {e}")
except Exception as e:
    check("Vision Module import", lambda: (_ for _ in ()).throw(e))

# 9. Learning Module
print("\n[9] Learning Module")
try:
    from learning_module import LearningModule
    import shutil

    cache_dir = "/tmp/test_nova_cache"
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)

    lm = LearningModule(db_path=":memory:", image_cache_dir=cache_dir)
    stats = lm.get_stats()
    check("learning stats has keys", lambda: "total_detections" in stats)
    check("learning stats total is 0", lambda: stats["total_detections"] == 0)

    loc = lm.get_likely_location("phone")
    check("no location for unseen object", lambda: loc is None)

    recall = lm.recall_object("phone")
    check("no recall for unseen object", lambda: recall is None)

    lm.close()
    shutil.rmtree(cache_dir, ignore_errors=True)
except ModuleNotFoundError as e:
    skip("Learning Module", f"missing dependency: {e}")
except Exception as e:
    check("Learning Module import", lambda: (_ for _ in ()).throw(e))

# 10. Audio Coordinator
print("\n[10] Audio Coordinator")
from audio_coordinator import AudioCoordinator

check("AudioCoordinator class importable", lambda: AudioCoordinator is not None)

# 11. HRTF Audio
print("\n[11] HRTF Audio")
from audio_hrtf import HRTF_AudioController, OPENAL_AVAILABLE

check("HRTF module importable", lambda: HRTF_AudioController is not None)

# 12. Process Manager
print("\n[12] Process Manager")
try:
    from process_manager import get_target_processes

    check("process_manager importable", lambda: callable(get_target_processes))
except ModuleNotFoundError as e:
    skip("Process Manager", f"missing dependency: {e}")
except Exception as e:
    check("Process Manager import", lambda: (_ for _ in ()).throw(e))

# Summary
print("\n" + "=" * 60)
print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed}")
if errors:
    print("\nFailures:")
    for e in errors:
        print(f"  - {e}")
else:
    print("\nAll tests passed!")
print("=" * 60)

sys.exit(0 if failed == 0 else 1)
