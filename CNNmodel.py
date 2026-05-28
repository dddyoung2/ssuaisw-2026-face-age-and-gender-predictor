# -*- coding: utf-8 -*-
# -*- coding: cp949 -*-
"""
============================================================
[Cell 0] ?�뜝�룞�삕?�뜝�룞�삕?�뜝�룞�삕 ?�뜝�룞�삕沃섎챿�삕?? ?�뜝�룞�삕筌ｌ꼶�봺 �굜遺얜굡
============================================================\
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
        print(f"[AFADPreprocessor] {len(self.samples):,}�뜝占�? ?�뜝�룞�삕沃섎챿�삕?? 獄쏆뮄猿�")

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
        print(f"[?�뜝�룞�삕�뜝占�?] ?�뜝�룞�삕�뜝占�? {ok:,}  ?�뜝�룞�삕?�뜝�룞�삕(?�뜝�룞�삕�뤃�뙋�삕?�뜝�럡而㎩뜝占�? ?�뜝�룞�삕?�뜝�룞�삕) {fail:,}")

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
# [Cell 1] CNN 筌뤴뫀�쑞 �겫�뜄�쑎?�뜝�룞�삕�뜝占�? (筌ㅼ뮇�겧 1?�뜝�룞�삕�뜝占�? ?�뜝�룞�삕?�뜝�룞�삕)
# ============================================================
import torch

if torch.cuda.is_available():
    device = torch.device("cuda")
elif hasattr(torch, "backends") and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
    device = torch.device("mps")
else:
    device = torch.device("cpu")

# =====================
# .pt ?�뜝�룞�삕?�뜝�룞�삕?�뜝�룞�삕 ????�뜝�룞�삕?�뜝�룞�삕 野껋럥以� ?�뜝�룞�삕?�뜝�룞�삕
# =====================
model_path = "./Best_Age_Estimate_model_traced.pt"

print(f"? TorchScript 筌ㅼ뮇�읅?�뜝�룞�삕 筌뤴뫀�쑞?�뜝�룞�삕 [{device.type.upper()}] 筌롫뗀�걟�뵳�딅퓠 嚥≪뮆諭� �뜝占�?...")
model = torch.jit.load(model_path, map_location=device)
model.eval()
print("? 筌뤴뫀�쑞 嚥≪뮆諭� ?�뜝�룞�삕�뜝占�?! ?�뜝�룞�삕?�뜝�룞�삕 ?�뜝�룞�삕 ?????? ?�뜝�룞�삕?�뜝�룞�삕 ?�뜝�룞�삕?�뜝�룞�삕?�뜝�룞�삕�뜝占�? 筌띾뜆苑�?�뜝�룞�삕.")

# ============================================================
# [Cell 2] ?�뜝�룞�삕沃섎챿�삕?? ?�뜝�룞�삕筌ｌ꼶�봺 ?�뜝�룞�삕�뜝占�? (?�뜝�룞�삕嚥≪뮇�뒲 ?�뜝�룞�삕�뜝占�? ?�뜝�룞�삕?�뜝�룞�삕 ?�뜝�룞�삕筌띾뜄�뼄 ?�뜝�룞�삕?�뜝�룞�삕)
# image_path ?�뜝�룞�삕 ?�뜝�룞�삕筌ｌ꼶�봺?�뜝�룞�삕 ?�뜝�룞�삕沃섎챿�삕?? 野껋럥以덂뜝占�? ?�뜝�룞�삕?�뜝�룞�삕�뜝占�? [input]
# ============================================================
import cv2

if 'preprocessor' not in globals():
    preprocessor = FacePreprocessor(target_size=224)

# ===================================
# INPUT INPUT INPUT INPUT INPUT INPUT
image_path = "./image.jpg" or "./image.png"
# ?�뜝�룞�삕?�뜝�룞�삕揶쏅�れ몵�뜝占�? ?�뜝�룞�삕?�뜝�룞�삕 ?�뜝�룞�삕沃섎챿�삕?? 野껋럥以� ?�뜝�룞�삕?�뜝�룞�삕
# ===================================
raw_image_bgr = cv2.imread(image_path)

if raw_image_bgr is None:
    print(f"? ?�뜝�룞�삕沃섎챿�삕??�뜝占�? 嚥≪뮆諭�?�뜝�룞�삕 ?�뜝�룞�삕 ?�뜝�룞�삕?�뜝�룞�삕?�뜝�룞�삕?�뜝�룞�삕: {image_path}")
else:
    result = preprocessor.process(raw_image_bgr)
    if result.success:
        print("? ?�뜝�룞�삕�뜝占�? ?�뜝�룞�삕筌ｌ꼶�봺 ?�뜝�룞�삕�뜝占�?! 'result' �뜝占�??�뜝�룞�삕?�뜝�룞�삕 ????�뜝�룞�삕?�뜝�룞�삕?�뜝�룞�삕?�뜝�룞�삕?�뜝�룞�삕?�뜝�룞�삕.")

# 筌ㅼ뮇伊�?�뜝�룞�삕?�뜝�룞�삕�뜝占�? result �뜝占�??�뜝�룞�삕?�뜝�룞�삕 ?�뜝�룞�삕筌ｌ꼶�봺?�뜝�룞�삕 ?�뜝�룞�삕沃섎챿�삕??�뜝占�? ????�뜝�룞�삕?�뜝�룞�삕?�뜝�룞�삕 ?�뜝�룞�삕?�뜝�룞�삕 ???�뜝占�? ?�뜝�룞�삕?�뜝�룞�삕�뜝占�?

# ============================================================
# [Cell 3] CNN 筌뤴뫀�쑞?�뜝�룞�삕 ?�뜝�룞�삕筌ｌ꼶�봺?�뜝�룞�삕 ?�뜝�룞�삕沃섎챿�삕??�뜝占�? ?�뜝�룞�삕?�뜝�룞�삕 ?�뜝�룞�삕筌β넄而� �빊�뮆�젾 + ?�뜝�룞�삕?�뜝�룞�삕?�뜝�룞�삕域밸챶�삪 ?�뜝�룞�삕揶쏄낱�넅
# ============================================================
import torch
import cv2
import numpy as np
import matplotlib.pyplot as plt
from torchvision import transforms

# 1. ?�뜝�룞�삕沃섎챿�삕?? ?�뜝�룞�삕筌ｌ꼶�봺 �뜝占�? ?�뜝�룞�삕?�뜝�룞�삕 �뜝占�??�뜝�룞�삕
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
    # ?�뜝�룞�삕筌γ�볤돌?�뜝�룞�삕, ?�뜝�룞�삕筌β돦苑��뜝占�?, ?�뜝�룞�삕筌γ�볤돌?�뜝�룞�삕?�뜝�룞�삕�몴醫딇뀋?�뜝�룞�삕, ?�뜝�룞�삕癰귢쑵�넇?�뜝�룞�삕?�뜝�룞�삕?�뜝�룞�삕
    # =========================================




# ============================================================
# ? ?�뜝�룞�삕揶쏄낱�넅 ?�뜝�룞�삕?�뜝�룞�삕 (?�뜝�룞�삕?�뜝�룞�삕 ?�뜝�룞�삕?�뜝�룞�삕?�뜝�룞�삕?�뜝�룞�삕 ?�뜝�룞�삕?�뜝�룞�삕 ?�뜝�룞�삕�뜝占�? �뜝占�??�뜝�룞�삕�뜝占�? ?�뜝�룞�삕?�뜝�룞�삕?�뜝�룞�삕�뜝占�? ?�뜝�룞�삕)
# ============================================================

gender_label = "Male" if int(predicted_gender.item()) == 0 else "Female"

print("="*45)
print("? [FaRL Model Final Analysis Results]")
print("="*45)
print(f"?�뜝�룞�삕 Predicted Age: {predicted_age.item():.2f} years old")
print(f"?�뜝�룞�삕 Predicted Gender: {gender_label} (Class Index: {int(predicted_gender.item())})")
print(f"?�뜝�룞�삕 Gender Confidence: {gender_confidence.item() * 100:.2f}%")
print("="*45)


# AFAD ?�뜝�룞�삕?�뜝�룞�삕?�뜝�룞�삕?�뜝�룞�삕?�뜝�룞�삕 ?�뜝�룞�삕?�뜝�룞�삕 疫꿸낀�삕??�뜝占�? ?�뜝�룞�삕?�뜝�룞�삕 (15?�뜝�룞�삕 ~ 40?�뜝�룞�삕)
ages_x = np.arange(15, 41)

# ?�뜝�룞�삕?�뜝�룞�삕 ?�뜝�룞�삕?�뜝�룞�삕?�뜝�룞�삕 ?�뜝�룞�삕�뜝占�? �겫袁る７�뜝占�? ?�뜝�룞�삕?�뜝�룞�삕?�뜝�룞�삕 獄쏄퀣肉닷뜝占�? �뜝占�??�뜝�룞�삕?�뜝�룞�삕�뜝占�? 100?�뜝�룞�삕 ��④퉲鍮� % ?�뜝�룞�삕?�뜝�룞�삕�뜝占�? �뜝占�?�뜝占�?
# age_probs?�뜝�룞�삕 shape?�뜝�룞�삕 (1, 26)?�뜝�룞�삕�뜝占�?�뜝占�? [0]?�뜝�룞�삕 ?�뜝�룞�삕?�뜝�룞�삕 26揶쏆뮇彛ⓨ뜝占�? 1筌△뫁�뜚 獄쏄퀣肉�?�뜝�룞�삕 �뜝占�??�뜝�룞�삕?�뜝�룞�삕?�뜝�룞�삕?�뜝�룞�삕.
probs_percent = age_probs[0].cpu().numpy() * 100

plt.figure(figsize=(10, 5))

# ?�뜝�룞�삕 ?�뜝�룞�삕�뜝占�? �겫袁る７ 筌띾맮�삕??域밸챶�삋?�뜝�룞�삕 (?�뜝�룞�삕?�뜝�룞�삕?�뜝�룞�삕域밸챶�삪 ?�뜝�룞�삕?�뜝�룞�삕) ?�뜝�룞�삕?�뜝�룞�삕
plt.bar(ages_x, probs_percent, color='royalblue', alpha=0.6, edgecolor='black', zorder=2, label='Age Probability Distribution')

# ?�뜝�룞�삕 �겫袁る７ �빊遺욧쉭�뜝占�? ?�뜝�룞�삕 ?�뜝�룞�삕 癰귣떯由� ?�뜝�룞�삕?�뜝�룞�삕 �뜝占�??�뜝�룞�삕?�뜝�룞�삕?�뜝�룞�삕 �댆�뼲�삕???�뜝�룞�삕域밸챶�삋?�뜝�룞�삕 �빊酉귥삕??
plt.plot(ages_x, probs_percent, color='darkblue', marker='o', markersize=4, linestyle='-', linewidth=1.5, zorder=3)

# ?�뜝�룞�삕 筌뤴뫀�쑞?�뜝�룞�삕 ?�뜝�룞�삕筌β돧釉� 筌ㅼ뮇伊� 疫꿸퀡�솊�뜝占�? ?�뜝�룞�삕?�뜝�룞�삕 ?�뜝�룞�삕燁살꼷肉� �뜮�몿而� ?�뜝�룞�삕?�뜝�룞�삕 ?�뜝�룞�삕�뜝占�? ?�뜝�룞�삕?�뜝�룞�삕
plt.axvline(x=predicted_age.item(), color='crimson', linestyle='--', linewidth=2, zorder=4,
            label=f'Predicted Age: {predicted_age.item():.2f} yrs')

# 域밸챶�삋?�뜝�룞�삕 ?�뜝�룞�삕????�뜝�룞�삕 ?�뜝�룞�삕�뜝占�? ?�뜝�룞�삕?�뜝�룞�삕?�뜝�룞�삕 ?�뜝�룞�삕?�뜝�룞�삕 (?�뜝�룞�삕?�뜝�룞�삕 ?�뜝�룞�삕?�뜝�룞�삕?�뜝�룞�삕 獄쏆꼷�겫)
plt.title("FaRL Model: Age Prediction Probability Distribution", fontsize=13, fontweight='bold', pad=15)
plt.xlabel("Age (Years)", fontsize=11, labelpad=10)
plt.ylabel("Probability (%)", fontsize=11, labelpad=10)

# X�뜝占�? ?�뜝�룞�삕疫뀀뜆�뱽 15?�뜝�룞�삕�뜝占�??�뜝�룞�삕 40?�뜝�룞�삕繹먮슪�삕?? 1?�뜝�룞�삕 ?�뜝�룞�삕?�뜝�룞�삕�뜝占�? �룯�꼷�굦?�뜝�룞�삕�뜝占�? ?�뜝�룞�삕?�뜝�룞�삕�뜝占�? ?�뜝�룞�삕�뜝占�?
plt.xticks(ages_x, fontsize=9)
plt.xlim(14, 41)
plt.ylim(0, max(probs_percent) * 1.2)  # 域밸챶�삋?�뜝�룞�삕 ?�뜝�룞�삕?�뜝�룞�삕 ?�뜝�룞�삕�뜝占�? ?�뜝�룞�삕�뜝占�?

plt.grid(axis='y', linestyle='--', alpha=0.5, zorder=1)
plt.legend(fontsize=10, loc='upper right')
plt.tight_layout()

# 雅뚯눛逾�?�뜝�룞�삕 ?�뜝�룞�삕?�뜝�룞�삕�뜝占�? / �굜遺얠삫 ?�뜝�룞�삕筌롫똻肉� 域밸챶�삋?�뜝�룞�삕 ?�뜝�룞�삕?�뜝�룞�삕�뜝占�?
plt.show()