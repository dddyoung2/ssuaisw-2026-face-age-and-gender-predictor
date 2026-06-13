# TASK

## TL;DR

- Goal: Complete the real measurement loop for the PyQt face age/gender predictor: after one successful measurement, the app must return to face detection, re-enable measurement when a face is ready, and run the next capture/analysis without restarting the app.
- Goal: Verify and complete the actual TorchScript `.pt` model integration. `InferenceWorker` must use the real model API instead of temporary random predictions.
- Goal: Confirm the QThread split remains correct: camera capture and heavy preprocessing/model inference must stay outside the GUI MainThread.
- Scope: controller state recovery, camera detection resume flow, inference/model API connection, worker/thread tests, and QA documentation.
- Role boundary: this is assigned to the QThread integration owner. Connecting camera/model work through QThread paths is in scope, as long as the existing architecture is preserved.
- Do not change: model weights, training logic, large assets, broad UI redesign, unrelated docs, GitHub PR text.

## Scope Review

These requested items are in scope for this project.

- Re-measurement after a successful result is a core GUI workflow for a real-time face age/gender predictor. Users should not need to restart the app after every measurement.
- Actual `.pt` model integration is central to the project. The current app cannot be considered complete if it returns temporary/random age and gender predictions.
- QThread separation is required because camera capture, face preprocessing, and model inference can block the GUI if they run on the MainThread.
- This task may touch the QThread/SystemController, CameraWorker/InferenceWorker, and model API boundary because the requested outcome is a working QThread-connected `main_app` flow. Keep changes limited to that integration path.

No requested item appears outside the project topic. Implement the items below unless a concrete technical blocker is found during implementation.

## Current Findings From Pre-Check

- `SystemController` already has a recovery shape: `on_inference_done()` calls `_return_to_idle()`, and `_return_to_idle()` emits `resume_detection_requested` when the camera is still running.
- Despite that design, the reported behavior is that after one successful measurement the app does not reliably re-detect and re-enable the capture/analysis button. Treat this as a functional bug to fix and test.
- `InferenceWorker` currently creates temporary random prediction dictionaries.
- `CNNmodel.py` currently behaves like notebook/sample code and performs model loading/sample inference work at module import time.
- The intended model path is repository-root-relative: `models/Best_Age_Estimate_model_traced.pt`. The user reports that the repo root contains `models/` and the `.pt` file there. In this Codex sandbox view, the `models/` directory was not visible, so implementation must resolve the repo-root path correctly, use the real file when present in the user's environment, and fail clearly when it is absent.
- Camera and inference workers are already moved to QThreads in `SystemController`, but the final implementation must verify that the real model path still runs in `InferenceThread`, not in the GUI MainThread.
- The final app entry point to verify is `python -m face_age_gender_predictor.app.main_app`.

## User-Facing Goal

The intended user flow is:

```text
Start app
-> Start camera
-> Face becomes ready
-> Capture/analysis button becomes enabled
-> User runs measurement
-> Countdown, 40-frame capture, model analysis, result display
-> App returns to detection mode automatically
-> Face becomes ready again
-> Capture/analysis button becomes enabled again
-> Previous result stays visible until the user starts the next measurement
-> User can measure again without restarting the app
```

## Requirements

### 1. Re-Measurement After Success

- After a successful result, the app must resume camera face detection automatically if the camera is still running.
- The app must return to `IDLE` or equivalent measurement-ready state after displaying the result.
- The measurement button must become disabled immediately after completion, then become enabled again only when a face is detected/ready again.
- The previous result UI must remain visible after the app returns to detection mode. Do not automatically clear the previous face preview/photo, age, gender, confidence, or graph simply because a new face is detected.
- Re-enabling the measurement button must only mean "a new measurement can be started"; it must not itself reset the previous result display.
- When the user clicks the re-enabled measurement button to start a new measurement, clear or reset stale measurement-specific UI for the new run, including previous result text, graph/probability display, progress, countdown, and captured preview state as appropriate.
- The previous result must not block the next measurement after the user starts the new run.
- `face_ready` state must be refreshed from the camera worker after detection resumes.
- `resume_detection_requested` must reach `CameraBridgeWorker.resume_detection()` after success and recoverable failure.
- Repeated successful measurements must work in the same app session:

```text
measurement 1 success -> re-detect -> measurement 2 success
```

- Repeated failure/retry must also recover:

```text
measurement failure -> re-detect -> measurement retry
```

- Closing/restarting the camera should not be required for the second measurement.
- Add tests or a targeted smoke script for controller state transitions if full GUI automation is impractical.

### 2. Actual `.pt` Model Integration

- `src/face_age_gender_predictor/inference/CNNmodel.py` must be safe to import.
- Importing `CNNmodel.py` must not load the model, read a sample image, run sample inference, print final sample results, or open matplotlib windows.
- Provide an inference API:

```python
def predict_frames(frames: list) -> list[dict]:
    ...
```

