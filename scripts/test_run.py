import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
"""
test_run.py
===========
camera_detector.py + result_processor.py 동작 확인용 테스트
모델팀 연동 전에 단독으로 실행해서 흐름을 확인할 수 있습니다.
"""

import os
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cv2

import random
from face_age_gender_predictor.camera.camera_detector import CameraDetector
from face_age_gender_predictor.processing.result_processor import process_predictions

face_ready = False
recording_requested = False
# ── 콜백 정의 ─────────────────────────────────────────────────────────────────

def on_single_person_detected():
    """얼굴 감지 신호 → 준비 완료 상태로만 변경"""
    global face_ready

    face_ready = True
    print("[테스트] 얼굴 감지됨 → 준비 완료")
    
def on_no_single_person():
    """얼굴 미감지 또는 준비 해제"""
    global face_ready

    face_ready = False
    print("[테스트] 얼굴 미감지 → 준비 해제")

def on_frames_ready(frames):
    """40프레임 수신 → 모델팀에 전달 후 결과 처리"""
    print(f"[테스트] {len(frames)}개 프레임 → 모델팀 전달 (시뮬레이션)")

    # 모델팀 응답 시뮬레이션
    # result_processor.py가 dict 리스트를 기대하므로 dict 형태로 생성
    fake_predictions = [
        {
            "age": random.uniform(20, 40),
            "gender": random.uniform(0, 1),
            "age_probs": [1 / 26] * 26,
            "gender_confidence": random.uniform(0.7, 1.0),
        }
        for _ in range(40)
    ]

    process_predictions(fake_predictions, on_result_ready=on_result_ready)
    


def on_result_ready(result: dict):
    """최종 결과 수신 → GUI팀에 전달"""
    global recording_requested

    print(
        f"[테스트] GUI팀에 전달 → "
        f"나이: {result['age']:.1f}세, "
        f"성별: {result['gender']}, "
        f"성별 확신도: {result['gender_confidence'] * 100:.1f}%"
    )

    recording_requested = False


# ── 실행 ──────────────────────────────────────────────────────────────────────

detector = CameraDetector(
    on_single_person_detected=on_single_person_detected,
    on_no_single_person=on_no_single_person,
    on_frames_ready=on_frames_ready,
    camera_index=0,
)

detector.start()

print("미리보기 시작 (종료: q키 | 감지 재개: r키 | 촬영시작: s키)")
try:
    while detector._running:
        frame = detector._latest_frame
        if frame is None:
            time.sleep(0.01)
            continue

        display = frame.copy()
        for (x, y, w, h) in detector._latest_faces:
            cv2.rectangle(display, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.putText(display, f"감지: {len(detector._latest_faces)}명", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        if detector._recording:
            cv2.putText(display, "REC", (10, 65),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        if not detector._detecting:
            cv2.putText(display, "대기중 (r: 재개)", (10, 100),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2)

        cv2.imshow("카메라 미리보기", display)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            detector.stop()
            break

        elif key == ord('r'):
            detector.resume_detection()

        elif key == ord('s'):
            if not face_ready:
                print("[테스트] 얼굴이 준비되지 않았습니다.")
                continue

            if detector.is_recording or recording_requested:
                print("[테스트] 이미 촬영 중입니다.")
                continue

            recording_requested = True
            print("[테스트] 측정 시작 요청 → 40프레임 촬영")
            detector.start_recording()
except KeyboardInterrupt:
    detector.stop()
print("종료됨")
