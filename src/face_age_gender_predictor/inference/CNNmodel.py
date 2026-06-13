# -*- coding: utf-8 -*-
"""
CNNmodel.py
===========
얼굴 이미지 전처리와 TorchScript 모델 추론을 담당하는 모듈.

이 모듈을 import하는 것만으로는 모델을 로드하거나 샘플 이미지를 읽거나
샘플 추론/그래프를 실행하지 않는다. 무거운 라이브러리(torch / torchvision /
mediapipe)와 실제 TorchScript 모델은 추론이 요청될 때(predict_frames 호출 시)
지연 로드(lazy load)된다.

앱(InferenceWorker)에서 사용하는 공개 API:

    def predict_frames(frames: list) -> list[dict]:
        ...

각 prediction dict는 result_processor.process_predictions와 호환된다.

    {
        "age": float,
        "gender": float,            # 모델 성별 클래스(0/1) 원시값
        "age_probs": list[float],   # 나이 확률분포 (15~40세, 26개)
        "gender_confidence": float,
    }
"""

import os

# torch + OpenMP 동시 로드 시 발생하는 충돌 방지 (실제 충돌 환경 보호용)
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "True")

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

import cv2
import numpy as np

# ============================================================
# 모델 경로 / 설정
# ============================================================

# repo 루트 기준 기본 모델 경로.
# __file__ = <repo>/src/face_age_gender_predictor/inference/CNNmodel.py
# parents[0]=inference, [1]=face_age_gender_predictor, [2]=src, [3]=<repo 루트>
_REPO_ROOT = Path(__file__).resolve().parents[3]

# 기대 모델 경로(상대 표기). 오류 메시지에서 사용자에게 그대로 안내한다.
DEFAULT_MODEL_RELPATH = "models/Best_Age_Estimate_model_traced.pt"

MODEL_INPUT_SIZE = 224  # 모델 입력 정사각형 크기
AGE_MIN = 15            # 나이 확률분포 시작 나이
AGE_MAX = 40            # 나이 확률분포 끝 나이 (26개 클래스: 15~40)

# 지연 로드된 라이브러리/모델 캐시
_torch = None                 # import된 torch 모듈 캐시
_transform = None             # torchvision 전처리 transform 캐시
_cached_model = None          # 로드된 TorchScript 모델 캐시
_cached_model_path = None     # 캐시된 모델의 경로(str)
_cached_device = None         # 캐시된 device


def get_default_model_path() -> Path:
    """repo 루트 기준 기본 TorchScript 모델 경로를 반환한다.

    현재 작업 디렉터리(cwd)와 무관하게 항상 repo 루트의
    models/Best_Age_Estimate_model_traced.pt 로 해석된다.
    """
    return _REPO_ROOT / "models" / "Best_Age_Estimate_model_traced.pt"


# ============================================================
# 얼굴 전처리 (mediapipe 기반 검출 + 정렬)
# ============================================================

def detect_and_align(image_bgr: np.ndarray,
                     target_size: int = MODEL_INPUT_SIZE,
                     margin: float = 0.45) -> Optional[np.ndarray]:
    """BGR 프레임에서 얼굴을 검출/정렬해 RGB (target_size x target_size) 이미지를 반환한다.

    얼굴이 없으면 None을 반환한다. mediapipe는 이 함수 안에서 지연 import된다.
    """
    import mediapipe as mp  # 지연 import (모듈 import 시점 부작용 방지)

    mp_face_detection = mp.solutions.face_detection

    h, w = image_bgr.shape[:2]

    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

    with mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5) as face_detection:
        results = face_detection.process(image_rgb)

        if not results.detections:
            return None

        best_detection = max(results.detections, key=lambda x: x.score[0])

        bbox = best_detection.location_data.relative_bounding_box
        x1 = int(bbox.xmin * w)
        y1 = int(bbox.ymin * h)
        box_w = int(bbox.width * w)
        box_h = int(bbox.height * h)
        x2, y2 = x1 + box_w, y1 + box_h

        keypoints = best_detection.location_data.relative_keypoints
        right_eye_rel = keypoints[0]
        left_eye_rel = keypoints[1]

        left_eye = (int(left_eye_rel.x * w), int(left_eye_rel.y * h))
        right_eye = (int(right_eye_rel.x * w), int(right_eye_rel.y * h))

        aligned = _rotate_by_eyes(image_bgr, left_eye, right_eye)

        x1, y1, x2, y2 = _expand_to_square_box(
            x1, y1, x2, y2,
            image_width=w,
            image_height=h,
            margin=margin,
        )
        face = aligned[y1:y2, x1:x2]

        if face.size == 0:
            return None

        face = cv2.resize(face, (target_size, target_size))
        return cv2.cvtColor(face, cv2.COLOR_BGR2RGB)


