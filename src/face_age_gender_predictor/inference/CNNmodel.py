# -*- coding: utf-8 -*-
"""Face preprocessing and TorchScript inference API.

The module has no import-time model loading side effects. The GUI controller
calls ``predict_frames`` directly from the single Qt event loop in this branch.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

import cv2
import numpy as np

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "True")

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MODEL_RELPATH = "models/Best_Age_Estimate_model_traced.pt"
MODEL_INPUT_SIZE = 224
AGE_MIN = 15
AGE_MAX = 40

_torch = None
_transform = None
_cached_model = None
_cached_model_path = None
_cached_device = None


def get_default_model_path() -> Path:
    return _REPO_ROOT / "models" / "Best_Age_Estimate_model_traced.pt"


def detect_and_align(
    image_bgr: np.ndarray,
    target_size: int = MODEL_INPUT_SIZE,
    margin: float = 0.45,
) -> Optional[np.ndarray]:
    import mediapipe as mp

    mp_face_detection = mp.solutions.face_detection
    h, w = image_bgr.shape[:2]
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

    with mp_face_detection.FaceDetection(
        model_selection=1,
        min_detection_confidence=0.5,
    ) as face_detection:
        results = face_detection.process(image_rgb)

    if not results.detections:
        return None

    best_detection = max(results.detections, key=lambda item: item.score[0])
    bbox = best_detection.location_data.relative_bounding_box
    x1 = int(bbox.xmin * w)
    y1 = int(bbox.ymin * h)
    box_w = int(bbox.width * w)
    box_h = int(bbox.height * h)
    x2 = x1 + box_w
    y2 = y1 + box_h

    keypoints = best_detection.location_data.relative_keypoints
    right_eye_rel = keypoints[0]
    left_eye_rel = keypoints[1]
    left_eye = (int(left_eye_rel.x * w), int(left_eye_rel.y * h))
    right_eye = (int(right_eye_rel.x * w), int(right_eye_rel.y * h))

    aligned = _rotate_by_eyes(image_bgr, left_eye, right_eye)
    x1, y1, x2, y2 = _expand_to_square_box(
        x1,
        y1,
        x2,
        y2,
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


def _rotate_by_eyes(
    image: np.ndarray,
    left_eye: tuple,
    right_eye: tuple,
) -> np.ndarray:
    le = np.array(left_eye)
    re = np.array(right_eye)
    dx, dy = le - re
    angle = np.degrees(np.arctan2(dy, dx))

    if angle > 90:
        angle -= 180
    elif angle < -90:
        angle += 180

    cx, cy = (le + re) / 2
    matrix = cv2.getRotationMatrix2D((float(cx), float(cy)), float(angle), 1.0)
    return cv2.warpAffine(
        image,
        matrix,
        (image.shape[1], image.shape[0]),
        flags=cv2.INTER_CUBIC,
    )


@dataclass
class PreprocessResult:
    success: bool
    face_crop: Optional[np.ndarray]


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
    """AFAD dataset preprocessing helper. It is not used by the GUI path."""

    GENDER_CODES = {"111", "112"}

    def __init__(self, root_dir: str, target_size: int = MODEL_INPUT_SIZE):
        self.root = Path(root_dir)
        self.target_size = target_size
        self.samples = self._scan()
        print(f"[AFADPreprocessor] {len(self.samples):,}개 샘플을 찾았습니다.")

    def run(self, output_dir: str, num_workers: int = 4):
        from tqdm import tqdm

        _ = num_workers
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        ok = fail = 0
        for sample in tqdm(self.samples, total=len(self.samples), desc="Preprocessing AFAD"):
            if self._process_one(sample, out):
                ok += 1
            else:
                fail += 1
        print(f"[전처리 완료] 성공 {ok:,}개 / 실패 {fail:,}개")

    def _scan(self) -> List[tuple]:
        samples = []
        for age_dir in sorted(self.root.iterdir()):
            if not age_dir.is_dir():
                continue
            try:
                age = int(age_dir.name)
            except ValueError:
                continue
            for g_dir in age_dir.iterdir():
                if g_dir.name not in self.GENDER_CODES:
                    continue
                for img in g_dir.glob("*.jpg"):
                    samples.append((img, age))
        return samples

    def _process_one(self, sample: tuple, out_root: Path) -> bool:
        img_path, age = sample
        bgr = cv2.imread(str(img_path))
        if bgr is None:
            return False

        face_rgb = detect_and_align(bgr, self.target_size)
        if face_rgb is None:
            resized = cv2.resize(bgr, (self.target_size, self.target_size))
            face_rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

        out_dir = out_root / str(age)
        out_dir.mkdir(exist_ok=True, parents=True)
        cv2.imwrite(
            str(out_dir / img_path.name),
            cv2.cvtColor(face_rgb, cv2.COLOR_RGB2BGR),
            [cv2.IMWRITE_JPEG_QUALITY, 95],
        )
        return True


def _import_torch():
    global _torch
    if _torch is None:
        import torch

        _torch = torch
    return _torch


def _resolve_device():
    torch = _import_torch()
    if torch.cuda.is_available():
        return torch.device("cuda")
    if hasattr(torch, "backends") and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def _get_transform():
    global _transform
    if _transform is None:
        from torchvision import transforms

        _transform = transforms.Compose(
            [
                transforms.ToPILImage(),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406],
                    std=[0.229, 0.224, 0.225],
                ),
            ]
        )
    return _transform


def load_model(model_path=None):
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
    global _cached_model, _cached_model_path, _cached_device
    _cached_model = None
    _cached_model_path = None
    _cached_device = None


def _as_float(value) -> float:
    if hasattr(value, "item"):
        return float(value.item())
    return float(value)


def _as_float_list(value) -> List[float]:
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "numpy"):
        value = value.numpy()
    arr = np.asarray(value, dtype=float).reshape(-1)
    return [float(item) for item in arr.tolist()]


def predict_frames(
    frames: List[np.ndarray],
    model_path=None,
    progress_callback: Optional[Callable[[int], None]] = None,
) -> List[dict]:
    if not frames:
        return []

    model, device = _get_cached_model(model_path)
    predictions: List[dict] = []

    for index, frame in enumerate(frames, start=1):
        face_rgb = detect_and_align(frame, target_size=MODEL_INPUT_SIZE)

        if face_rgb is not None:
            predicted_age, predicted_gender, age_probs, gender_confidence = _run_model(
                model,
                device,
                face_rgb,
            )
            predictions.append(
                {
                    "age": _as_float(predicted_age),
                    "gender": _as_float(predicted_gender),
                    "age_probs": _as_float_list(age_probs),
                    "gender_confidence": _as_float(gender_confidence),
                }
            )

        if progress_callback is not None:
            progress_callback(index)

    return predictions


def _run_model(model, device, face_rgb: np.ndarray):
    torch = _import_torch()
    transform = _get_transform()
    input_tensor = transform(face_rgb).unsqueeze(0).to(device)

    with torch.no_grad():
        return model(input_tensor)
