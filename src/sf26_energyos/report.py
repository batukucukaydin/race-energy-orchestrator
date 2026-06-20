from __future__ import annotations

from html import escape
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .config import EnergyConfig, MODEL_COLUMNS, REQUIRED_INPUT_COLUMNS
from .data import LapData


def render_report(
    lap_data: LapData,
    base_frame: pd.DataFrame,
    fixed_trace: pd.DataFrame,
    predictive_trace: pd.DataFrame,
    metrics: pd.DataFrame,
    config: EnergyConfig,
    output_path: str | Path,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    fig = _build_strategy_figure(fixed_trace, predictive_trace, config)
    plot_html = fig.to_html(full_html=False, include_plotlyjs="inline")
    metrics_html = _format_metrics(metrics)
    segment_html = _segment_summary(base_frame)
    notes_html = "".join(f"<li>{escape(note)}</li>" for note in lap_data.notes)
    if not notes_html:
        notes_html = "<li>No fallback notes.</li>"

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SF26 EnergyOS Prototype Report</title>
  <style>
    :root {{
      --ink: #17202a;
      --muted: #5d6978;
      --line: #d8dee8;
      --panel: #f7f9fc;
      --accent: #b00020;
    }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: #ffffff;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 28px 22px 48px;
    }}
    h1, h2 {{
      margin: 0 0 12px;
      letter-spacing: 0;
    }}
    h1 {{
      font-size: 30px;
      line-height: 1.18;
    }}
    h2 {{
      margin-top: 28px;
      font-size: 19px;
    }}
    p, li {{
      color: var(--muted);
      line-height: 1.5;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin: 18px 0 20px;
    }}
    .stat {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      background: var(--panel);
    }}
    .stat b {{
      display: block;
      font-size: 20px;
      margin-top: 4px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 10px 0 18px;
      font-size: 13px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 8px 9px;
      text-align: right;
      vertical-align: top;
    }}
    th:first-child, td:first-child {{
      text-align: left;
    }}
    th {{
      background: var(--panel);
      color: #354052;
      font-weight: 650;
    }}
    code {{
      background: #eef2f7;
      border-radius: 4px;
      padding: 1px 4px;
    }}
    .notice {{
      border-left: 4px solid var(--accent);
      background: #fff6f7;
      padding: 10px 14px;
      margin: 18px 0;
    }}
    @media (max-width: 780px) {{
      .summary {{ grid-template-columns: 1fr; }}
      main {{ padding: 20px 14px 36px; }}
    }}
  </style>
</head>
<body>
<main>
  <h1>SF26 EnergyOS Prototype Report</h1>
  <p>Predictive 2026-style hybrid energy deployment and clipping prevention simulation.</p>
  <div class="notice">
    This report uses public FastF1 telemetry when available and synthetic 2026 ERS, battery,
    thermal, active-aero, and strategy assumptions. It is not Ferrari telemetry and does not
    represent real SF-26 parameters.
  </div>
  {_summary_cards(metrics)}
  <h2>Strategy Comparison</h2>
  {metrics_html}
  <h2>Telemetry and Energy Trace</h2>
  {plot_html}
  <h2>Segment Summary</h2>
  {segment_html}
  <h2>Data Source</h2>
  <p><b>{escape(lap_data.source)}</b>: {escape(lap_data.source_detail)}</p>
  <ul>{notes_html}</ul>
  <h2>Data Contract</h2>
  <p>Input columns: {", ".join(f"<code>{col}</code>" for col in REQUIRED_INPUT_COLUMNS)}</p>
  <p>Model columns: {", ".join(f"<code>{col}</code>" for col in MODEL_COLUMNS)}</p>
  <h2>Regulatory References</h2>
  <ul>
    <li><a href="{config.reference_links[0]}">FIA Formula One regulations category</a></li>
    <li><a href="{config.reference_links[1]}">FIA 2026 Technical Regulations Section C, Issue 18 PDF</a></li>
  </ul>