def _expand_to_square_box(
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    image_width: int,
    image_height: int,
    margin: float = 0.45,
) -> tuple[int, int, int, int]:
    """Expand a face bbox to a clamped square crop that keeps the whole face.

    Face detectors often return a tight inner-face rectangle. The model and
    result preview work better when the crop includes forehead, chin, and ears,
    so expand around the bbox center and make the crop square before resizing.
    """
    box_w = max(1, x2 - x1)
    box_h = max(1, y2 - y1)
    side = int(max(box_w, box_h) * (1.0 + margin * 2.0))

    cx = (x1 + x2) // 2
    cy = (y1 + y2) // 2
    nx1 = cx - side // 2
    ny1 = cy - side // 2
    nx2 = nx1 + side
    ny2 = ny1 + side

    if nx1 < 0:
        nx2 -= nx1
        nx1 = 0
    if ny1 < 0:
        ny2 -= ny1
        ny1 = 0
    if nx2 > image_width:
        shift = nx2 - image_width
        nx1 = max(0, nx1 - shift)
        nx2 = image_width
    if ny2 > image_height:
        shift = ny2 - image_height
        ny1 = max(0, ny1 - shift)
        ny2 = image_height

    return int(nx1), int(ny1), int(nx2), int(ny2)


def _rotate_by_eyes(image: np.ndarray,
                    left_eye: tuple,
                    right_eye: tuple) -> np.ndarray:
    le = np.array(left_eye)
    re = np.array(right_eye)

    dx, dy = le - re
    angle = np.degrees(np.arctan2(dy, dx))

    if angle > 90:
        angle -= 180
    elif angle < -90:
        angle += 180

    cx, cy = (le + re) / 2

    M = cv2.getRotationMatrix2D((float(cx), float(cy)), float(angle), 1.0)
    return cv2.warpAffine(image, M, (image.shape[1], image.shape[0]), flags=cv2.INTER_CUBIC)


@dataclass
class PreprocessResult:
    success   : bool
    face_crop : Optional[np.ndarray]


class FacePreprocessor:
    def __init__(self, target_size: int = MODEL_INPUT_SIZE):
        self.target_size = target_size

    def process(self, raw_bgr: np.ndarray) -> PreprocessResult:
        face_rgb = detect_and_align(raw_bgr, self.target_size)

        if face_rgb is None:
            return PreprocessResult(success=False, face_crop=None)

        face_bgr = cv2.cvtColor(face_rgb, cv2.COLOR_RGB2BGR)
        return PreprocessResult(success=True, face_crop=face_bgr)


class AFADPreprocessor:
    """AFAD 데이터셋 전처리(학습/데이터 준비용). 추론 경로에서는 사용하지 않는다."""

    GENDER_CODES = {"111", "112"}

    def __init__(self, root_dir: str, target_size: int = MODEL_INPUT_SIZE):
        self.root = Path(root_dir)
        self.target_size = target_size
        self.samples = self._scan()
        print(f"[AFADPreprocessor] {len(self.samples):,}개 샘플을 찾았습니다.")

    def run(self, output_dir: str, num_workers: int = 4):
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from tqdm import tqdm

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        with ThreadPoolExecutor(max_workers=num_workers) as pool:
            futures = {pool.submit(self._process_one, s, out): s for s in self.samples}
            ok = fail = 0
            for f in tqdm(as_completed(futures), total=len(futures), desc="Preprocessing AFAD"):
                if f.result():
                    ok += 1
                else:
                    fail += 1
        print(f"[전처리 완료] 성공 {ok:,}개 / 실패 {fail:,}개")

    def _scan(self) -> List[tuple]:
        samples = []
        for age_dir in sorted(self.root.iterdir()):
            if not age_dir.is_dir(): continue
            try: age = int(age_dir.name)
            except ValueError: continue
            for g_dir in age_dir.iterdir():
                if g_dir.name not in self.GENDER_CODES: continue
                for img in g_dir.glob("*.jpg"):
                    samples.append((img, age))
        return samples

    def _process_one(self, sample: tuple, out_root: Path) -> bool:
        img_path, age = sample
        bgr = cv2.imread(str(img_path))
        if bgr is None: return False

        face_rgb = detect_and_align(bgr, self.target_size)

        if face_rgb is None:
            face_rgb = cv2.cvtColor(cv2.resize(bgr, (self.target_size, self.target_size)), cv2.COLOR_BGR2RGB)

        out_dir = out_root / str(age)
        out_dir.mkdir(exist_ok=True, parents=True)
        cv2.imwrite(str(out_dir / img_path.name), cv2.cvtColor(face_rgb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 95])
        return True


# ============================================================
# TorchScript 모델 로드 (지연 + 캐시)
# ============================================================

def _import_torch():
    """torch 모듈을 지연 import해서 캐시한다."""
    global _torch
    if _torch is None:
        import torch  # 지연 import
        _torch = torch
    return _torch


