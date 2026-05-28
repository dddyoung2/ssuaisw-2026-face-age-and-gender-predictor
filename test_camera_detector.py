
import time
from camera_detector import CameraDetector

detector = None

def on_single_person_detected():
    print("[TEST] �� 1�� ������ �� �Կ� ����")
    if detector is not None and not detector.is_recording:
        detector.start_recording()

def on_no_single_person():
    print("[TEST] ���� ���ų� ���� ���Դϴ�.")

def on_frames_ready(frames):
    print(f"[TEST] 40������ ���� �Ϸ�: {len(frames)}��")

    if frames:
        print(f"[TEST] ù ������ shape: {frames[0].shape}")

    detector.stop()

detector = CameraDetector(
    on_single_person_detected=on_single_person_detected,
    on_no_single_person=on_no_single_person,
    on_frames_ready=on_frames_ready,
    camera_index=0,
)

detector.start()

try:
    while detector._running:
        time.sleep(1)
except KeyboardInterrupt:
    detector.stop()