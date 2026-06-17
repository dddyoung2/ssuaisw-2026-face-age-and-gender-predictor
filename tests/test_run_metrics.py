import json

import pytest

from face_age_gender_predictor.processing.run_metrics import RunMetricLogger


def test_run_metric_logger_writes_csv_and_json(tmp_path):
    logger = RunMetricLogger(log_dir=tmp_path, mode="single_thread")

    logger.start_run(camera_index=2)
    logger.mark("camera_start_requested")
    logger.mark("camera_started")
    logger.mark("measurement_requested")
    logger.mark("capture_started")
    logger.mark("capture_finished", frames=40)
    logger.mark("inference_started", frames=40)
    logger.mark("inference_finished", predictions=40)
    logger.mark("result_ready", success=True, valid_count=40)
    summary = logger.finish(success=True, reason=None, result={"success": True})

    assert summary.csv_path.exists()
    assert summary.json_path.exists()
    assert summary.durations["capture_duration"] is not None
    assert "RunSummary" in summary.to_terminal_text()

    payload = json.loads(summary.json_path.read_text(encoding="utf-8"))
    assert payload["mode"] == "single_thread"
    assert payload["success"] is True
    assert len(payload["events"]) >= 2


def test_finish_without_active_run_does_not_write_fake_log(tmp_path):
    logger = RunMetricLogger(log_dir=tmp_path, mode="single_thread")

    with pytest.raises(RuntimeError, match="cannot finish metrics"):
        logger.finish(success=True, result={"success": True})

    assert list(tmp_path.iterdir()) == []
