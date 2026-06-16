"""
main_window.py
==============
PyQt5 GUI 화면 계층(View).

이 창은 카메라 읽기/얼굴 감지/추론을 직접 수행하지 않는다. 모든 무거운 작업은
SystemController가 단일 Qt 이벤트 루프에서 담당하고, GUI는 다음만 책임진다.

- 버튼 입력을 signal로 SystemController에 전달
- SystemController가 보내주는 상태/프레임/진행률/결과/오류를 화면에 표시

즉 GUI 위젯 갱신과 앱 작업은 같은 Qt 이벤트 루프에서 순차적으로 일어난다.

단독 실행(`python -m ...app.main_window`)도 가능하지만, 그 경우 SystemController가
없으므로 카메라/추론 동작 없이 빈 창만 뜬다. 정식 진입점은 `app.main_app`이다.
"""

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


# SystemController(AppState)의 상태 이름 → GUI 표시 상태 매핑
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
    AppState.READY: StateMeta("준비 완료", "READY", "얼굴을 가이드 박스 안에 맞춘 뒤 측정을 시작해주세요.", "#8DD8F8"),
    AppState.COUNTDOWN: StateMeta("카운트다운", "COUNTDOWN", "곧 촬영이 시작됩니다. 잠시 가만히 있어주세요.", "#f59e0b"),
    AppState.COLLECTING: StateMeta("프레임 캡처 중", "CAPTURING", "40프레임을 캡처하는 중입니다. 움직이지 말아주세요.", "#38bdf8"),
    AppState.ANALYZING: StateMeta("분석 중", "ANALYZING", "수집한 프레임으로 나이와 성별을 추정하고 있습니다.", "#8b5cf6"),
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
        self.setMinimumHeight(84 if not accent else 92)

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
            font-weight: 700;
            min-height: {min_height}px;
            padding: 0px;
            """
        )


class AgeHistogramWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.values = [0] * 26
        self.setMinimumHeight(210)
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
        painter.fillRect(rect, QColor("#091522"))

        painter.setPen(QPen(QColor("#21314a"), 1))
        painter.drawRoundedRect(rect.adjusted(0, 0, -1, -1), 18, 18)

        title_font = QFont("Pretendard", 11)
        title_font.setWeight(QFont.Bold)
        painter.setFont(title_font)
        painter.setPen(QColor("#f8fafc"))
        painter.drawText(16, 28, "나이 히스토그램")

        chart_left = 16
        chart_top = 48
        chart_right = rect.width() - 16
        chart_bottom = rect.height() - 34
        chart_width = max(1, chart_right - chart_left)
        chart_height = max(1, chart_bottom - chart_top)

        painter.setPen(QPen(QColor("#1f2c40"), 1))
        painter.drawLine(chart_left, chart_bottom, chart_right, chart_bottom)

        max_value = max(self.values) if self.values else 0
        if max_value <= 0:
            painter.setPen(QColor("#7e92ad"))
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

            color = QColor("#f8d66d") if value == max_value else QColor("#38bdf8")
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(QRectF(x, y, bar_width, bar_height), 3, 3)

            if age in {15, 20, 25, 30, 35, 40}:
                label_font = QFont("Pretendard", 7)
                painter.setFont(label_font)
                painter.setPen(QColor("#8ba2bf"))
                painter.drawText(
                    QRectF(x - 6, chart_bottom + 5, bar_width + 12, 16),
                    Qt.AlignCenter,
                    str(age),
                )


class AgeEstimatorWindow(QMainWindow):
    RESPONSIVE_BREAKPOINT = 1100
    COLLECTION_TARGET_FRAMES = 40
    MODEL_INPUT_SIZE = (224, 224)
    AGE_MIN = 15
    AGE_MAX = 40

    # --- GUI → SystemController 로 보내는 입력 signal ---
    start_camera_requested = pyqtSignal()
    measurement_requested = pyqtSignal()
    stop_camera_requested = pyqtSignal()
    close_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Face Age Estimation")
        self.resize(1280, 800)
        self.setMinimumSize(900, 640)

        # 표시용 상태 (SystemController가 갱신한다)
        self.state = AppState.IDLE
        self.camera_running = False
        self.face_ready = False
        self.countdown_value = 0
        self.capture_progress = 0

        self.latest_frame: Optional[np.ndarray] = None
        self.latest_face_box: Optional[FaceBox] = None
        # 이번 측정에서 캡처한 얼굴 스냅샷(결과 미리보기용).
        # latest_frame은 촬영 종료 직후 재개되는 감지 루프가 덮어쓰므로,
        # 카운트다운 동안 얼굴이 있는 프레임을 따로 고정해 결과 표시 시점에 사용한다.
        self.captured_frame: Optional[np.ndarray] = None
        self.captured_face_box: Optional[FaceBox] = None
        self.age_histogram_values = [0] * 26

        self.build_ui()
        self.apply_styles()
        self.enter_state(AppState.IDLE)
        self.set_face_status("대기", "#94a3b8")
        self.set_gender("-")
        self.set_age_result("-")
        self.set_gender_confidence("-")
        self.set_age_confidence("-")
        self.reset_progress_bar()
        self.clear_preview_panel()
        self.sync_button_states()
        self.update_responsive_layout(self.width())

    # ====================================================================
    # UI 구성
    # ====================================================================

    def build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)

        self.main_layout = QBoxLayout(QBoxLayout.LeftToRight, root)
        self.main_layout.setContentsMargins(18, 18, 18, 18)
        self.main_layout.setSpacing(18)

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
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(10)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        title = QLabel("Live Camera")
        title.setObjectName("videoTitle")

        subtitle = QLabel("사각형 안에 얼굴을 넣고 측정을 클릭하세요!")
        subtitle.setObjectName("videoSubtitle")
        subtitle.setWordWrap(True)

        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        self.live_state_tag = QLabel("대기 중")
        self.live_state_tag.setAlignment(Qt.AlignCenter)
        self.live_state_tag.setMinimumWidth(110)
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
        self.preview_face_label.setFixedSize(150, 150)

        preview_info_layout = QVBoxLayout()
        preview_info_layout.setSpacing(8)

        self.preview_gender_title = QLabel("성별")
        self.preview_gender_title.setObjectName("previewMetaTitle")
        self.preview_gender_value = QLabel("-")
        self.preview_gender_value.setObjectName("previewMetaValue")

        self.preview_gender_confidence_title = QLabel("성별 확신도")
        self.preview_gender_confidence_title.setObjectName("previewMetaTitle")
        self.preview_gender_confidence_value = QLabel("-")
        self.preview_gender_confidence_value.setObjectName("previewMetaValueSmall")

        self.preview_age_title = QLabel("나이")
        self.preview_age_title.setObjectName("previewMetaTitle")
        self.preview_age_value = QLabel("-")
        self.preview_age_value.setObjectName("previewMetaValue")

        self.preview_age_confidence_title = QLabel("나이 확신도")
        self.preview_age_confidence_title.setObjectName("previewMetaTitle")
        self.preview_age_confidence_value = QLabel("-")
        self.preview_age_confidence_value.setObjectName("previewMetaValueSmall")

        preview_info_layout.addWidget(self.preview_gender_title)
        preview_info_layout.addWidget(self.preview_gender_value)
        preview_info_layout.addWidget(self.preview_gender_confidence_title)
        preview_info_layout.addWidget(self.preview_gender_confidence_value)
        preview_info_layout.addSpacing(6)
        preview_info_layout.addWidget(self.preview_age_title)
        preview_info_layout.addWidget(self.preview_age_value)
        preview_info_layout.addWidget(self.preview_age_confidence_title)
        preview_info_layout.addWidget(self.preview_age_confidence_value)
        preview_info_layout.addStretch(1)

        preview_body.addWidget(self.preview_face_label, 0)
        preview_body.addLayout(preview_info_layout, 1)

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
            QMainWindow { background-color: #08111f; }

            QWidget#root {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #07101d,
                    stop: 0.45 #0b1324,
                    stop: 1 #08111f
                );
            }

            QLabel, QPushButton { font-family: "Pretendard"; }

            QFrame#videoCard, QFrame#sidePanel {
                background-color: #0d1726;
                border: 1px solid #1f2c40;
                border-radius: 22px;
            }

            QLabel#videoTitle {
                color: #f8fafc;
                font-size: 18px;
                font-weight: 800;
            }

            QLabel#videoSubtitle {
                color: #91a4bd;
                font-size: 12px;
            }

            QLabel#videoSurface {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #0a1320,
                    stop: 1 #111b2d
                );
                border: 1px solid #24344b;
                border-radius: 18px;
                color: #7e92ad;
                font-size: 22px;
                font-weight: 700;
            }

            QLabel#eyebrow {
                color: #7dd3fc;
                font-size: 11px;
                font-weight: 800;
                letter-spacing: 1px;
            }

            QLabel#panelTitle {
                color: #f8fafc;
                font-size: 24px;
                font-weight: 800;
            }

            QLabel#helperBox {
                background-color: #0a1320;
                border: 1px solid #21314a;
                border-radius: 14px;
                color: #dae7f7;
                font-size: 12px;
                padding: 12px;
                min-height: 42px;
            }

            QLabel#progressTitle {
                color: #93a5bf;
                font-size: 11px;
                font-weight: 800;
                margin-top: 4px;
            }

            QProgressBar#captureProgressBar {
                background-color: #0a1320;
                border: 1px solid #21314a;
                border-radius: 10px;
                min-height: 18px;
                color: #f8fafc;
                text-align: center;
                font-size: 11px;
                font-weight: 700;
            }

            QProgressBar#captureProgressBar::chunk {
                background-color: #38bdf8;
                border-radius: 9px;
            }

            QFrame#metricCard {
                background-color: #0a1320;
                border: 1px solid #21314a;
                border-radius: 16px;
            }

            QLabel#metricTitle {
                color: #93a5bf;
                font-size: 11px;
                font-weight: 800;
                min-height: 16px;
            }

            QLabel#metricValue {
                color: #f8fafc;
                font-size: 22px;
                font-weight: 700;
            }

            QPushButton {
                min-height: 38px;
                border-radius: 12px;
                border: none;
                font-size: 13px;
                font-weight: 700;
                padding: 8px 10px;
            }

            QPushButton#startButton {
                background-color: #23344a;
                color: #f8fafc;
            }

            QPushButton#startButton:hover { background-color: #2c425d; }

            QPushButton#measureButton {
                background-color: #ea580c;
                color: #ffffff;
            }

            QPushButton#measureButton:hover { background-color: #f97316; }

            QPushButton#stopButton {
                background-color: #334155;
                color: #e2e8f0;
            }

            QPushButton#stopButton:hover { background-color: #41536a; }

            QPushButton:disabled {
                background-color: #334155;
                color: #94a3b8;
            }

            QFrame#previewCard {
                background-color: #091522;
                border: 1px solid #21314a;
                border-radius: 18px;
            }

            QLabel#previewTitle {
                color: #f8fafc;
                font-size: 14px;
                font-weight: 800;
            }

            QLabel#previewFace {
                background-color: #0a1320;
                border: 1px solid #24344b;
                border-radius: 14px;
                color: #7e92ad;
                font-size: 14px;
                font-weight: 700;
            }

            QLabel#previewMetaTitle {
                color: #8ba2bf;
                font-size: 12px;
                font-weight: 700;
            }

            QLabel#previewMetaValue {
                color: #f8fafc;
                font-size: 24px;
                font-weight: 800;
                min-height: 28px;
            }

            QLabel#previewMetaValueSmall {
                color: #cbd5e1;
                font-size: 18px;
                font-weight: 800;
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

    # ====================================================================
    # 버튼 → signal (실제 동작은 SystemController가 수행)
    # ====================================================================

    def _emit_start_camera(self) -> None:
        self.start_camera_requested.emit()

    def _emit_measurement(self) -> None:
        self.measurement_requested.emit()

    def _emit_stop_camera(self) -> None:
        self.stop_camera_requested.emit()

    # ====================================================================
    # SystemController → GUI slot (MainThread에서만 위젯 갱신)
    # ====================================================================

    @pyqtSlot(str)
    def on_status_message(self, message: str) -> None:
        # 상태 메시지를 보조 안내 영역에 표시한다.
        self.helper_label.setText(message)

    @pyqtSlot(str)
    def on_state_changed(self, state_name: str) -> None:
        mapped = CONTROLLER_STATE_MAP.get(state_name, AppState.IDLE)

        # IDLE이면서 카메라/얼굴이 준비되었으면 READY 표시
        if mapped == AppState.IDLE and self.camera_running and self.face_ready:
            mapped = AppState.READY

        # 새 측정 시작(카운트다운) 시 이전 결과와 이전 캡처 스냅샷을 정리한다.
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
            self.set_face_status("대기", "#94a3b8")
            self.reset_progress_bar()
        else:
            self.set_face_status("검색 중", "#38bdf8")
        self.sync_button_states()

    @pyqtSlot(bool)
    def on_face_ready_changed(self, ready: bool) -> None:
        self.face_ready = ready
        if not self.camera_running:
            return

        if ready:
            self.set_face_status("감지됨", "#22c55e")
            if self.state in {AppState.IDLE, AppState.READY}:
                self.enter_state(AppState.READY)
        else:
            self.set_face_status("미감지", "#f87171")
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
        # payload: (frame: np.ndarray(BGR), face_box: Optional[FaceBox])
        try:
            frame, face_box = payload
        except (TypeError, ValueError):
            return
        if frame is None:
            return

        self.latest_frame = frame
        self.latest_face_box = face_box

        # 측정이 시작된 뒤(카운트다운/캡처) 얼굴이 있는 마지막 프레임을 결과 미리보기용으로
        # 고정한다. 캡처 종료 후 재개되는 감지 루프가 latest_frame을 덮어써도, 이 스냅샷은
        # 이번 측정에서 캡처한 얼굴을 그대로 유지한다.
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
    # 결과 표시
    # ====================================================================

    @classmethod
    def _compute_age_confidence(cls, age_probs, predicted_age) -> float:
        """예측 나이 ±2세 윈도우의 확률 질량(%)을 반환한다.

        모델의 26-클래스(15~40세) 확률분포에서, 예측 나이를 중심으로 ±2세 범위에 속하는
        클래스 확률을 합산한다. 유효 클래스 범위(AGE_MIN~AGE_MAX) 밖의 나이는 제외하고,
        표시값은 0~100%로 clamp한다.
        """
        if not age_probs or predicted_age is None:
            return 0.0

        center = int(round(predicted_age))
        total = 0.0
        for age in range(center - 2, center + 3):  # center-2 .. center+2 (5개)
            if cls.AGE_MIN <= age <= cls.AGE_MAX:
                index = age - cls.AGE_MIN
                if 0 <= index < len(age_probs):
                    total += age_probs[index]

        return min(100.0, max(0.0, total * 100.0))

    def _show_success_result(self, result: dict) -> None:
        # 이번 측정에서 고정한 캡처 스냅샷으로 얼굴 미리보기를 만든다.
        # (스냅샷이 없으면 live 프레임으로 폴백)
        frame = self.captured_frame if self.captured_frame is not None else self.latest_frame
        face_box = (
            self.captured_face_box if self.captured_face_box is not None else self.latest_face_box
        )
        preview_face = self._make_preview_face(frame, face_box)
        if preview_face is not None:
            self.set_preview_face(preview_face)

        age = result.get("age")
        gender = result.get("gender")
        age_probs = result.get("age_probs") or [0.0] * 26
        gender_confidence = result.get("gender_confidence") or 0.0

        gender_text = "여성" if gender == 1 else "남성"
        self.set_gender(gender_text)
        self.set_age_result(f"{age:.0f}세" if age is not None else "-")
        self.set_gender_confidence(f"{gender_confidence * 100:.1f}%")

        # 나이 확신도: 예측 나이 ±2세 윈도우의 확률 질량을 사용자 지표로 사용
        # (단일 클래스 최댓값은 값이 너무 낮아 "나이 확신도" 라벨과 맞지 않음)
        age_confidence = self._compute_age_confidence(age_probs, age)
        self.set_age_confidence(f"{age_confidence:.1f}%")

        # 히스토그램: age_probs(26개)를 정수 스케일로 표시 (위젯이 최대값 기준 정규화)
        histogram_values = [int(round(p * 1000)) for p in age_probs]
        self.age_histogram_values = histogram_values
        self.age_histogram.set_values(histogram_values)

        self.helper_label.setText(
            f"측정 완료 — 유효 프레임 {result.get('valid_count')}개로 분석했습니다."
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

    # ====================================================================
    # 미리보기 렌더링 (전달받은 프레임에 overlay만 그린다)
    # ====================================================================

    def render_preview(self, frame: np.ndarray, face_box: Optional[FaceBox]) -> None:
        display_frame = frame.copy()
        self.draw_guide_box(display_frame)
        self.draw_status_banner(display_frame)

        if face_box is not None:
            x, y, w, h = face_box
            cv2.rectangle(display_frame, (x, y), (x + w, y + h), (36, 210, 146), 3)
            cv2.putText(
                display_frame,
                "FACE DETECTED",
                (x, max(32, y - 12)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.66,
                (36, 210, 146),
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

        cv2.rectangle(frame, (18, 16), (250, 74), (10, 17, 31), -1)
        cv2.rectangle(frame, (18, 16), (250, 74), (58, 73, 96), 1)

        cv2.putText(frame, meta.banner, (30, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(frame, "Ready when you are", (30, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (188, 200, 216), 1, cv2.LINE_AA)

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

    # ====================================================================
    # 표시 헬퍼
    # ====================================================================

    def enter_state(self, state: AppState, custom_hint: Optional[str] = None) -> None:
        self.state = state
        meta = STATE_META[state]

        self.status_card.set_value(meta.label, meta.color, 19)
        if custom_hint is not None:
            self.helper_label.setText(custom_hint)
        self.set_state_tag(meta.label, meta.color)

    def set_state_tag(self, text: str, color: str) -> None:
        self.live_state_tag.setText(text)
        self.live_state_tag.setStyleSheet(
            f"""
            QLabel {{
                background-color: {color};
                color: white;
                border-radius: 11px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 800;
            }}
            """
        )

    def set_face_status(self, text: str, color: str) -> None:
        self.face_card.set_value(text, color, 19)

    def set_gender(self, text: str) -> None:
        if text == "남성":
            color = "#60a5fa"
        elif text == "여성":
            color = "#f9a8d4"
        elif text == "미정":
            color = "#cbd5e1"
        else:
            color = "#f8fafc"

        self.preview_gender_value.setText(text)
        self.preview_gender_value.setStyleSheet(f"color: {color}; font-size: 24px; font-weight: 800;")

    def set_gender_confidence(self, text: str) -> None:
        self.preview_gender_confidence_value.setText(text)
        self.preview_gender_confidence_value.setStyleSheet("color: #7dd3fc; font-size: 18px; font-weight: 800;")

    def set_age_result(self, text: str) -> None:
        if text == "실패":
            color = "#f87171"
        elif text == "-":
            color = "#cbd5e1"
        else:
            color = "#f8d66d"

        self.preview_age_value.setText(text)
        self.preview_age_value.setStyleSheet(f"color: {color}; font-size: 28px; font-weight: 800;")

    def set_age_confidence(self, text: str) -> None:
        self.preview_age_confidence_value.setText(text)
        self.preview_age_confidence_value.setStyleSheet("color: #a7f3d0; font-size: 18px; font-weight: 800;")

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
        # 측정 버튼은 SystemController의 measure_button_enabled_changed로 제어되지만,
        # busy/카메라 상태에 따른 즉시 비활성화도 함께 보장한다.
        if busy or not self.camera_running:
            self.measure_button.setEnabled(False)

    # ====================================================================
    # 윈도우 이벤트
    # ====================================================================

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.update_responsive_layout(self.width())

    def closeEvent(self, event) -> None:
        # 종료를 SystemController에 알려 카메라 자원을 정리하게 한다.
        self.close_requested.emit()
        event.accept()


def main() -> None:
    # 단독 실행 진입점. 정식 진입점은 app.main_app.main() 이다.
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
