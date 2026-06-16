"""Plot saved single-thread metric JSON files.

Usage:
  python scripts/plot_single_thread_metrics.py --log-dir logs/single_thread_runs
"""

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot single-thread run metrics.")
    parser.add_argument("--log-dir", default="logs/single_thread_runs")
    parser.add_argument("--output", default="logs/single_thread_runs/summary.png")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    log_dir = Path(args.log_dir)
    rows = []

    for path in sorted(log_dir.glob("*_single_thread.json")):
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        row = {"run_id": payload["run_id"]}
        row.update(payload.get("durations") or {})
        rows.append(row)

    if not rows:
        raise SystemExit(f"No single-thread JSON logs found in {log_dir}")

    import matplotlib.pyplot as plt

    keys = [
        "camera_start_latency",
        "face_ready_latency",
        "capture_duration",
        "inference_duration",
        "result_latency",
    ]
    labels = [row["run_id"] for row in rows]
    x_positions = range(len(labels))

    fig, axes = plt.subplots(len(keys), 1, figsize=(12, 2.4 * len(keys)), sharex=True)
    if len(keys) == 1:
        axes = [axes]

    for axis, key in zip(axes, keys):
        values = [row.get(key) or 0 for row in rows]
        axis.bar(x_positions, values, color="#38bdf8")
        axis.set_ylabel(key)
        axis.grid(axis="y", linestyle="--", alpha=0.35)

    axes[-1].set_xticks(list(x_positions))
    axes[-1].set_xticklabels(labels, rotation=45, ha="right")
    fig.suptitle("Single-thread Experiment Metrics")
    fig.tight_layout()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150)
    print(f"Saved plot: {output}")


if __name__ == "__main__":
    main()
