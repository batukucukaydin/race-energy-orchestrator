from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

import pandas as pd

from .config import EnergyConfig
from .data import load_lap_data
from .metrics import metrics_frame
from .model import simulate_strategy
from .pages import render_support_pages
from .report import render_report
from .scenarios import compare_scenarios
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
    parser.add_argument("--ambient-temp-c", type=float, default=None, help="Override ambient temperature for scenario runs.")
    parser.add_argument("--initial-soc-mj", type=float, default=None, help="Override starting Energy Store state in MJ.")
    parser.add_argument(
        "--initial-battery-temp-c",
        type=float,
        default=None,
        help="Override starting battery temperature in Celsius.",
    )
    parser.add_argument("--horizon-s", type=float, default=None, help="Override predictive strategy lookahead horizon.")
    parser.add_argument(
        "--compare-scenarios",
        action="store_true",
        help="Run baseline, hot, low-SoC, and thermal-stress comparisons.",
    )
    parser.add_argument("--comparison-output", default=None, help="CSV path for the scenario comparison.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = _config_from_args(args)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_output = Path(args.metrics_output) if args.metrics_output else None
    trace_output = Path(args.trace_output) if args.trace_output else None

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
    comparison = None
    comparison_output = None
    if args.compare_scenarios:
        comparison = compare_scenarios(lap_data.frame, config)
        comparison_output = Path(args.comparison_output) if args.comparison_output else None
    if comparison_output is not None:
        comparison_output.parent.mkdir(parents=True, exist_ok=True)
        comparison.to_csv(comparison_output, index=False)

    if metrics_output is not None:
        metrics_output.parent.mkdir(parents=True, exist_ok=True)
        metrics.to_csv(metrics_output, index=False)
    if trace_output is not None:
        trace_output.parent.mkdir(parents=True, exist_ok=True)
        combined_trace.to_csv(trace_output, index=False)
    render_report(
        lap_data,
        featured,
        fixed,
        predictive,
        metrics,
        config,
        output_path,
        comparison,
        year=args.year,
        event=args.event,
        session_name=args.session,
        driver=args.driver,
    )
    render_support_pages(output_path.parent, lap_data, fixed, predictive, config)

    print(f"Report: {output_path}")
    if metrics_output is not None:
        print(f"Metrics: {metrics_output}")
    if trace_output is not None:
        print(f"Trace: {trace_output}")
    if comparison_output is not None:
        print(f"Scenario comparison: {comparison_output}")
    print(f"Data source: {lap_data.source} - {lap_data.source_detail}")
    return 0


def _config_from_args(args: argparse.Namespace) -> EnergyConfig:
    config = EnergyConfig()
    overrides = {}
    if args.ambient_temp_c is not None:
        overrides["ambient_temp_c"] = args.ambient_temp_c
    if args.initial_soc_mj is not None:
        overrides["initial_soc_mj"] = args.initial_soc_mj
    if args.initial_battery_temp_c is not None:
        overrides["initial_battery_temp_c"] = args.initial_battery_temp_c
    if args.horizon_s is not None:
        overrides["horizon_s"] = args.horizon_s
    if overrides:
        config = replace(config, **overrides)
    return config