def _resolve_device():
    """사용 가능한 추론 device를 결정한다."""
    torch = _import_torch()
    if torch.cuda.is_available():
        return torch.device("cuda")
    if hasattr(torch, "backends") and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def _get_transform():
    """torchvision 전처리 transform을 지연 생성해 캐시한다."""
    global _transform
    if _transform is None:
        from torchvision import transforms  # 지연 import
        _transform = transforms.Compose([
            transforms.ToPILImage(),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
    return _transform


def load_model(model_path=None):
    """TorchScript 모델을 로드해서 (model, device)를 반환한다.

    파일이 없으면 기대 경로를 명시한 FileNotFoundError를 발생시킨다.
    (torch import보다 파일 존재 확인을 먼저 해서, 파일이 없을 때는 무거운 torch
    로드 없이 즉시 명확한 오류를 낸다.)
    """
    resolved = Path(model_path) if model_path is not None else get_default_model_path()

    if not resolved.exists():
        raise FileNotFoundError(
            "TorchScript 모델 파일을 찾을 수 없습니다. "
            f"기대 경로: {DEFAULT_MODEL_RELPATH} "
            f"(확인한 절대 경로: {resolved})"
        )

    torch = _import_torch()
    device = _resolve_device()
    model = torch.jit.load(str(resolved), map_location=device)
    model.eval()
    return model, device


def _get_cached_model(model_path=None):
    """로드된 모델을 캐시해 반복 측정 시 재로드하지 않는다."""
    global _cached_model, _cached_model_path, _cached_device

    resolved = Path(model_path) if model_path is not None else get_default_model_path()
    resolved_str = str(resolved)

    if _cached_model is not None and _cached_model_path == resolved_str:
        return _cached_model, _cached_device

    model, device = load_model(resolved)
    _cached_model = model
    _cached_model_path = resolved_str
    _cached_device = device
    return model, device


def reset_model_cache():
    """캐시된 모델을 해제한다(테스트/재로드용)."""
    global _cached_model, _cached_model_path, _cached_device
    _cached_model = None
    _cached_model_path = None
    _cached_device = None


# ============================================================
# 텐서 변환 헬퍼 (실제 torch 텐서와 테스트용 fake 모두 지원)
# ============================================================

def _as_float(value) -> float:
    """스칼라 텐서/숫자를 float으로 변환한다."""
    if hasattr(value, "item"):
        return float(value.item())
    return float(value)


def _as_float_list(value) -> List[float]:
    """확률분포 텐서/배열을 1차원 float 리스트로 변환한다."""
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "numpy"):
        value = value.numpy()
    arr = np.asarray(value, dtype=float).reshape(-1)
    return [float(x) for x in arr.tolist()]


# ============================================================
# 추론 공개 API
# ============================================================

def predict_frames(
    frames: List[np.ndarray],
    model_path=None,
    progress_callback: Optional[Callable[[int], None]] = None,
) -> List[dict]:
    """40프레임(BGR ndarray 리스트)을 받아 prediction dict 리스트를 반환한다.

    - 모델은 지연 로드되며 반복 호출 시 캐시를 재사용한다.
    - 얼굴 전처리에 실패한 프레임은 건너뛴다(전역/치명적 실패가 아닌 경우).
    - 모델 파일 없음/로드 실패/추론 실패 같은 전역 오류는 예외로 전파되어
      InferenceWorker가 error_occurred로 GUI에 전달한다.

    progress_callback이 주어지면 프레임을 하나 처리할 때마다(건너뛴 경우 포함)
    1부터 시작하는 처리 인덱스를 인자로 호출한다.
    """
    if not frames:
        return []

    model, device = _get_cached_model(model_path)

    predictions: List[dict] = []

    for index, frame in enumerate(frames, start=1):
        # 얼굴 미검출(detect_and_align이 None 반환)만 해당 프레임을 건너뛴다.
        # mediapipe/torchvision import 실패, OpenCV 처리 오류, 전처리 코드 버그 같은
        # 치명적 전처리 실패는 예외로 전파되어 InferenceWorker.error_occurred로 도달한다.
        # (빈 prediction으로 숨기지 않는다 — 원인을 잃지 않기 위함)
        face_rgb = detect_and_align(frame, target_size=MODEL_INPUT_SIZE)

        if face_rgb is not None:
            predicted_age, predicted_gender, age_probs, gender_confidence = _run_model(
                model, device, face_rgb
            )

            predictions.append({
                "age": _as_float(predicted_age),
                "gender": _as_float(predicted_gender),
                "age_probs": _as_float_list(age_probs),
                "gender_confidence": _as_float(gender_confidence),
            })

        if progress_callback is not None:
            progress_callback(index)

    return predictions


def _run_model(model, device, face_rgb: np.ndarray):
    """torch에 의존하는 유일한 추론 구간.

    전처리된 RGB 얼굴 이미지를 입력 텐서로 변환해 모델을 1회 실행하고,
    (predicted_age, predicted_gender, age_probs, gender_confidence)를 반환한다.
    torch/torchvision은 이 함수 안에서만 사용되므로, 테스트는 이 함수를 대체해
    torch 없이 predict_frames의 집계/skip/progress 로직을 검증할 수 있다.
    """
    torch = _import_torch()
    transform = _get_transform()

    input_tensor = transform(face_rgb).unsqueeze(0).to(device)

    with torch.no_grad():
        return model(input_tensor)