- Use repository-root-relative `models/Best_Age_Estimate_model_traced.pt` as the default model path.
- The model file remains external and must not be committed.
- If the model file is missing, report a clear error that names the expected path.
- Load the TorchScript model lazily when inference is requested, not during import.
- Reuse the loaded model where reasonable so repeated measurements do not reload the model unnecessarily.
- For each valid frame, perform preprocessing and model inference to produce prediction dictionaries compatible with `result_processor`:

```python
{
    "age": float,
    "gender": float,
    "age_probs": list[float],
    "gender_confidence": float,
}
```

- Replace temporary/random predictions in `InferenceWorker` with `CNNmodel.predict_frames(self.frames)`.
- Do not hide model errors with random fallback predictions.
- Model load, preprocessing, or inference failures must be routed to the GUI error path via `InferenceWorker.error_occurred`.
- `main_app` must work through the QThread-connected path; do not create a parallel GUI-only or script-only inference path.
- If some frames cannot be preprocessed, skip them and let `result_processor` decide success/failure based on valid prediction count, unless the failure is global/critical.
- Preserve the documented result contract from `result_processor`.

### 3. QThread / Threading Separation

- Camera capture and frame detection must remain in the camera worker path, not in GUI slots.
- Model preprocessing and TorchScript inference must run through `InferenceWorker` in `InferenceThread`.
- GUI code must only update UI state, preview frames, progress, result labels, and error messages.
- No `torch.jit.load`, model forward pass, frame preprocessing loop, or 40-frame capture loop may run in the GUI MainThread.
- Cross-thread communication must use Qt signals/slots or the existing callback-to-signal bridge.
- Worker failures must terminate/clean up their threads and leave the app recoverable where possible.
- After inference finishes, `inference_thread` and `inference_worker` references must be cleared.
- After camera stop or app shutdown, camera resources and threads must be released.

## Target Files

Likely implementation files:

- `src/face_age_gender_predictor/app/main_app.py`
- `src/face_age_gender_predictor/app/workers.py`
- `src/face_age_gender_predictor/camera/camera_detector.py`
- `src/face_age_gender_predictor/inference/CNNmodel.py`
- `src/face_age_gender_predictor/processing/result_processor.py` only if contract compatibility requires a minimal fix
- `src/face_age_gender_predictor/app/main_window.py` only for minimal state-display/reset changes needed by the QThread-connected flow
- `tests/test_workers.py`
- `tests/test_camera_detector.py`
- New focused tests for `CNNmodel.py` or controller state transitions
- `AI-Agents/IMPLEMENTATION.md`

Avoid unless clearly necessary:

- GUI visual redesign in `main_window.py`; minimal slot/state reset changes are allowed when needed for re-measurement correctness
- Broad docs rewrites
- Build/CI configuration changes

Do not edit:

- `.env`, `.env.*`
- `models/*.pt`, `models/*.pth`, `models/*.onnx`
- Personal images or large generated assets
- `AI-Agents/PR.md` unless the user explicitly assigns Codex Release work
- GitHub PR body or release metadata

## Test / Verification Expectations

- Automated tests must not require the real `.pt` model file unless explicitly marked as optional/manual.
- Use monkeypatch/fake model objects to verify `CNNmodel.predict_frames()` contracts.
- Add or update a test that verifies the default model path resolves to repository-root `models/Best_Age_Estimate_model_traced.pt`.
- Add a test that proves importing `CNNmodel.py` has no model-load/sample-run side effects.
- Add a test that proves `InferenceWorker` delegates to `predict_frames`.
- Add a test that proves model/inference exceptions reach `error_occurred` and `finished`.
- Add or update controller/worker tests for second measurement recovery and for the QThread-connected `InferenceWorker` path used by `main_app`.
- If possible, add a manual QA checklist for:
  - first successful measurement,
  - automatic return to detection,
  - button re-enabled after face ready,
  - second successful measurement without restart,
  - model file missing error,
  - app close/camera release.

## Out of Scope

- Training or improving the model.
- Changing model output semantics beyond adapting them to the documented prediction dict.
- Adding new datasets.
- Changing the UI concept or doing a redesign.
- Committing model files.
- Opening, pushing, or merging a PR.

## Notes for Implementer

- Keep the work incremental. Fix the measurement loop and model connection without broad refactors.
- Preserve the existing app architecture: GUI -> `SystemController` -> `CameraBridgeWorker` / `InferenceWorker` -> result processor.
- Treat this as a QThread integration task: the implementation target is the normal `main_app` flow, not a standalone script.
- If the real TorchScript output shape differs from the documented sample:

```python
predicted_age, predicted_gender, age_probs, gender_confidence = model(input_tensor)
```

record the mismatch in `AI-Agents/IMPLEMENTATION.md` and adapt only as much as needed.
- If the `.pt` file is not visible in the current execution environment, do not fabricate success. Implement repository-root path resolution, test with fakes, and record that real-model execution depends on the user's environment exposing `models/Best_Age_Estimate_model_traced.pt`.
