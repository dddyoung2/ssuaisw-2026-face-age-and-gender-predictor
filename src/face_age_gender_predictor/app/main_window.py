"""
main_window.py
==============
PyQt5 GUI 화면 계층(View).

디자인은 첨부된 구버전 GUI(밝은 블루/화이트 light theme)를 기준으로 정렬했고,
로직(나이 확신도 표준편차 공식, invalid age_probs 방어, 성별 표시 contract)은
현행을 유지한다. 즉 구버전의 예측 나이 ±2세 확률 질량 방식은 사용하지 않는다.
"""

import math
import sys
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Tuple

import cv2
import numpy as np
from PyQt5.QtCore import Qt, QRectF, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QImage, QPixmap, QPainter, QColor, QPen, QFont
from PyQt5.QtWidgets import (
    QApplication, QBoxLayout, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QMainWindow, QMessageBox, QProgressBar, QPushButton, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)

FaceBox = Tuple[int, int, int, int]


class AppState(Enum):
    IDLE = auto()
    READY = auto()
    COUNTDOWN = auto()
    COLLECTING = auto()
    ANALYZING = auto()
    DONE = auto()
    ERROR = auto()


CONTROLLER_STATE_MAP = {
    "IDLE": AppState.IDLE,
    "COUNTDOWN": AppState.COUNTDOWN,
    "CAPTURING": AppState.COLLECTING,
    "ANALYZING": AppState.ANALYZING,
    "DONE": AppState.DONE,
    "ERROR": AppState.ERROR,
}


@dataclass(frozen=True)
class StateMeta:
    label: str
    banner: str
    hint: str
    color: str


STATE_META = {
    AppState.IDLE: StateMeta("대기 중", "IDLE", "카메라를 시작하면 실시간 얼굴 인식 화면이 열립니다.", "#64748b"),
    AppState.READY: StateMeta("준비 완료", "READY", "얼굴을 가이드 박스 안에 맞춘 뒤 측정을 시작해주세요.", "#2563eb"),
    AppState.COUNTDOWN: StateMeta("카운트다운", "COUNTDOWN", "곧 촬영이 시작됩니다. 잠시 가만히 있어주세요.", "#f59e0b"),
    AppState.COLLECTING: StateMeta("프레임 캡처 중", "CAPTURING", "40프레임을 캡처하는 중입니다. 움직이지 말아주세요.", "#2563eb"),
    AppState.ANALYZING: StateMeta("분석 중", "ANALYZING", "수집한 프레임으로 나이와 성별을 추정하고 있습니다.", "#7c3aed"),
    AppState.DONE: StateMeta("측정 완료", "DONE", "측정된 얼굴과 결과가 아래에 표시되었습니다.", "#10b981"),
    AppState.ERROR: StateMeta("오류", "ERROR", "카메라 또는 얼굴 인식 상태를 확인해주세요.", "#ef4444"),
}


