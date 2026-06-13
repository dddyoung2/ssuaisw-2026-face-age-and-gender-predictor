# ACCEPTANCE

This task is complete when the following conditions are met.

## Scope Fit

- [ ] The implementer confirms the work remains within the real-time face age/gender predictor scope.
- [ ] The implementer confirms this is handled as QThread integration owner work: camera/model processing is connected through the existing QThread architecture, not through a new parallel app path.
- [ ] Any discovered out-of-scope item is reported before implementation rather than silently added.

## Re-Measurement Flow

- [ ] After one successful measurement, the app returns to a recoverable idle/detection state without restarting.
- [ ] Camera detection resumes automatically after a successful result when the camera is still running.
- [ ] The measurement button is disabled immediately after completion until a new ready face is detected.
- [ ] When a face is detected again, the measurement button becomes enabled again.
- [ ] Re-enabling the measurement button does not automatically clear the previous result display.
- [ ] Previous face preview/photo, graph/probability display, age, gender, and confidence remain visible until the user starts the next measurement.
- [ ] When the user starts the next measurement, stale result/progress/countdown/captured-preview UI is reset for the new run.
- [ ] A second measurement can be started and completed in the same app session.
- [ ] Failure paths also recover to detection/idle where retry is possible.
- [ ] The previous result display does not block a later measurement.
- [ ] Camera stop/start still works after one or more measurements.
- [ ] App shutdown still releases camera and worker resources.

## Model Integration

- [ ] `CNNmodel.py` can be imported without loading the model.
- [ ] `CNNmodel.py` can be imported without reading sample images, running sample inference, printing final sample output, or opening plots.
- [ ] `CNNmodel.py` exposes `predict_frames(frames: list) -> list[dict]`.
- [ ] The default model path is repository-root-relative `models/Best_Age_Estimate_model_traced.pt`.
- [ ] The path resolver works from the normal `main_app` execution flow, not only from the repository root current working directory.
- [ ] If the expected `.pt` file is missing, the app reports a clear model-file error instead of returning fake predictions.
- [ ] The missing-file error message names `models/Best_Age_Estimate_model_traced.pt`.
- [ ] TorchScript model loading is lazy and occurs only when prediction is requested.
- [ ] Model loading is cached/reused where reasonable for repeated measurements.
- [ ] `InferenceWorker` calls `CNNmodel.predict_frames(self.frames)`.
- [ ] `InferenceWorker` no longer generates random temporary predictions for the production path.
- [ ] Prediction dicts contain `age`, `gender`, `age_probs`, and `gender_confidence`.
- [ ] Prediction dicts are compatible with `result_processor.process_predictions`.
- [ ] Unusable frames are skipped or handled without arbitrary placeholder predictions.
- [ ] Model load/preprocessing/inference exceptions are routed to `error_occurred`.
- [ ] `finished` is emitted after inference success or failure.

## QThread / Threading

- [ ] Camera capture runs through `CameraBridgeWorker` / `CameraDetector`, not GUI slots.
- [ ] 40-frame capture does not run in the GUI MainThread.
- [ ] Model preprocessing does not run in the GUI MainThread.
- [ ] TorchScript model loading and forward pass do not run in the GUI MainThread.
- [ ] `InferenceWorker` runs in `InferenceThread`.
- [ ] `python -m face_age_gender_predictor.app.main_app` uses the QThread-connected `SystemController` -> `InferenceWorker` -> `CNNmodel.predict_frames` path.
- [ ] GUI updates are performed via signals/slots.
- [ ] `inference_thread` and `inference_worker` references are cleared after completion.
- [ ] Camera worker/thread cleanup still works after stop and app shutdown.
- [ ] Re-measurement does not create duplicate stale workers or duplicate signal connections.

## Tests

- [ ] Automated tests pass without requiring the real `.pt` file.
- [ ] A test verifies `CNNmodel.py` import has no model-load/sample-run side effects.
- [ ] A test verifies the default model path resolves to repository-root `models/Best_Age_Estimate_model_traced.pt`.
- [ ] A test verifies `InferenceWorker` delegates to `predict_frames`.
- [ ] A test verifies inference exceptions are routed to `error_occurred` and `finished`.
- [ ] A test verifies second-measurement recovery or the equivalent controller state transition.
- [ ] A test or documented smoke check verifies the normal `main_app` path is wired to the QThread-based inference flow.
- [ ] Existing camera detector tests pass.
- [ ] Existing result processor tests pass.
- [ ] If real `.pt` execution cannot be tested locally, it is recorded as Not Verified with the reason.

## Manual QA

- [ ] Start app and camera.
- [ ] Confirm face ready enables the capture/analysis button.
- [ ] Complete one normal measurement.
- [ ] Confirm detection resumes automatically.
- [ ] Confirm the capture/analysis button is re-enabled when the face is ready again.
- [ ] Complete a second measurement without restarting the app.
- [ ] Confirm missing model file shows a clear GUI error if the `.pt` file is unavailable.
- [ ] Confirm closing the app releases the camera.

## Documentation

- [ ] `AI-Agents/IMPLEMENTATION.md` records changed files.
- [ ] `AI-Agents/IMPLEMENTATION.md` records test commands and results.
- [ ] `AI-Agents/IMPLEMENTATION.md` records whether repository-root `models/Best_Age_Estimate_model_traced.pt` was visible in the execution environment and whether real model inference was verified.
- [ ] `AI-Agents/IMPLEMENTATION.md` records any model output-shape assumptions or mismatches.
- [ ] `AI-Agents/REVIEW.md` is left for Codex QA.
- [ ] `AI-Agents/PR.md` is not written by Claude Code.

## Guardrails

- [ ] No `.env`, secret, personal image, or large model file is added.
- [ ] No `models/*.pt`, `models/*.pth`, or `models/*.onnx` file is modified or staged.
- [ ] No unrelated refactor is included.
- [ ] No direct push to `main`.
