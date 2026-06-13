# -*- coding: utf-8 -*-
"""공유 pytest 픽스처.

PyQt 위젯/QObject 테스트가 한 프로세스에서 공존할 수 있도록 offscreen QApplication을
세션 단위로 하나만 생성해 제공한다. (프로세스당 QApplication은 하나만 존재 가능)
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app
