# -*- coding: utf-8 -*-
"""
CNNmodel.py
===========
얼굴 이미지 전처리, TorchScript 모델 로드, 나이/성별 추론 결과 출력 예제 코드입니다.
"""
import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'
import cv2
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import mediapipe as mp

mp_face_detection = mp.solutions.face_detection

def detect_and_align(image_bgr: np.ndarray,
                     target_size: int = 224,
                     margin: float = 0.2) -> np.ndarray | None:

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

        dx = int(box_w * margin)
        dy = int(box_h * margin)
        x1, y1 = max(0, x1 - dx), max(0, y1 - dy)
        x2, y2 = min(w, x2 + dx), min(h, y2 + dy)

        keypoints = best_detection.location_data.relative_keypoints
        right_eye_rel = keypoints[0]
        left_eye_rel = keypoints[1]

        left_eye = (int(left_eye_rel.x * w), int(left_eye_rel.y * h))
        right_eye = (int(right_eye_rel.x * w), int(right_eye_rel.y * h))

        aligned = _rotate_by_eyes(image_bgr, left_eye, right_eye)

        face = aligned[y1:y2, x1:x2]

        if face.size == 0:
            return None

        face = cv2.resize(face, (target_size, target_size))
        return cv2.cvtColor(face, cv2.COLOR_BGR2RGB)


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
    face_crop : np.ndarray | None

class FacePreprocessor:
    def __init__(self, target_size: int = 224):
        self.target_size = target_size

    def process(self, raw_bgr: np.ndarray) -> PreprocessResult:
        face_rgb = detect_and_align(raw_bgr, self.target_size)

        if face_rgb is None:
            return PreprocessResult(success=False, face_crop=None)

        face_bgr = cv2.cvtColor(face_rgb, cv2.COLOR_RGB2BGR)
        return PreprocessResult(success=True, face_crop=face_bgr)

class AFADPreprocessor:
    GENDER_CODES = {"111", "112"}

    def __init__(self, root_dir: str, target_size: int = 224):
        self.root = Path(root_dir)
        self.target_size = target_size
        self.samples = self._scan()
        print(f"[AFADPreprocessor] {len(self.samples):,}개 샘플을 찾았습니다.")

    def run(self, output_dir: str, num_workers: int = 4):
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

    def _scan(self) -> list[tuple[Path, int]]:
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

    def _process_one(self, sample: tuple[Path, int], out_root: Path) -> bool:
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
# [Cell 1] CNN 모델 로드
# ============================================================
import torch

if torch.cuda.is_available():
    device = torch.device("cuda")
elif hasattr(torch, "backends") and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
    device = torch.device("mps")
else:
    device = torch.device("cpu")

# =====================
# .pt TorchScript 모델 파일 경로
# =====================
model_path = "./Best_Age_Estimate_model_traced.pt"

print(f"TorchScript 모델을 [{device.type.upper()}] 장치로 불러오는 중...")
model = torch.jit.load(model_path, map_location=device)
model.eval()
print("모델 로드 완료. 추론을 시작할 수 있습니다.")

# ============================================================
# [Cell 2] 입력 이미지 전처리
# image_path 값을 분석할 이미지 파일 경로로 바꿔서 사용합니다.
# ============================================================
import cv2

if 'preprocessor' not in globals():
    preprocessor = FacePreprocessor(target_size=224)

# ===================================
# INPUT INPUT INPUT INPUT INPUT INPUT
image_path = "./image.jpg" or "./image.png"
# ===================================
raw_image_bgr = cv2.imread(image_path)

if raw_image_bgr is None:
    print(f"이미지를 불러오지 못했습니다: {image_path}")
else:
    result = preprocessor.process(raw_image_bgr)
    if result.success:
        print("얼굴 전처리 완료. result.face_crop에 전처리 결과가 저장되었습니다.")

# ============================================================
# [Cell 3] CNN 모델 추론 및 결과 출력
# ============================================================
import torch
import cv2
import numpy as np
import matplotlib.pyplot as plt
from torchvision import transforms

# 1. 전처리된 얼굴 이미지를 RGB로 변환
face_rgb = cv2.cvtColor(result.face_crop, cv2.COLOR_BGR2RGB)

transform = transforms.Compose([
    transforms.ToPILImage(),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

input_tensor = transform(face_rgb).unsqueeze(0).to(device)


with torch.no_grad():
    # =========================================
    # OUTPUT OUTPUT OUTPUT OUTPUT OUTPUT OUTPUT
    predicted_age, predicted_gender, age_probs, gender_confidence = model(input_tensor)
    # predicted_age, predicted_gender, age_probs, gender_confidence를 반환받습니다.
    # =========================================


# ============================================================
# 최종 예측 결과 출력
# ============================================================

gender_label = "Male" if int(predicted_gender.item()) == 0 else "Female"

print("="*45)
print("[FaRL Model Final Analysis Results]")
print("="*45)
print(f"Predicted Age: {predicted_age.item():.2f} years old")
print(f"Predicted Gender: {gender_label} (Class Index: {int(predicted_gender.item())})")
print(f"Gender Confidence: {gender_confidence.item() * 100:.2f}%")
print("="*45)


# AFAD 나이 클래스 범위 (15세 ~ 40세)
ages_x = np.arange(15, 41)

# age_probs shape가 (1, 26)이라고 가정하고 확률을 퍼센트로 변환합니다.
probs_percent = age_probs[0].cpu().numpy() * 100

plt.figure(figsize=(10, 5))

# 나이별 확률 분포 막대 그래프
plt.bar(ages_x, probs_percent, color='royalblue', alpha=0.6, edgecolor='black', zorder=2, label='Age Probability Distribution')

# 확률 분포 추세선
plt.plot(ages_x, probs_percent, color='darkblue', marker='o', markersize=4, linestyle='-', linewidth=1.5, zorder=3)

# 모델이 예측한 나이 위치를 세로선으로 표시
plt.axvline(x=predicted_age.item(), color='crimson', linestyle='--', linewidth=2, zorder=4,
            label=f'Predicted Age: {predicted_age.item():.2f} yrs')

# 그래프 제목과 축 라벨 설정
plt.title("FaRL Model: Age Prediction Probability Distribution", fontsize=13, fontweight='bold', pad=15)
plt.xlabel("Age (Years)", fontsize=11, labelpad=10)
plt.ylabel("Probability (%)", fontsize=11, labelpad=10)

# X축을 15세부터 40세까지 1세 단위로 표시
plt.xticks(ages_x, fontsize=9)
plt.xlim(14, 41)
plt.ylim(0, max(probs_percent) * 1.2)  # 최대 확률보다 약간 크게 y축 범위 설정

plt.grid(axis='y', linestyle='--', alpha=0.5, zorder=1)
plt.legend(fontsize=10, loc='upper right')
plt.tight_layout()

# 그래프 창 표시
plt.show()
