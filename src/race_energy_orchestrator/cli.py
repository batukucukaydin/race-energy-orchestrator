from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .config import EnergyConfig
from .data import load_lap_data
from .metrics import metrics_frame
from .model import simulate_strategy
from .report import render_report
from .segmentation import add_track_features


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="race-energy-orchestrator",
        description="Generate a predictive hybrid race energy management and clipping report.",
    )
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--event", default="Monza")
    parser.add_argument("--session", default="Q")
    parser.add_argument("--driver", default="LEC")
    parser.add_argument("--output", default="outputs/report.html")
    parser.add_argument("--metrics-output", default=None)
    parser.add_argument("--trace-output", default=None)
    parser.add_argument("--cache-dir", default="work/fastf1-cache")
    parser.add_argument("--synthetic-only", action="store_true", help="Skip FastF1 and use deterministic demo data.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = EnergyConfig()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_output = Path(args.metrics_output) if args.metrics_output else output_path.parent / "metrics.csv"
    trace_output = Path(args.trace_output) if args.trace_output else output_path.parent / "strategy_trace.csv"

    lap_data = load_lap_data(
        year=args.year,
        event=args.event,
        session_name=args.session,
        driver=args.driver,
        cache_dir=args.cache_dir,
        synthetic_only=args.synthetic_only,
    )
    featured = add_track_features(lap_data.frame, config)
    fixed = simulate_strategy(featured, config, "fixed_map")
    predictive = simulate_strategy(featured, config, "predictive_mpc")

    metrics = metrics_frame([fixed, predictive], config)
    combined_trace = pd.concat([fixed, predictive], ignore_index=True)

    metrics_output.parent.mkdir(parents=True, exist_ok=True)
    trace_output.parent.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(metrics_output, index=False)
    combined_trace.to_csv(trace_output, index=False)
    render_report(lap_data, featured, fixed, predictive, metrics, config, output_path)

    print(f"Report: {output_path}")
    print(f"Metrics: {metrics_output}")
    print(f"Trace: {trace_output}")
    print(f"Data source: {lap_data.source} - {lap_data.source_detail}")
    return 0