class AspectRatioLabel(QLabel):
    def __init__(self, placeholder_text: str = "", parent=None) -> None:
        super().__init__(parent)
        self._placeholder_text = placeholder_text
        self._source_pixmap: Optional[QPixmap] = None
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setText(placeholder_text)

    def set_frame_pixmap(self, pixmap: QPixmap) -> None:
        self._source_pixmap = pixmap
        self._rescale()

    def clear_frame(self) -> None:
        self._source_pixmap = None
        self.clear()
        self.setText(self._placeholder_text)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._rescale()

    def _rescale(self) -> None:
        if self._source_pixmap is None or self._source_pixmap.isNull():
            return

        scaled = self._source_pixmap.scaled(
            self.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.setPixmap(scaled)


class MetricCard(QFrame):
    def __init__(self, title: str, accent: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("accentMetricCard" if accent else "metricCard")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(74)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("metricTitle")
        self.title_label.setMinimumHeight(16)

        self.value_label = QLabel("-")
        self.value_label.setObjectName("metricValue")
        self.value_label.setMinimumHeight(28)
        self.value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

    def set_value(self, text: str, color: str, size: int) -> None:
        min_height = 30
        if size >= 24:
            min_height = 34
        if size >= 28:
            min_height = 38

        self.value_label.setText(text)
        self.value_label.setStyleSheet(
            f"""
            color: {color};
            font-size: {size}px;
            font-weight: 900;
            min-height: {min_height}px;
            padding: 0px;
            """
        )


class AgeHistogramWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.values = [0] * 26
        self.setMinimumHeight(178)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_values(self, values: list[int]) -> None:
        if len(values) != 26:
            values = [0] * 26
        self.values = values
        self.update()

    def clear_values(self) -> None:
        self.values = [0] * 26
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect()
        painter.fillRect(rect, QColor("#ffffff"))

        painter.setPen(QPen(QColor("#d7e3f2"), 1))
        painter.drawRoundedRect(rect.adjusted(0, 0, -1, -1), 14, 14)

        title_font = QFont("Pretendard", 10)
        title_font.setWeight(QFont.Bold)
        painter.setFont(title_font)
        painter.setPen(QColor("#172033"))
        painter.drawText(14, 26, "나이 히스토그램")

        chart_left = 16
        chart_top = 48
        chart_right = rect.width() - 16
        chart_bottom = rect.height() - 30
        chart_width = max(1, chart_right - chart_left)
        chart_height = max(1, chart_bottom - chart_top)

        painter.setPen(QPen(QColor("#d7e3f2"), 1))
        painter.drawLine(chart_left, chart_bottom, chart_right, chart_bottom)

        max_value = max(self.values) if self.values else 0
        if max_value <= 0:
            painter.setPen(QColor("#7a8799"))
            painter.drawText(rect, Qt.AlignCenter, "측정 후 15~40세 나이 분포가 표시됩니다.")
            return

        bar_gap = 2
        bar_width = max(3, (chart_width - bar_gap * 25) / 26)

        for index, value in enumerate(self.values):
            age = 15 + index
            ratio = value / max_value if max_value else 0
            bar_height = chart_height * ratio

            x = chart_left + index * (bar_width + bar_gap)
            y = chart_bottom - bar_height

            color = QColor("#2563eb") if value == max_value else QColor("#93c5fd")
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(QRectF(x, y, bar_width, bar_height), 3, 3)

            if age in {15, 20, 25, 30, 35, 40}:
                label_font = QFont("Pretendard", 7)
                painter.setFont(label_font)
                painter.setPen(QColor("#8a98aa"))
                painter.drawText(
                    QRectF(x - 6, chart_bottom + 5, bar_width + 12, 16),
                    Qt.AlignCenter,
                    str(age),
                )


# ====================================================================
# 나이 확신도(age confidence) 계산 — 26-bin(15~40세) 분포의 weighted stddev 기반
# (구버전 첨부 코드의 ±2세 확률 질량 방식은 사용하지 않는다.)
# ====================================================================

# 나이 분포는 15..40세 26개 bin이다.
AGE_CONF_BIN_COUNT = 26
AGE_CONF_AGE_MIN = 15

# test data 검증으로 얻은 실효 표준편차 범위와 confidence 매핑 상수.
# 표준편차가 작을수록(분포가 좁을수록) 확신도가 높다.
AGE_CONF_STDDEV_BEST = 1.57    # 이 이하면 99%
AGE_CONF_STDDEV_WORST = 8.23   # 이 이상이면 1%
AGE_CONF_CONFIDENCE_BEST = 99.0
AGE_CONF_CONFIDENCE_WORST = 1.0


def age_distribution_stddev(age_probs) -> Optional[float]:
    """26-bin 나이 분포(15..40)의 weighted standard deviation을 반환한다.

    - normalized probability든 unnormalized positive weight든, 합이 0보다 크면
      normalize 후 사용한다.
    - 유효하지 않은 분포(None / 길이 != 26 / 숫자가 아닌 값 / NaN·Inf / 음수 /
      합 <= 0)면 None을 반환한다. (절대 높은 confidence로 fallback하지 않기 위함)
    """
    if age_probs is None or isinstance(age_probs, (str, bytes)):
        return None

    try:
        values = list(age_probs)
    except TypeError:
        return None

    if len(values) != AGE_CONF_BIN_COUNT:
        return None

    weights = []
    for v in values:
        # bool은 int의 하위 타입이지만 확률 값으로 보지 않는다.
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return None
        if not math.isfinite(v):
            return None
        if v < 0:
            return None
        weights.append(float(v))

    total = sum(weights)
    if total <= 0:
        return None

    norm = [w / total for w in weights]
    ages = [AGE_CONF_AGE_MIN + i for i in range(AGE_CONF_BIN_COUNT)]
    mean = sum(norm[i] * ages[i] for i in range(AGE_CONF_BIN_COUNT))
    variance = sum(norm[i] * (ages[i] - mean) ** 2 for i in range(AGE_CONF_BIN_COUNT))
    if variance < 0:  # 부동소수점 안전장치
        variance = 0.0
    return math.sqrt(variance)


def age_confidence_from_stddev(stddev: float) -> float:
    """표준편차 -> confidence(%) inverse linear mapping. [1.0, 99.0]로 clamp한다.

        ratio = (stddev - BEST) / (WORST - BEST)
        confidence = CONFIDENCE_BEST - ratio * (CONFIDENCE_BEST - CONFIDENCE_WORST)
    """
    span = AGE_CONF_STDDEV_WORST - AGE_CONF_STDDEV_BEST
    ratio = (stddev - AGE_CONF_STDDEV_BEST) / span
    confidence = AGE_CONF_CONFIDENCE_BEST - ratio * (
        AGE_CONF_CONFIDENCE_BEST - AGE_CONF_CONFIDENCE_WORST
    )
    return min(AGE_CONF_CONFIDENCE_BEST, max(AGE_CONF_CONFIDENCE_WORST, confidence))


def age_confidence_percent(age_probs) -> Optional[float]:
    """26-bin 나이 분포 -> age confidence(%). 유효하지 않으면 None."""
    stddev = age_distribution_stddev(age_probs)
    if stddev is None:
        return None
    return age_confidence_from_stddev(stddev)


class AgeEstimatorWindow(QMainWindow):
    RESPONSIVE_BREAKPOINT = 1100
    COLLECTION_TARGET_FRAMES = 40
    MODEL_INPUT_SIZE = (224, 224)
    AGE_MIN = 15
    AGE_MAX = 40

    start_camera_requested = pyqtSignal()
    measurement_requested = pyqtSignal()
    stop_camera_requested = pyqtSignal()
    close_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Face Age Estimation")
        self.resize(1280, 800)
        self.setMinimumSize(900, 640)

        self.state = AppState.IDLE
        self.camera_running = False
        self.face_ready = False
        self.countdown_value = 0
        self.capture_progress = 0

        self.latest_frame: Optional[np.ndarray] = None
        self.latest_face_box: Optional[FaceBox] = None
        self.captured_frame: Optional[np.ndarray] = None
        self.captured_face_box: Optional[FaceBox] = None
        self.age_histogram_values = [0] * 26

        self.build_ui()
        self.apply_styles()
        self.enter_state(AppState.IDLE)
        self.set_face_status("대기", "#172033")
        self.set_gender("-")
        self.set_age_result("-")
        self.set_gender_confidence("-")
        self.set_age_confidence("-")
        self.reset_progress_bar()
        self.clear_preview_panel()
        self.sync_button_states()
        self.update_responsive_layout(self.width())

    def build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)

        self.main_layout = QBoxLayout(QBoxLayout.LeftToRight, root)
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.main_layout.setSpacing(14)

        self.video_card = self.build_video_panel()
        self.side_scroll = self.build_side_panel()

        self.main_layout.addWidget(self.video_card, 7)
        self.main_layout.addWidget(self.side_scroll, 4)

    def build_video_panel(self) -> QFrame:
        video_card = QFrame()
        video_card.setObjectName("videoCard")
        video_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(video_card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)

        header = QHBoxLayout()
        header.setSpacing(10)

        title_box = QVBoxLayout()
        title_box.setSpacing(3)

        title = QLabel("Live Camera")
        title.setObjectName("videoTitle")

        subtitle = QLabel("사각형 안에 얼굴을 넣고 측정을 클릭하세요!")
        subtitle.setObjectName("videoSubtitle")
        subtitle.setWordWrap(True)

        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        self.live_state_tag = QLabel("대기 중")
        self.live_state_tag.setAlignment(Qt.AlignCenter)
        self.live_state_tag.setMinimumWidth(96)
        self.live_state_tag.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        header.addLayout(title_box, stretch=1)
        header.addWidget(self.live_state_tag)

        self.video_label = AspectRatioLabel("카메라 화면")
        self.video_label.setObjectName("videoSurface")
        self.video_label.setMinimumSize(460, 300)

        layout.addLayout(header)
        layout.addWidget(self.video_label, stretch=1)

        return video_card

    def build_side_panel(self) -> QScrollArea:
        side_scroll = QScrollArea()
        side_scroll.setObjectName("sideScroll")
        side_scroll.setWidgetResizable(True)
        side_scroll.setFrameShape(QFrame.NoFrame)
        side_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        side_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        side_scroll.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        side_panel = QFrame()
        side_panel.setObjectName("sidePanel")
        side_scroll.setWidget(side_panel)

        layout = QVBoxLayout(side_panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        eyebrow = QLabel("디자인 수정 예정")
        eyebrow.setObjectName("eyebrow")

        title = QLabel("실시간 얼굴 나이 추정")
        title.setObjectName("panelTitle")
        title.setWordWrap(True)

        self.helper_label = QLabel("")
        self.helper_label.setObjectName("helperBox")
        self.helper_label.setWordWrap(True)

        self.progress_title = QLabel("프레임 캡처 진행률")
        self.progress_title.setObjectName("progressTitle")

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("captureProgressBar")
        self.progress_bar.setRange(0, self.COLLECTION_TARGET_FRAMES)
        self.progress_bar.setTextVisible(True)

        metrics_grid = QGridLayout()
        metrics_grid.setHorizontalSpacing(10)
        metrics_grid.setVerticalSpacing(10)

        self.status_card = MetricCard("현재 상태")
        self.face_card = MetricCard("얼굴 감지")

        metrics_grid.addWidget(self.status_card, 0, 0)
        metrics_grid.addWidget(self.face_card, 0, 1)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)

        self.start_camera_button = self.create_button("카메라 시작", "startButton", self._emit_start_camera)
        self.measure_button = self.create_button("측정 시작", "measureButton", self._emit_measurement)
        self.stop_button = self.create_button("카메라 종료", "stopButton", self._emit_stop_camera)

        button_row.addWidget(self.start_camera_button)
        button_row.addWidget(self.measure_button)
        button_row.addWidget(self.stop_button)

        self.preview_card = QFrame()
        self.preview_card.setObjectName("previewCard")

        preview_layout = QVBoxLayout(self.preview_card)
        preview_layout.setContentsMargins(14, 14, 14, 14)
        preview_layout.setSpacing(12)

        preview_title = QLabel("측정된 얼굴")
        preview_title.setObjectName("previewTitle")

        preview_body = QHBoxLayout()
        preview_body.setSpacing(14)

        self.preview_face_label = QLabel("측정 전")
        self.preview_face_label.setObjectName("previewFace")
        self.preview_face_label.setAlignment(Qt.AlignCenter)
        self.preview_face_label.setFixedSize(130, 130)

        preview_info_grid = QGridLayout()
        preview_info_grid.setHorizontalSpacing(34)
        preview_info_grid.setVerticalSpacing(10)
        preview_info_grid.setColumnStretch(0, 1)
        preview_info_grid.setColumnStretch(1, 1)

        self.preview_gender_title = QLabel("성별")
        self.preview_gender_title.setObjectName("previewMetaTitle")
        self.preview_gender_value = QLabel("-")
        self.preview_gender_value.setObjectName("previewMetaValue")

        self.preview_age_title = QLabel("나이")
        self.preview_age_title.setObjectName("previewMetaTitle")
        self.preview_age_value = QLabel("-")
        self.preview_age_value.setObjectName("previewMetaValue")

        self.preview_gender_confidence_title = QLabel("성별 확신도")
        self.preview_gender_confidence_title.setObjectName("previewMetaTitle")
        self.preview_gender_confidence_value = QLabel("-")
        self.preview_gender_confidence_value.setObjectName("previewMetaValueSmall")

        self.preview_age_confidence_title = QLabel("나이 확신도")
        self.preview_age_confidence_title.setObjectName("previewMetaTitle")
        self.preview_age_confidence_value = QLabel("-")
        self.preview_age_confidence_value.setObjectName("previewMetaValueSmall")

        preview_info_grid.addWidget(self.preview_gender_title, 0, 0)
        preview_info_grid.addWidget(self.preview_age_title, 0, 1)
        preview_info_grid.addWidget(self.preview_gender_value, 1, 0)
        preview_info_grid.addWidget(self.preview_age_value, 1, 1)
        preview_info_grid.addWidget(self.preview_gender_confidence_title, 2, 0)
        preview_info_grid.addWidget(self.preview_age_confidence_title, 2, 1)
        preview_info_grid.addWidget(self.preview_gender_confidence_value, 3, 0)
        preview_info_grid.addWidget(self.preview_age_confidence_value, 3, 1)
        preview_info_grid.setRowStretch(4, 1)

        preview_body.addWidget(self.preview_face_label, 0)
        preview_body.addLayout(preview_info_grid, 1)

        preview_layout.addWidget(preview_title)
        preview_layout.addLayout(preview_body)

        self.age_histogram = AgeHistogramWidget()

        layout.addWidget(eyebrow)
        layout.addWidget(title)
        layout.addWidget(self.helper_label)
        layout.addWidget(self.progress_title)
        layout.addWidget(self.progress_bar)
        layout.addLayout(metrics_grid)
        layout.addLayout(button_row)
        layout.addWidget(self.preview_card)
        layout.addWidget(self.age_histogram)
        layout.addStretch(1)

        return side_scroll

    def create_button(self, text: str, object_name: str, handler) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(object_name)
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(handler)
        return button

    def apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #eaf3ff;
            }

            QWidget#root {
                background-color: #eaf3ff;
            }

            QLabel, QPushButton {
                font-family: "Pretendard";
                color: #172033;
            }

            QFrame#videoCard,
            QFrame#sidePanel {
                background-color: #fbfdff;
                border: 1px solid #dbe7f5;
                border-radius: 18px;
            }

            QLabel#videoTitle {
                color: #172033;
                font-size: 18px;
                font-weight: 900;
            }

            QLabel#videoSubtitle {
                color: #6b7890;
                font-size: 12px;
                font-weight: 700;
            }

            QLabel#videoSurface {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #202a38,
                    stop: 0.55 #303b4b,
                    stop: 1 #1f2835
                );
                border: 1px solid #c9d7e8;
                border-radius: 14px;
                color: #9aa8ba;
                font-size: 22px;
                font-weight: 900;
            }

            QLabel#eyebrow {
                color: #2563eb;
                font-size: 11px;
                font-weight: 900;
            }

            QLabel#panelTitle {
                color: #172033;
                font-size: 24px;
                font-weight: 900;
            }

            QLabel#helperBox {
                background-color: #ffffff;
                border: 1px solid #d7e3f2;
                border-radius: 12px;
                color: #334155;
                font-size: 12px;
                font-weight: 700;
                padding: 12px;
                min-height: 42px;
            }

            QLabel#progressTitle {
                color: #7a8799;
                font-size: 11px;
                font-weight: 900;
                margin-top: 4px;
            }

            QProgressBar#captureProgressBar {
                background-color: #ffffff;
                border: 1px solid #d7e3f2;
                border-radius: 9px;
                min-height: 18px;
                color: #172033;
                text-align: center;
                font-size: 11px;
                font-weight: 900;
            }

            QProgressBar#captureProgressBar::chunk {
                background-color: #2f63f6;
                border-radius: 8px;
            }

            QFrame#metricCard {
                background-color: #ffffff;
                border: 1px solid #d7e3f2;
                border-radius: 12px;
            }

            QLabel#metricTitle {
                color: #7a8799;
                font-size: 11px;
                font-weight: 900;
                min-height: 16px;
            }

            QLabel#metricValue {
                color: #172033;
                font-size: 22px;
                font-weight: 900;
            }

            QPushButton {
                min-height: 42px;
                border-radius: 10px;
                border: 1px solid #d7e3f2;
                font-size: 13px;
                font-weight: 900;
                padding: 8px 10px;
                background-color: #ffffff;
                color: #64748b;
            }

            QPushButton#startButton {
                background-color: #ffffff;
                color: #64748b;
            }

            QPushButton#startButton:hover {
                background-color: #f3f7fc;
                border-color: #bfd0e5;
            }

            QPushButton#measureButton {
                background-color: #2f63f6;
                border-color: #2f63f6;
                color: #ffffff;
            }

            QPushButton#measureButton:hover {
                background-color: #2454d8;
            }

            QPushButton#stopButton {
                background-color: #ffffff;
                color: #64748b;
            }

            QPushButton#stopButton:hover {
                background-color: #f3f7fc;
                border-color: #bfd0e5;
            }

            QPushButton:disabled {
                background-color: #edf3fa;
                border-color: #e2eaf5;
                color: #9aa8ba;
            }

            QFrame#previewCard {
                background-color: #ffffff;
                border: 1px solid #d7e3f2;
                border-radius: 14px;
            }

            QLabel#previewTitle {
                color: #172033;
                font-size: 14px;
                font-weight: 900;
            }

            QLabel#previewFace {
                background-color: #fbfdff;
                border: 1px solid #d7e3f2;
                border-radius: 12px;
                color: #8a98aa;
                font-size: 13px;
                font-weight: 900;
            }

            QLabel#previewMetaTitle {
                color: #7a8799;
                font-size: 12px;
                font-weight: 900;
            }

            QLabel#previewMetaValue {
                color: #172033;
                font-size: 24px;
                font-weight: 900;
                min-height: 28px;
            }

            QLabel#previewMetaValueSmall {
                color: #2563eb;
                font-size: 18px;
                font-weight: 900;
                min-height: 22px;
            }

            QScrollArea#sideScroll {
                background: transparent;
                border: none;
            }
            """
        )

    def update_responsive_layout(self, width: int) -> None:
        if width < self.RESPONSIVE_BREAKPOINT:
            self.main_layout.setDirection(QBoxLayout.TopToBottom)
            self.main_layout.setStretch(0, 6)
            self.main_layout.setStretch(1, 4)
            self.video_label.setMinimumHeight(320)
        else:
            self.main_layout.setDirection(QBoxLayout.LeftToRight)
            self.main_layout.setStretch(0, 7)
            self.main_layout.setStretch(1, 4)
            self.video_label.setMinimumHeight(400)

    def _emit_start_camera(self) -> None:
        self.start_camera_requested.emit()

    def _emit_measurement(self) -> None:
        self.measurement_requested.emit()

    def _emit_stop_camera(self) -> None:
        self.stop_camera_requested.emit()

    @pyqtSlot(str)
    def on_status_message(self, message: str) -> None:
        self.helper_label.setText(message)

    @pyqtSlot(str)
    def on_state_changed(self, state_name: str) -> None:
        mapped = CONTROLLER_STATE_MAP.get(state_name, AppState.IDLE)

        if mapped == AppState.IDLE and self.camera_running and self.face_ready:
            mapped = AppState.READY

        if mapped == AppState.COUNTDOWN:
            self.reset_progress_bar()
            self.clear_preview_panel()
            self.captured_frame = None
            self.captured_face_box = None

        self.enter_state(mapped)
        self.sync_button_states()

    @pyqtSlot(bool)
    def on_camera_running_changed(self, running: bool) -> None:
        self.camera_running = running
        if not running:
            self.latest_frame = None
            self.latest_face_box = None
            self.countdown_value = 0
            self.video_label.clear_frame()
            self.set_face_status("대기", "#172033")
            self.reset_progress_bar()
        else:
            self.set_face_status("검색 중", "#2563eb")
        self.sync_button_states()

    @pyqtSlot(bool)
    def on_face_ready_changed(self, ready: bool) -> None:
        self.face_ready = ready
        if not self.camera_running:
            return

        if ready:
            self.set_face_status("감지됨", "#16a34a")
            if self.state in {AppState.IDLE, AppState.READY}:
                self.enter_state(AppState.READY)
        else:
            self.set_face_status("미감지", "#ef4444")
            if self.state in {AppState.IDLE, AppState.READY}:
                self.enter_state(AppState.IDLE)
        self.sync_button_states()

    @pyqtSlot(bool)
    def on_measure_enabled_changed(self, enabled: bool) -> None:
        self.measure_button.setEnabled(enabled)

    @pyqtSlot(int)
    def on_countdown_changed(self, value: int) -> None:
        self.countdown_value = value
        if value > 0:
            self.helper_label.setText(f"{value}초 뒤 촬영을 시작합니다. 정면을 유지해주세요.")

    @pyqtSlot(int, int)
    def on_capture_progress(self, current: int, total: int) -> None:
        self.capture_progress = current
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(current)
        self.progress_bar.setFormat(f"{current} / {total} frames")

    @pyqtSlot(int, int)
    def on_inference_progress(self, current: int, total: int) -> None:
        self.helper_label.setText(f"분석 중... ({current}/{total})")

    @pyqtSlot(object)
    def on_preview_frame(self, payload) -> None:
        try:
            frame, face_box = payload
        except (TypeError, ValueError):
            return
        if frame is None:
            return

        self.latest_frame = frame
        self.latest_face_box = face_box

        if face_box is not None and self.state in {AppState.COUNTDOWN, AppState.COLLECTING}:
            self.captured_frame = frame
            self.captured_face_box = face_box

        self.render_preview(frame, face_box)

    @pyqtSlot(dict)
    def on_result_ready(self, result: dict) -> None:
        if result.get("success"):
            self._show_success_result(result)
        else:
            self._show_failure_result(result)

    @pyqtSlot(str)
    def on_error_message(self, message: str) -> None:
        self.set_gender("미정")
        self.set_age_result("실패")
        self.set_gender_confidence("-")
        self.set_age_confidence("-")
        self.age_histogram.clear_values()
        self.helper_label.setText(message)
        QMessageBox.warning(self, "측정 오류", message)

    # ====================================================================
    # 결과 표시 — 나이 확신도/성별 로직은 현행(표준편차/contract)을 유지한다.
    # ====================================================================

    @staticmethod
    def _compute_age_confidence(age_probs) -> Optional[float]:
        """26-bin 나이 분포(15~40세)의 weighted standard deviation 기반 age confidence(%).

        표준편차가 작을수록(분포가 좁을수록) 확신도가 높다.
        - stddev 1.57 -> 99%, stddev 8.23 -> 1% (inverse linear, [1, 99] clamp)
        - 유효하지 않은 분포면 None을 반환한다(높은 confidence로 fallback하지 않음).

        구버전 첨부 코드의 예측 나이 ±2세 확률 질량 방식은 사용하지 않는다.
        """
        return age_confidence_percent(age_probs)

    @staticmethod
    def _gender_label(gender) -> str:
        """앱 내부 label contract: gender == 1 -> 여성, 그 외(0) -> 남성."""
        return "여성" if gender == 1 else "남성"

    def _show_success_result(self, result: dict) -> None:
        frame = self.captured_frame if self.captured_frame is not None else self.latest_frame
        face_box = self.captured_face_box if self.captured_face_box is not None else self.latest_face_box

        preview_face = self._make_preview_face(frame, face_box)
        if preview_face is not None:
            self.set_preview_face(preview_face)

        age = result.get("age")
        gender = result.get("gender")
        age_probs = result.get("age_probs") or [0.0] * 26
        gender_confidence = result.get("gender_confidence") or 0.0

        gender_text = self._gender_label(gender)
        self.set_gender(gender_text)
        self.set_age_result(f"{age:.0f}세" if age is not None else "-")
        self.set_gender_confidence(f"{gender_confidence * 100:.1f}%")

        # 나이 확신도: 26-bin(15~40세) 분포의 weighted stddev 기반 confidence.
        # invalid 분포(NaN/Inf/비숫자/길이 불일치/합<=0)는 confidence뿐 아니라
        # 히스토그램 변환(int(round(p*1000)))에서도 예외를 낼 수 있으므로, 동일한 유효성
        # 판단으로 묶어 처리한다: 유효하면 표시 + 히스토그램, 유효하지 않으면 "-" + 빈 히스토그램.
        age_confidence = self._compute_age_confidence(age_probs)
        if age_confidence is None:
            self.set_age_confidence("-")
            self.age_histogram_values = [0] * 26
            self.age_histogram.clear_values()
        else:
            self.set_age_confidence(f"{age_confidence:.1f}%")
            histogram_values = [int(round(p * 1000)) for p in age_probs]
            self.age_histogram_values = histogram_values
            self.age_histogram.set_values(histogram_values)

        self.helper_label.setText(
            f"측정 완료. 유효 프레임 {result.get('valid_count')}개로 분석했습니다."
        )

    def _show_failure_result(self, result: dict) -> None:
        valid_count = result.get("valid_count", 0)
        reason = result.get("reason", "측정 실패")

        self.set_gender("미정")
        self.set_age_result("실패")
        self.set_gender_confidence("-")
        self.set_age_confidence("-")
        self.age_histogram.clear_values()

        message = (
            f"측정에 실패했습니다. (유효 프레임 {valid_count}개, 사유: {reason})\n"
            f"다시 시도해주세요."
        )
        self.helper_label.setText(message)
        QMessageBox.information(self, "측정 실패", message)

    def _make_preview_face(self, frame, face_box) -> Optional[np.ndarray]:
        if frame is None or face_box is None:
            return None

        x, y, w, h = self._expanded_square_face_box(frame.shape, face_box)
        face_crop = frame[y:y + h, x:x + w]
        if face_crop.size == 0:
            return None

        rgb_face = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb_face, self.MODEL_INPUT_SIZE, interpolation=cv2.INTER_LINEAR)
        if resized.ndim != 3 or resized.shape[2] != 3:
            return None
        return resized

    @staticmethod
    def _expanded_square_face_box(frame_shape, face_box: FaceBox, margin: float = 0.45) -> FaceBox:
        height, width = frame_shape[:2]
        x, y, w, h = face_box
        side = int(max(w, h) * (1.0 + margin * 2.0))
        side = max(1, side)

        cx = x + w // 2
        cy = y + h // 2
        x1 = cx - side // 2
        y1 = cy - side // 2
        x2 = x1 + side
        y2 = y1 + side

        if x1 < 0:
            x2 -= x1
            x1 = 0
        if y1 < 0:
            y2 -= y1
            y1 = 0
        if x2 > width:
            shift = x2 - width
            x1 = max(0, x1 - shift)
            x2 = width
        if y2 > height:
            shift = y2 - height
            y1 = max(0, y1 - shift)
            y2 = height

        return int(x1), int(y1), int(x2 - x1), int(y2 - y1)

    def render_preview(self, frame: np.ndarray, face_box: Optional[FaceBox]) -> None:
        display_frame = frame.copy()
        self.draw_guide_box(display_frame)
        self.draw_status_banner(display_frame)

        if face_box is not None:
            x, y, w, h = face_box
            cv2.rectangle(display_frame, (x, y), (x + w, y + h), (37, 99, 235), 3)
            cv2.putText(
                display_frame,
                "FACE DETECTED",
                (x, max(32, y - 12)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.66,
                (37, 99, 235),
                2,
                cv2.LINE_AA,
            )

        if self.countdown_value > 0:
            cv2.putText(
                display_frame,
                str(self.countdown_value),
                (display_frame.shape[1] // 2 - 35, display_frame.shape[0] // 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                3.0,
                (255, 221, 87),
                6,
                cv2.LINE_AA,
            )

        self.render_frame(display_frame)

    def draw_guide_box(self, frame: np.ndarray) -> None:
        height, width = frame.shape[:2]
        box_w = int(width * 0.36)
        box_h = int(height * 0.54)
        x1 = (width - box_w) // 2
        y1 = (height - box_h) // 2
        x2 = x1 + box_w
        y2 = y1 + box_h

        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 255), 2)
        cv2.putText(
            frame,
            "Align face here",
            (x1, y1 - 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

    def draw_status_banner(self, frame: np.ndarray) -> None:
        meta = STATE_META[self.state]

        cv2.rectangle(frame, (18, 16), (250, 74), (32, 42, 56), -1)
        cv2.rectangle(frame, (18, 16), (250, 74), (148, 163, 184), 1)

        cv2.putText(
            frame,
            meta.banner,
            (30, 42),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.72,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            "Ready when you are",
            (30, 62),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            (203, 213, 225),
            1,
            cv2.LINE_AA,
        )

    def render_frame(self, frame: np.ndarray) -> None:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channel = rgb_frame.shape
        bytes_per_line = channel * width

        image = QImage(
            rgb_frame.data,
            width,
            height,
            bytes_per_line,
            QImage.Format_RGB888,
        ).copy()

        self.video_label.set_frame_pixmap(QPixmap.fromImage(image))

    def enter_state(self, state: AppState, custom_hint: Optional[str] = None) -> None:
        self.state = state
        meta = STATE_META[state]

        self.status_card.set_value(meta.label, "#172033", 19)
        if custom_hint is not None:
            self.helper_label.setText(custom_hint)
        else:
            self.helper_label.setText(meta.hint)
        self.set_state_tag(meta.label, meta.color)

    def set_state_tag(self, text: str, color: str) -> None:
        self.live_state_tag.setText(text)
        self.live_state_tag.setStyleSheet(
            """
            QLabel {
                background-color: #edf3fa;
                color: #64748b;
                border-radius: 11px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 900;
            }
            """
        )

    def set_face_status(self, text: str, color: str) -> None:
        self.face_card.set_value(text, color, 19)

    def set_gender(self, text: str) -> None:
        if text == "남성":
            color = "#2563eb"
        elif text == "여성":
            color = "#db2777"
        elif text == "미정":
            color = "#64748b"
        else:
            color = "#172033"

        self.preview_gender_value.setText(text)
        self.preview_gender_value.setStyleSheet(
            f"color: {color}; font-size: 24px; font-weight: 900;"
        )

    def set_gender_confidence(self, text: str) -> None:
        self.preview_gender_confidence_value.setText(text)
        self.preview_gender_confidence_value.setStyleSheet(
            "color: #2563eb; font-size: 18px; font-weight: 900;"
        )

    def set_age_result(self, text: str) -> None:
        if text == "실패":
            color = "#ef4444"
        elif text == "-":
            color = "#64748b"
        else:
            color = "#172033"

        self.preview_age_value.setText(text)
        self.preview_age_value.setStyleSheet(
            f"color: {color}; font-size: 24px; font-weight: 900;"
        )

    def set_age_confidence(self, text: str) -> None:
        self.preview_age_confidence_value.setText(text)
        self.preview_age_confidence_value.setStyleSheet(
            "color: #0f766e; font-size: 18px; font-weight: 900;"
        )

    def clear_preview_panel(self) -> None:
        self.preview_face_label.setPixmap(QPixmap())
        self.preview_face_label.setText("측정 전")
        self.set_gender("-")
        self.set_age_result("-")
        self.set_gender_confidence("-")
        self.set_age_confidence("-")
        self.age_histogram_values = [0] * 26
        self.age_histogram.clear_values()

    def set_preview_face(self, face_rgb_224: Optional[np.ndarray]) -> None:
        if face_rgb_224 is None:
            self.preview_face_label.setPixmap(QPixmap())
            self.preview_face_label.setText("측정 전")
            return

        height, width, channel = face_rgb_224.shape
        bytes_per_line = channel * width

        image = QImage(
            face_rgb_224.data,
            width,
            height,
            bytes_per_line,
            QImage.Format_RGB888,
        ).copy()

        pixmap = QPixmap.fromImage(image).scaled(
            self.preview_face_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.preview_face_label.setText("")
        self.preview_face_label.setPixmap(pixmap)

    def reset_progress_bar(self) -> None:
        self.progress_bar.setRange(0, self.COLLECTION_TARGET_FRAMES)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat(f"0 / {self.COLLECTION_TARGET_FRAMES} frames")

    def sync_button_states(self) -> None:
        busy = self.state in {AppState.COUNTDOWN, AppState.COLLECTING, AppState.ANALYZING}

        self.start_camera_button.setEnabled(not self.camera_running)
        self.stop_button.setEnabled(self.camera_running and not busy)
        if busy or not self.camera_running:
            self.measure_button.setEnabled(False)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.update_responsive_layout(self.width())

    def closeEvent(self, event) -> None:
        self.close_requested.emit()
        event.accept()


def main() -> None:
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = AgeEstimatorWindow()
    window.helper_label.setText(
        "단독 실행 모드입니다. 카메라/추론을 사용하려면 "
        "python -m face_age_gender_predictor.app.main_app 로 실행하세요."
    )
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