</main>
</body>
</html>
"""
    output.write_text(html, encoding="utf-8")
    return output


def _build_strategy_figure(
    fixed_trace: pd.DataFrame,
    predictive_trace: pd.DataFrame,
    config: EnergyConfig,
) -> go.Figure:
    fig = make_subplots(
        rows=6,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.035,
        subplot_titles=(
            "Speed",
            "Driver Inputs",
            "MGU-K Deploy / Regen",
            "Energy Store SoC",
            "Battery Temperature",
            "Clipping Risk and Active Aero",
        ),
    )

    x = predictive_trace["distance_m"]
    fig.add_trace(go.Scatter(x=x, y=predictive_trace["speed_kmh"], name="Speed km/h", line=dict(color="#2f6f9f")), row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=predictive_trace["throttle"], name="Throttle %", line=dict(color="#1f9d55")), row=2, col=1)
    fig.add_trace(go.Scatter(x=x, y=predictive_trace["brake"], name="Brake %", line=dict(color="#c0362c")), row=2, col=1)

    fig.add_trace(go.Scatter(x=x, y=fixed_trace["deploy_kw"], name="Fixed deploy kW", line=dict(color="#f59e0b")), row=3, col=1)
    fig.add_trace(go.Scatter(x=x, y=predictive_trace["deploy_kw"], name="Predictive deploy kW", line=dict(color="#2563eb")), row=3, col=1)
    fig.add_trace(go.Scatter(x=x, y=-fixed_trace["regen_kw"], name="Fixed regen kW", line=dict(color="#fbbf24", dash="dot")), row=3, col=1)
    fig.add_trace(go.Scatter(x=x, y=-predictive_trace["regen_kw"], name="Predictive regen kW", line=dict(color="#60a5fa", dash="dot")), row=3, col=1)

    fig.add_trace(go.Scatter(x=x, y=fixed_trace["soc_mj"], name="Fixed SoC MJ", line=dict(color="#92400e")), row=4, col=1)
    fig.add_trace(go.Scatter(x=x, y=predictive_trace["soc_mj"], name="Predictive SoC MJ", line=dict(color="#1d4ed8")), row=4, col=1)
    fig.add_hline(y=config.minimum_soc_mj, row=4, col=1, line=dict(color="#b91c1c", dash="dash"))

    fig.add_trace(go.Scatter(x=x, y=fixed_trace["battery_temp_c"], name="Fixed battery C", line=dict(color="#b45309")), row=5, col=1)
    fig.add_trace(go.Scatter(x=x, y=predictive_trace["battery_temp_c"], name="Predictive battery C", line=dict(color="#0f766e")), row=5, col=1)
    fig.add_hline(y=config.battery_soft_limit_c, row=5, col=1, line=dict(color="#ea580c", dash="dash"))

    aero_numeric = predictive_trace["aero_mode"].map({"Z_MODE": 0, "X_MODE": 1})
    fig.add_trace(go.Scatter(x=x, y=fixed_trace["clipping_risk"], name="Fixed clipping risk", line=dict(color="#dc2626")), row=6, col=1)
    fig.add_trace(go.Scatter(x=x, y=predictive_trace["clipping_risk"], name="Predictive clipping risk", line=dict(color="#7c3aed")), row=6, col=1)
    fig.add_trace(go.Scatter(x=x, y=aero_numeric, name="X_MODE active", line=dict(color="#111827", dash="dot")), row=6, col=1)

    fig.update_yaxes(title_text="km/h", row=1, col=1)
    fig.update_yaxes(title_text="%", row=2, col=1)
    fig.update_yaxes(title_text="kW", row=3, col=1)
    fig.update_yaxes(title_text="MJ", row=4, col=1)
    fig.update_yaxes(title_text="C", row=5, col=1)
    fig.update_yaxes(title_text="risk", row=6, col=1, range=[-0.05, 1.05])
    fig.update_xaxes(title_text="Distance (m)", row=6, col=1)
    fig.update_layout(
        height=1180,
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
        margin=dict(l=50, r=28, t=90, b=45),
        template="plotly_white",
    )
    return fig


def _format_metrics(metrics: pd.DataFrame) -> str:
    columns = [
        "strategy",
        "lap_time_proxy_s",
        "clipping_duration_s",
        "max_speed_loss_kmh",
        "end_soc_mj",
        "unused_energy_mj",
        "max_battery_temp_c",
        "total_deploy_mj",
        "total_regen_mj",
    ]
    table = metrics[columns].copy()
    numeric_cols = table.select_dtypes("number").columns
    table[numeric_cols] = table[numeric_cols].round(3)
    return table.to_html(index=False, escape=True)


def _segment_summary(frame: pd.DataFrame) -> str:
    grouped = (
        frame.groupby(["segment_type", "aero_mode"], as_index=False)
        .agg(distance_m=("ds_m", "sum"), duration_s=("dt_s", "sum"), mean_speed_kmh=("speed_kmh", "mean"))
        .sort_values(["segment_type", "aero_mode"])
    )
    grouped[["distance_m", "duration_s", "mean_speed_kmh"]] = grouped[
        ["distance_m", "duration_s", "mean_speed_kmh"]
    ].round(2)
    return grouped.to_html(index=False, escape=True)


def _summary_cards(metrics: pd.DataFrame) -> str:
    fixed = metrics[metrics["strategy"] == "fixed_map"].iloc[0]
    predictive = metrics[metrics["strategy"] == "predictive_mpc"].iloc[0]
    clipping_delta = fixed["clipping_duration_s"] - predictive["clipping_duration_s"]
    lap_delta = fixed["lap_time_proxy_s"] - predictive["lap_time_proxy_s"]
    risk_delta = fixed["max_clipping_risk"] - predictive["max_clipping_risk"]
    return f"""
  <div class="summary">
    <div class="stat">Lap proxy improvement<b>{lap_delta:.3f} s</b></div>
    <div class="stat">Clipping reduction<b>{clipping_delta:.3f} s</b></div>
    <div class="stat">Max risk reduction<b>{risk_delta:.3f}</b></div>
  </div>
"""
