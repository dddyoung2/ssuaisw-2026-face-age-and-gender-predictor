"""Plot threaded and single-threaded run metric JSON files.

Examples:
  python scripts/plot_run_metrics.py
  python scripts/plot_run_metrics.py --threaded logs/threaded_runs --single logs/single_thread_runs
"""

import argparse
import json
from pathlib import Path
from statistics import mean


METRIC_KEYS = [
    "capture_duration",
    "inference_duration",
    "result_latency",
    "max_gui_heartbeat_gap_during_inference",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot comparison metrics.")
    parser.add_argument("--threaded", default="logs/threaded_runs")
    parser.add_argument("--single", default="logs/single_thread_runs")
    parser.add_argument("--output", default="logs/comparison_summary.png")
    return parser.parse_args()


def load_runs(log_dir: str | Path, mode: str) -> list[dict]:
    path = Path(log_dir)
    rows = []
    for item in sorted(path.glob(f"*_{mode}.json")):
        with item.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        rows.append(payload)
    return rows


def metric_values(runs: list[dict], key: str) -> list[float]:
    values = []
    for run in runs:
        value = (run.get("durations") or {}).get(key)
        if value is not None:
            values.append(float(value))
    return values


def mean_or_zero(values: list[float]) -> float:
    return mean(values) if values else 0.0


def main() -> None:
    args = parse_args()
    threaded = load_runs(args.threaded, "threaded")
    single = load_runs(args.single, "single_thread")

    if not threaded and not single:
        raise SystemExit("No metric JSON files found.")

    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    axes = axes.flatten()

    for axis, key in zip(axes, METRIC_KEYS):
        threaded_values = metric_values(threaded, key)
        single_values = metric_values(single, key)
        labels = ["threaded", "single"]
        means = [mean_or_zero(threaded_values), mean_or_zero(single_values)]

        bars = axis.bar(labels, means, color=["#38bdf8", "#f97316"])
        axis.set_title(key)
        axis.set_ylabel("seconds")
        axis.grid(axis="y", linestyle="--", alpha=0.35)

        for bar, value in zip(bars, means):
            axis.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height(),
                f"{value:.2f}s" if value else "-",
                ha="center",
                va="bottom",
                fontsize=9,
            )

        if threaded_values:
            axis.scatter(["threaded"] * len(threaded_values), threaded_values, color="#075985", zorder=3)
        if single_values:
            axis.scatter(["single"] * len(single_values), single_values, color="#9a3412", zorder=3)

    fig.suptitle("Threaded vs Single-threaded Runtime Metrics")
    fig.tight_layout()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150)
    print(f"threaded runs: {len(threaded)}")
    print(f"single runs  : {len(single)}")
    print(f"Saved plot   : {output}")


if __name__ == "__main__":
    main()
