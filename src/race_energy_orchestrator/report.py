from __future__ import annotations

import json
from html import escape
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .config import EnergyConfig, F1_2026_EVENTS, MODEL_COLUMNS, REQUIRED_INPUT_COLUMNS, SUPPORTED_YEAR, event_data_available
from .data import LapData
from .live import build_live_decision_feed


def render_report(
    lap_data: LapData,
    base_frame: pd.DataFrame,
    fixed_trace: pd.DataFrame,
    predictive_trace: pd.DataFrame,
    metrics: pd.DataFrame,
    config: EnergyConfig,
    output_path: str | Path,
    scenario_comparison: pd.DataFrame | None = None,
    year: int = SUPPORTED_YEAR,
    event: str = "Suzuka",
    session_name: str = "Q",
    driver: str = "LEC",
    api_base: str = "http://localhost:8001",
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    fig = _build_strategy_figure(fixed_trace, predictive_trace, config)
    plot_html = fig.to_html(full_html=False, include_plotlyjs="inline", config={"responsive": True}, div_id="reo-telemetry-plot")
    live_feed = build_live_decision_feed(predictive_trace, config)
    selection_query = "?" + urlencode({"year": year, "event": event, "session_name": session_name, "driver": driver})
    notes_html = "".join(f"<li>{escape(note)}</li>" for note in lap_data.notes) or "<li>Fallback notu yok.</li>"
    event_options = _event_options(event)

    html = f"""<!doctype html>
<html lang="tr" data-api-base="{escape(api_base)}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Race Energy Orchestrator Dashboard</title>
  <link rel="prefetch" href="explorer.html{selection_query}">
  <link rel="prefetch" href="guide.html{selection_query}">
  <style>
    :root {{
      --bg: #f3f5f2;
      --surface: #ffffff;
      --surface-strong: #171a1f;
      --ink: #14171c;
      --muted: #66717d;
      --line: #d9ded8;
      --red: #b5121b;
      --red-deep: #7f0c14;
      --teal: #007a7a;
      --amber: #bf7a00;
      --blue: #245f9f;
      --green: #2f7d4f;
      --shadow: 0 18px 44px rgba(24, 29, 35, 0.10);
    }}
    [data-theme="dark"] {{
      --bg: #0d1116;
      --surface: #151b22;
      --surface-strong: #090c10;
      --ink: #eef3f7;
      --muted: #aab6c1;
      --line: #303b47;
      --shadow: 0 18px 44px rgba(0, 0, 0, 0.28);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        linear-gradient(135deg, rgba(181, 18, 27, 0.08), transparent 26rem),
        radial-gradient(circle at 80% 0%, rgba(0, 122, 122, 0.13), transparent 21rem),
        repeating-linear-gradient(90deg, rgba(20, 23, 28, 0.025) 0 1px, transparent 1px 84px),
        var(--bg);
      font-family: "Avenir Next", "SF Pro Display", "Segoe UI", sans-serif;
      letter-spacing: 0;
      overflow-x: hidden;
    }}
    main {{
      width: min(1440px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 26px 0 44px;
    }}
    .shell {{
      display: grid;
      grid-template-columns: 260px minmax(0, 1fr);
      gap: 18px;
      align-items: start;
      min-width: 0;
    }}
    aside {{
      position: sticky;
      top: 18px;
      min-height: calc(100vh - 52px);
      padding: 18px;
      border-radius: 8px;
      background: var(--surface-strong);
      color: white;
      box-shadow: var(--shadow);
    }}
    .brand {{
      display: grid;
      gap: 4px;
      margin-bottom: 24px;
    }}
    .brand .mark {{
      width: 42px;
      height: 42px;
      display: grid;
      place-items: center;
      border-radius: 6px;
      background: linear-gradient(135deg, var(--red), #f4c430);
      font-weight: 800;
    }}
    .brand b {{
      font-size: 18px;
      margin-top: 6px;
    }}
    .brand span, aside p, .side-label {{
      color: #b8c0c8;
      line-height: 1.45;
    }}
    .side-block {{
      padding: 14px 0;
      border-top: 1px solid rgba(255, 255, 255, 0.12);
    }}
    .side-value {{
      display: block;
      margin-top: 5px;
      color: white;
      font-size: 20px;
      font-weight: 750;
    }}
    .content {{
      display: grid;
      gap: 16px;
      min-width: 0;
      max-width: 100%;
    }}
    .topbar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 16px;
    }}
    .topbar-label {{ color: var(--muted); font-size: 13px; font-weight: 700; }}
    .page-nav {{ display: inline-flex; flex-wrap: wrap; gap: 6px; align-items: center; }}
    .page-nav a {{ padding: 7px 10px; border: 1px solid var(--line); border-radius: 5px; background: var(--surface); color: var(--ink); font-size: 12px; font-weight: 800; text-decoration: none; transition: border-color .18s ease, background .18s ease, color .18s ease; }}
    .page-nav a.active {{ border-color: var(--red); color: var(--red-deep); }}
    .language-switch {{ display: inline-flex; padding: 3px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface); }}
    .language-switch button {{ border: 0; border-radius: 6px; padding: 7px 11px; background: transparent; color: var(--muted); cursor: pointer; font: inherit; font-size: 12px; font-weight: 800; }}
    .language-switch button.active {{ background: var(--surface-strong); color: white; }}
    .theme-toggle {{ min-width: 36px; min-height: 32px; padding: 6px 9px; border: 1px solid var(--line); border-radius: 6px; background: var(--surface); color: var(--ink); cursor: pointer; font: inherit; font-weight: 800; }}
    .topbar-actions {{ display: inline-flex; align-items: center; gap: 8px; margin-left: auto; }}
    [data-theme="dark"] .panel, [data-theme="dark"] .hero-main, [data-theme="dark"] .hero-metrics, [data-theme="dark"] .metric, [data-theme="dark"] .insight, [data-theme="dark"] .command, [data-theme="dark"] details {{ background: var(--surface); color: var(--ink); }}
    [data-theme="dark"] .panel table th, [data-theme="dark"] .panel table td {{ border-color: var(--line); }}
    [data-theme="dark"] input, [data-theme="dark"] select, [data-theme="dark"] button {{ color-scheme: dark; }}
    .purpose {{ display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(280px, .8fr); gap: 12px; align-items: stretch; }}
    .purpose-card {{ padding: 16px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface); }}
    .purpose-card h2 {{ margin: 0 0 7px; font-size: 18px; }}
    .purpose-card p {{ margin: 0; }}
    .resource-links {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }}
    .resource-links a {{ display: grid; gap: 5px; padding: 14px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface); color: var(--ink); text-decoration: none; box-shadow: var(--shadow); }}
    .resource-links a:hover {{ border-color: var(--red); }}
    .resource-links span {{ color: var(--muted); font-size: 12px; line-height: 1.4; }}
    .session-context {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; }}
    .session-context > div {{ min-width: 0; padding: 13px 14px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface); box-shadow: var(--shadow); }}
    .session-context span {{ display: block; color: var(--muted); font-size: 11px; font-weight: 800; text-transform: uppercase; }}
    .session-context b {{ display: block; margin-top: 6px; overflow-wrap: anywhere; font-size: 14px; }}
    .panel-note {{ margin: -7px 0 12px; color: var(--muted); font-size: 12px; }}
    .selection-bar {{ display: grid; grid-template-columns: 1fr 1.8fr 1fr 1fr auto; gap: 9px; align-items: end; padding: 14px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface); box-shadow: var(--shadow); }}
    .selection-bar label {{ display: grid; gap: 5px; color: var(--muted); font-size: 11px; font-weight: 800; text-transform: uppercase; }}
    .selection-bar select {{ width: 100%; min-height: 36px; padding: 7px 9px; border: 1px solid var(--line); border-radius: 5px; background: var(--surface); color: var(--ink); font: inherit; }}
    .selection-bar button {{ min-height: 36px; padding: 7px 12px; border: 0; border-radius: 5px; background: var(--red); color: #fff; cursor: pointer; font: inherit; font-weight: 800; }}
    .live-console {{
      display: grid;
      gap: 16px;
      padding: 20px;
      border: 1px solid #303a45;
      border-radius: 8px;
      background: #171a1f;
      color: #f7f9fc;
      box-shadow: var(--shadow);
    }}
    .live-console-head, .live-console-meta, .live-controls {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }}
    .live-console h2 {{ margin: 0; font-size: 18px; }}
    .live-console p {{ margin: 5px 0 0; color: #b8c0c8; }}
    .live-badge {{ padding: 5px 8px; border-radius: 5px; background: #22382d; color: #a6e3bd; font-size: 12px; font-weight: 800; }}
    .live-decision {{ display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(260px, .8fr); gap: 14px; }}
    .live-command {{ min-height: 176px; padding: 18px; border-radius: 7px; border-left: 5px solid var(--teal); background: #20252c; }}
    .live-command.warning {{ border-left-color: var(--amber); }}
    .live-command.advisory {{ border-left-color: var(--blue); }}
    .live-command.critical {{ border-left-color: var(--red); }}
    .live-command small {{ display: block; color: #b8c0c8; font-weight: 800; text-transform: uppercase; }}
    .live-command b {{ display: block; margin: 12px 0 8px; font-size: clamp(26px, 4vw, 44px); line-height: 1; }}
    .live-command p {{ max-width: 700px; color: #edf2f6; font-size: 15px; }}
    .live-kpis {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }}
    .live-kpi {{ padding: 13px; border: 1px solid #3a434d; border-radius: 6px; background: #20252c; }}
    .live-kpi span {{ display: block; color: #aeb9c4; font-size: 11px; font-weight: 800; text-transform: uppercase; }}
    .live-kpi b {{ display: block; margin-top: 7px; font-size: 22px; }}
    .live-controls {{ padding-top: 2px; border-top: 1px solid #303a45; }}
    .live-controls button {{ width: 36px; height: 34px; border: 1px solid #4b5661; border-radius: 5px; background: #20252c; color: #fff; cursor: pointer; font-size: 15px; }}
    .live-controls input {{ accent-color: var(--red); flex: 1 1 280px; }}
    .live-time {{ color: #b8c0c8; font-size: 12px; font-weight: 700; }}
    .live-stream {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 8px; }}
    .live-stream-item {{ padding: 9px 11px; border: 1px solid #3a434d; border-radius: 6px; background: #20252c; }}
    .live-stream-item span {{ display: block; color: #aeb9c4; font-size: 10px; font-weight: 800; text-transform: uppercase; }}
    .live-stream-item b {{ display: block; margin-top: 4px; color: #fff; font-size: 15px; }}
    .track-shell {{ position: relative; }}
    .track-marker {{ position: absolute; top: -4px; bottom: -4px; width: 3px; transform: translateX(-50%); border-radius: 4px; background: #fff; box-shadow: 0 0 0 2px var(--red), 0 0 12px rgba(181, 18, 27, 0.8); pointer-events: none; }}
    .decision-flow {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 12px; }}
    .decision-step {{ padding: 12px; border-left: 3px solid var(--red); background: #f8faf8; }}
    .decision-step b {{ display: block; margin-bottom: 5px; font-size: 13px; }}
    .decision-step span {{ color: var(--muted); font-size: 12px; line-height: 1.4; }}
    details.advanced-section {{ border: 1px solid var(--line); border-radius: 8px; background: #fff; }}
    details.advanced-section > summary {{ padding: 15px 18px; cursor: pointer; font-size: 18px; font-weight: 800; list-style-position: inside; }}
    details.advanced-section > .panel {{ border: 0; box-shadow: none; border-radius: 0; }}
    .hero {{
      min-height: 260px;
      display: grid;
      grid-template-columns: minmax(0, 1.3fr) minmax(300px, 0.7fr);
      gap: 18px;
      align-items: stretch;
      min-width: 0;
    }}
    .hero-main, .panel {{
      border: 1px solid rgba(20, 23, 28, 0.09);
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.86);
      box-shadow: var(--shadow);
      min-width: 0;
    }}
    .hero-main {{
      position: relative;
      overflow: hidden;
      padding: 26px;
      background:
        linear-gradient(110deg, rgba(23, 26, 31, 0.96), rgba(23, 26, 31, 0.82)),
        repeating-linear-gradient(45deg, rgba(255,255,255,0.10) 0 2px, transparent 2px 18px);
      color: white;
    }}
    .hero-main::after {{
      content: "";
      position: absolute;
      inset: auto -8% -28% 18%;
      height: 190px;
      transform: skewX(-18deg);
      background: linear-gradient(90deg, transparent, rgba(181, 18, 27, 0.62), rgba(244, 196, 48, 0.34));
    }}
    .eyebrow {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 5px 9px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.12);
      color: #e9edf2;
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
    }}
    h1 {{
      max-width: 760px;
      margin: 24px 0 10px;
      font-size: clamp(34px, 5vw, 74px);
      line-height: 0.94;
      letter-spacing: 0;
      overflow-wrap: anywhere;
    }}
    .hero-main p {{
      max-width: 760px;
      color: #d9e0e7;
      font-size: 16px;
      line-height: 1.55;
      position: relative;
      z-index: 1;
    }}
    .hero-metrics {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      min-width: 0;
    }}
    .compact-hero {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
      min-height: 76px;
      padding: 14px 18px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      box-shadow: var(--shadow);
    }}
    .compact-hero h1 {{ margin: 4px 0 0; font-size: 22px; line-height: 1.15; }}
    .compact-hero p {{ margin: 4px 0 0; color: var(--muted); font-size: 12px; line-height: 1.35; }}
    .compact-hero .eyebrow {{ padding: 0; background: transparent; color: var(--red); font-size: 11px; letter-spacing: .04em; }}
    .compact-hero-meta {{ display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; color: var(--muted); font-size: 12px; font-weight: 700; text-align: right; }}
    .data-status {{ margin: 12px 0; padding: 12px 14px; border: 1px solid #c58a28; border-left: 4px solid #c58a28; border-radius: 7px; background: #fff8e7; color: #68470d; font-size: 13px; }}
    [data-theme="dark"] .data-status {{ background: #332a18; color: #f4d38a; border-color: #bd8421; }}
    .metric {{
      min-height: 124px;
      padding: 16px;
      border-radius: 8px;
      background: var(--surface);
      border: 1px solid rgba(20, 23, 28, 0.08);
      box-shadow: var(--shadow);
    }}
    .metric span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
    }}
    .metric b {{
      display: block;
      margin-top: 10px;
      font-size: 30px;
      line-height: 1;
    }}
    .metric small {{
      display: block;
      margin-top: 8px;
      color: var(--muted);
    }}
    .insight-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }}
    .insight {{
      display: grid;
      gap: 8px;
      min-height: 122px;
      padding: 14px;
      border-radius: 8px;
      border: 1px solid var(--line);
      background: #fbfcfb;
    }}
    .insight span {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 750;
      text-transform: uppercase;
    }}
    .insight b {{
      font-size: 25px;
      line-height: 1;
    }}
    .insight p {{
      margin: 0;
      font-size: 13px;
    }}
    .explorer-heading, .explorer-footer {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
    }}
    .explorer-heading p {{ margin: 0; }}
    .explorer-controls {{
      display: flex;
      flex-wrap: wrap;
      align-items: end;
      gap: 10px;
      margin: 14px 0;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #f7f9f7;
    }}
    .explorer-controls label {{
      display: grid;
      gap: 5px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 750;
    }}
    .explorer-controls input[type="search"], .explorer-controls select, .explorer-controls button {{
      min-height: 34px;
      padding: 7px 9px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: white;
      color: var(--ink);
      font: inherit;
    }}
    .explorer-controls input[type="search"] {{ min-width: 230px; }}
    .explorer-controls button {{ cursor: pointer; font-weight: 700; }}
    .check-label {{ display: flex !important; align-items: center; min-height: 34px; }}
    .explorer-table-wrap {{ overflow-x: auto; max-height: 520px; border: 1px solid var(--line); border-radius: 6px; }}
    .explorer-table-wrap table {{ min-width: 980px; }}
    .explorer-table-wrap thead {{ position: sticky; top: 0; z-index: 1; }}
    .explorer-table-wrap td {{ white-space: nowrap; }}
    .incident-row td {{ color: var(--red-deep); background: #fff8f6; }}
    .explorer-footer {{ padding-top: 12px; color: var(--muted); font-size: 12px; }}
    .explorer-pages {{ display: flex; gap: 8px; }}
    .explorer-pages button {{ padding: 7px 10px; border: 1px solid var(--line); border-radius: 6px; background: white; cursor: pointer; }}
    .explorer-pages button:disabled {{ cursor: default; opacity: 0.45; }}
    .grid {{
      display: grid;
      grid-template-columns: minmax(0, 1.35fr) minmax(330px, 0.65fr);
      gap: 16px;
      align-items: start;
      min-width: 0;
    }}
    .panel {{
      padding: 18px;
      min-width: 0;
    }}
    .panel h2 {{
      margin: 0 0 12px;
      font-size: 18px;
      letter-spacing: 0;
    }}
    .plot-panel {{
      padding: 10px 10px 0;
    }}
    .plot-panel h2 {{
      padding: 8px 8px 0;
    }}
    .track {{
      display: flex;
      width: 100%;
      min-height: 42px;
      overflow: hidden;
      border-radius: 6px;
      border: 1px solid var(--line);
      background: #edf1f4;
    }}
    .track span {{
      display: block;
      min-width: 3px;
      height: 42px;
    }}
    .legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px 14px;
      margin-top: 12px;
      color: var(--muted);
      font-size: 12px;
    }}
    .legend i {{
      display: inline-block;
      width: 10px;
      height: 10px;
      border-radius: 2px;
      margin-right: 5px;
    }}
    .command-list {{
      display: grid;
      gap: 9px;
      max-height: 432px;
      overflow: auto;
      padding-right: 4px;
    }}
    .command {{
      display: grid;
      grid-template-columns: 86px minmax(0, 1fr);
      gap: 10px;
      align-items: center;
      padding: 10px;
      border-radius: 8px;
      background: #f8faf8;
      border: 1px solid var(--line);
    }}
    .command time {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }}
    .command b {{
      display: block;
      font-size: 13px;
      letter-spacing: 0;
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      width: fit-content;
      padding: 4px 8px;
      border-radius: 999px;
      background: #e9f2ef;
      color: var(--teal);
      font-size: 12px;
      font-weight: 750;
    }}
    .pill.warning {{
      background: #fff1df;
      color: var(--amber);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 0;
      font-size: 13px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 9px 8px;
      text-align: right;
      vertical-align: top;
    }}
    th:first-child, td:first-child {{
      text-align: left;
    }}
    th {{
      color: #33404c;
      background: #f4f6f5;
      font-weight: 750;
    }}
    code {{
      background: #eef2f1;
      border-radius: 4px;
      padding: 1px 4px;
    }}
    p, li {{
      color: var(--muted);
      line-height: 1.5;
      overflow-wrap: anywhere;
    }}
    a {{ color: var(--red-deep); }}
    @media (max-width: 1060px) {{
      .shell, .hero, .grid, .purpose, .live-decision {{ grid-template-columns: 1fr; }}
      aside {{ position: relative; min-height: auto; top: 0; }}
      .hero-main {{ min-height: 300px; }}
      .compact-hero {{ align-items: flex-start; flex-direction: column; }}
      .compact-hero-meta {{ justify-content: flex-start; text-align: left; }}
      .session-context {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .resource-links {{ grid-template-columns: 1fr; }}
      .selection-bar {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .live-stream {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .shell, .content, .hero, .grid, .panel {{ width: 100%; max-width: 100%; }}
    }}
    @media (max-width: 680px) {{
      main {{ width: min(100vw - 20px, 1440px); padding-top: 10px; }}
      .hero-metrics {{ grid-template-columns: 1fr; }}
      .topbar, .decision-flow {{ grid-template-columns: 1fr; flex-direction: column; align-items: stretch; }}
      .insight-grid {{ grid-template-columns: 1fr; }}
      .metric {{ min-height: 104px; }}
      .explorer-heading {{ align-items: start; flex-direction: column; }}
      .explorer-controls {{ align-items: stretch; flex-direction: column; }}
      .explorer-controls input[type="search"] {{ min-width: 0; width: 100%; }}
      .command {{ grid-template-columns: 1fr; }}
      .hero-main {{ min-height: 260px; padding: 26px 18px; }}
      .compact-hero h1 {{ font-size: 20px; }}
      .session-context {{ grid-template-columns: 1fr; }}
      .selection-bar {{ grid-template-columns: 1fr; }}
      h1 {{ max-width: min(320px, calc(100vw - 76px)); font-size: 34px; line-height: 1.02; }}
      .hero-main p, aside p {{ max-width: min(280px, calc(100vw - 96px)); font-size: 14px; }}
      .panel {{ overflow-x: auto; }}
    }}
  </style>
</head>
<body>
<main>
  <div class="topbar">
    <span class="topbar-label" data-i18n="panelPurpose">Race Energy Orchestrator / Energy decision cockpit</span>
    <nav class="page-nav" aria-label="Dashboard pages"><a class="active" href="index.html{selection_query}" data-i18n="navDashboard">Dashboard</a><a href="explorer.html{selection_query}" data-i18n="navTelemetry">Telemetry</a><a href="guide.html{selection_query}" data-i18n="navGuide">Guide</a></nav>
    <div class="topbar-actions"><div class="language-switch" aria-label="Language"><button id="lang-tr" class="active" type="button">TR</button><button id="lang-en" type="button">EN</button></div><button class="theme-toggle" id="reo-theme-toggle" type="button" aria-label="Toggle dark mode">◐</button></div>
  </div>
  <div class="shell">
    <aside>
      <div class="brand">
        <div class="mark">REO</div>
        <b>Race Energy Orchestrator</b>
        <span>Predictive race energy control</span>
      </div>
      {_side_summary(lap_data, metrics, predictive_trace)}
      <div class="side-block">
        <span class="side-label" data-i18n="sourceLabel">Veri kaynağı</span>
        <span class="side-value" id="reo-side-source">{escape(lap_data.source)}</span>
        <p id="reo-source-detail">{escape(lap_data.source_detail)}</p>
      </div>
    </aside>
    <section class="content">
      <div class="compact-hero">
        <div>
          <span class="eyebrow" data-i18n="productName">REO · Race Energy Orchestrator</span>
          <h1 data-i18n="heroTitle">Enerji karar kokpiti</h1>
          <p data-i18n="heroCopy">Sabit harita ve predictive orchestration karşılaştırması.</p>
        </div>
        <div class="compact-hero-meta">
          <span id="reo-compact-session">{escape(event)} · {escape(session_name)} · {escape(driver)}</span>
          <span data-i18n="compactStatus">Operational view</span>
        </div>
      </div>

      <section class="session-context" aria-label="Session context">
        <div><span data-i18n="trackLabel">Pist / Track</span><b id="reo-track-label">{escape(event)}-like synthetic proxy</b></div>
        <div><span data-i18n="eventLabel">Yarış / Event</span><b id="reo-event-label">{escape(str(year))} {escape(event)}</b></div>
        <div><span data-i18n="sessionLabel">Session</span><b id="reo-session-label">{escape(session_name)}</b></div>
        <div><span data-i18n="driverLabel">Driver</span><b id="reo-driver-label">{escape(driver)}</b></div>
        <div><span data-i18n="apiLabel">API durumu</span><b id="reo-api-state" data-i18n="apiChecking">Kontrol ediliyor</b></div>
      </section>
      <div id="reo-data-status" class="data-status" hidden></div>

      <form class="selection-bar" id="reo-selection-form">
        <label><span data-i18n="yearLabel">Yıl / Year</span><select id="reo-year-select"><option value="2026">2026</option></select></label>
        <label><span data-i18n="eventSelectLabel">Yarış / Track</span><select id="reo-event-select">{event_options}</select></label>
        <label><span data-i18n="sessionSelectLabel">Oturum</span><select id="reo-session-select"><option value="Q">Qualifying</option><option value="R">Race</option><option value="FP1">FP1</option><option value="FP2">FP2</option><option value="FP3">FP3</option></select></label>
        <label><span data-i18n="driverSelectLabel">Sürücü</span><select id="reo-driver-select"><option value="LEC">LEC</option><option value="VER">VER</option><option value="NOR">NOR</option><option value="HAM">HAM</option></select></label>
        <button type="submit" data-i18n="loadData">Veriyi yükle</button>
      </form>
      <script>
        (() => {{
          const query = new URLSearchParams(window.location.search);
          const selection = {{ year: '2026', event: query.get('event') || 'Suzuka', session_name: query.get('session_name') || query.get('session') || 'Q', driver: query.get('driver') || 'LEC' }};
          window.reoSelectionQuery = new URLSearchParams(selection).toString();
          const setValue = (id, value) => {{ const node = document.getElementById(id); if (node) node.value = value; }};
          setValue('reo-year-select', selection.year);
          setValue('reo-event-select', selection.event);
          setValue('reo-session-select', selection.session_name);
          setValue('reo-driver-select', selection.driver);
          document.getElementById('reo-selection-form').addEventListener('submit', event => {{
            event.preventDefault();
            const next = new URLSearchParams({{ year: document.getElementById('reo-year-select').value, event: document.getElementById('reo-event-select').value, session_name: document.getElementById('reo-session-select').value, driver: document.getElementById('reo-driver-select').value }});
            window.location.search = next.toString();
          }});
        }})();
      </script>

      <script>
        window.reoConfig = {{ battery_soft_limit_c: {config.battery_soft_limit_c}, horizon_s: {config.horizon_s}, target_finish_soc_mj: {config.target_finish_soc_mj} }};
      </script>

      <div class="hero-metrics data-dependent">
        {_kpi_cards(metrics, predictive_trace, config)}
      </div>

      {_live_decision_console(live_feed, lap_data.source)}

      <script>
        (() => {{
          const apiBase = document.documentElement.dataset.apiBase || new URLSearchParams(window.location.search).get('api_base') || '';
          window.reoApiBase = apiBase;
          const selectedQuery = window.reoSelectionQuery ? `?${{window.reoSelectionQuery}}` : '';
          const setText = (id, value) => {{ const node = document.getElementById(id); if (node) node.textContent = value; }};
          const setDataAvailability = (state, message = '') => {{
            const status = document.getElementById('reo-data-status');
            const live = state === 'live';
            const future = state === 'future';
            if (status) {{ status.hidden = live; status.textContent = message; }}
            document.querySelectorAll('.data-dependent').forEach(node => {{ node.hidden = future; }});
            if (live) setText('reo-api-state', 'LIVE');
          }};
          const syncDashboardContext = async () => {{
            try {{
              const [sessionResponse, metricsResponse] = await Promise.all([
                fetch(`${{apiBase}}/api/session${{selectedQuery}}`, {{ cache: 'no-store' }}),
                fetch(`${{apiBase}}/api/metrics${{selectedQuery}}`, {{ cache: 'no-store' }})
              ]);
              if (sessionResponse.status === 409 || metricsResponse.status === 409) {{
                const response = sessionResponse.status === 409 ? sessionResponse : metricsResponse;
                const detail = await response.json();
                setDataAvailability('future', `VERİ MEVCUT DEĞİL · ${{detail.detail || 'Bu yarış henüz tamamlanmadı.'}}`);
                setText('reo-api-state', 'VERİ YOK');
                return;
              }}
              if (!sessionResponse.ok || !metricsResponse.ok) throw new Error('API unavailable');
              setDataAvailability('live');
              const session = await sessionResponse.json();
              const metricPayload = await metricsResponse.json();
              const rows = metricPayload.rows || [];
              const fixed = rows.find(row => row.strategy === 'fixed_map');
              const predictive = rows.find(row => row.strategy === 'predictive_mpc');
              if (!fixed || !predictive) throw new Error('Metrics unavailable');
              const lapDelta = Number(fixed.lap_time_proxy_s) - Number(predictive.lap_time_proxy_s);
              const clippingDelta = Number(fixed.clipping_duration_s) - Number(predictive.clipping_duration_s);
              setText('reo-track-label', session.circuit_label);
              setText('reo-event-label', `${{session.year}} ${{session.event}}`);
              setText('reo-session-label', session.session_name);
              setText('reo-driver-label', session.driver);
              setText('reo-compact-session', `${{session.event}} · ${{session.session_name}} · ${{session.driver}}`);
              setText('reo-side-source', session.data_source);
              setText('reo-source-detail', session.source_detail);
              setText('reo-api-state', `LIVE · ${{session.data_mode}}`);
              window.reoConfig = {{ battery_soft_limit_c: Number(session.battery_soft_limit_c), horizon_s: Number(session.horizon_s), target_finish_soc_mj: Number(session.target_finish_soc_mj) }};
              setText('reo-kpi-lap', `${{lapDelta.toFixed(3)}}s`);
              setText('reo-kpi-clipping', `${{clippingDelta.toFixed(1)}}s`);
              const socRange = Math.max(Number(session.usable_energy_mj) - Number(session.minimum_soc_mj), 0.0001);
              const finishSocPct = (Number(predictive.end_soc_mj) - Number(session.minimum_soc_mj)) / socRange * 100;
              setText('reo-kpi-soc', `${{finishSocPct.toFixed(1)}}%`);
              setText('reo-kpi-soc-detail', `${{Number(predictive.end_soc_mj).toFixed(3)}} MJ`);
              setText('reo-side-lap', `${{lapDelta.toFixed(3)}} s`);
              setText('reo-side-clipping', `${{Number(predictive.clipping_duration_s).toFixed(3)}} s`);
              setText('reo-side-risk', Number(predictive.max_clipping_risk).toFixed(2));
            }} catch (error) {{
              setDataAvailability('embedded', 'ÇEVRİMDIŞI · Gömülü örnek veri gösteriliyor.');
              setText('reo-api-state', document.documentElement.lang === 'en' ? 'OFFLINE · EMBEDDED' : 'ÇEVRİMDIŞI · GÖMÜLÜ');
            }}
          }};
          syncDashboardContext();
          window.setInterval(syncDashboardContext, 3000);
        }})();
      </script>

      <div class="panel data-dependent">
        <h2 data-i18n="trackTitle">Pistte enerji planı</h2>
        {_track_ribbon(base_frame)}
      </div>

      <div class="grid">
        <div class="panel plot-panel data-dependent">
          <h2 data-i18n="telemetryTitle">Strateji grafiği / Oturum snapshot'ı</h2>
          <p class="panel-note" data-i18n="telemetryNote">Grafik, API oturumundan üretilen karşılaştırma snapshot'ıdır. Canlı karar ve KPI değerleri API'den güncellenir.</p>
          {plot_html}
          <script>
            (() => {{
              const selectedQuery = window.reoSelectionQuery ? `?${{window.reoSelectionQuery}}` : '';
              const updateTelemetry = row => {{
                if (!row) return;
                const plot = document.getElementById('reo-telemetry-plot');
                if (plot && window.Plotly) {{
                  window.Plotly.relayout(plot, {{ 'shapes[2].x0': row.distance_m, 'shapes[2].x1': row.distance_m }});
                }}
                const marker = document.getElementById('reo-track-marker');
                const total = Number(window.reoLapDistanceM || 1);
                if (marker) marker.style.left = `${{Math.max(0, Math.min(100, row.distance_m / total * 100))}}%`;
              }};
              const updateTrackRibbon = rows => {{
                const ribbon = document.getElementById('reo-track-ribbon');
                if (!ribbon || !rows?.length) return;
                const colors = {{straight:'#245f9f', acceleration:'#2f7d4f', braking:'#b5121b', slow_corner:'#bf7a00', fast_corner:'#007a7a'}};
                const labels = {{straight:'Düzlük', acceleration:'Hızlanma', braking:'Fren', slow_corner:'Yavaş viraj', fast_corner:'Hızlı viraj'}};
                const groups = [];
                rows.forEach(row => {{
                  const type = row.segment_type || 'straight';
                  const last = groups[groups.length - 1];
                  if (last && last.type === type) last.count += 1;
                  else groups.push({{type, count: 1}});
                }});
                const total = rows.length;
                ribbon.innerHTML = groups.map(group => {{
                  const width = group.count / total * 100;
                  const label = labels[group.type] || group.type;
                  return `<span title="${{label}}" style="width:${{width.toFixed(3)}}%;background:${{colors[group.type] || '#66717d'}}"></span>`;
                }}).join('');
              }};
              window.reoUpdateTelemetry = updateTelemetry;
              if (window.reoLiveRow) updateTelemetry(window.reoLiveRow);
              const html = value => String(value).replace(/[&<>\"']/g, character => ({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}}[character]));
              const number = (value, digits = 3) => Number(value || 0).toFixed(digits);
              const renderMetrics = rows => {{
                const body = document.getElementById('reo-metrics-body');
                if (!body) return;
                const labels = ['Sabit harita', 'Orchestrator'];
                const keys = ['lap_time_proxy_s','clipping_duration_s','clipping_loss_proxy_s','thermal_limited_duration_s','max_speed_loss_kmh','end_soc_mj','unused_energy_mj','max_battery_temp_c','total_deploy_mj','total_regen_mj','deploy_intensity_pct','clipping_control_score'];
                body.innerHTML = rows.map((row, index) => `<tr><td>${{labels[index] || html(row.strategy)}}</td>${{keys.map(key => `<td>${{number(row[key])}}</td>`).join('')}}</tr>`).join('');
              }};
              const renderSegments = rows => {{
                const body = document.getElementById('reo-segment-body');
                if (!body || !rows?.length) return;
                const grouped = new Map();
                rows.forEach((row, index) => {{
                  const key = `${{row.segment_type}}|${{row.aero_mode}}`;
                  const previous = rows[index - 1];
                  const distance = index && previous ? Math.max(0, Number(row.distance_m) - Number(previous.distance_m)) : 0;
                  const duration = index && previous ? Math.max(0, Number(row.time_s) - Number(previous.time_s)) : 0;
                  const item = grouped.get(key) || {{ segment_type: row.segment_type, aero_mode: row.aero_mode, distance: 0, duration: 0, speed: 0, count: 0 }};
                  item.distance += distance; item.duration += duration; item.speed += Number(row.speed_kmh); item.count += 1;
                  grouped.set(key, item);
                }});
                body.innerHTML = [...grouped.values()].map(item => `<tr><td>${{html(item.segment_type)}}</td><td>${{html(item.aero_mode)}}</td><td>${{number(item.distance, 2)}}</td><td>${{number(item.duration, 2)}}</td><td>${{number(item.speed / Math.max(item.count, 1), 2)}}</td></tr>`).join('');
              }};
              const renderTimeline = rows => {{
                const target = document.getElementById('reo-command-timeline');
                if (!target || !rows?.length) return;
                const changes = rows.filter((row, index) => index === 0 || row.driver_command !== rows[index - 1].driver_command).slice(0, 22);
                target.innerHTML = changes.map(row => `<div class="command"><time>${{number(row.time_s, 1)}}s<br>${{number(row.distance_m, 0)}}m</time><div><span class="pill">${{html(row.driver_command)}}</span><b>Risk ${{number(row.clipping_risk, 2)}} | SoC ${{number(row.soc_mj, 2)}} MJ</b></div></div>`).join('');
              }};
              let lastInsightRows = [];
              let lastInsightTrace = [];
              const insightCopy = {{
                tr: {{ gain: 'Orkestrasyon kazancı', gainCopy: 'Sabit haritaya karşı tur süresi iyileşmesi.', control: 'Clipping kontrolü', controlled: 'Kontrol altında', monitor: 'Risk izlenmeli', reduced: 'clipping süresi azaltıldı.', intensity: 'Deploy yoğunluğu', energyCopy: 'deploy, {{regen}} regen.', mode: 'Karar modu', dominant: 'Tur örneklerinin {{share}}% bölümünde baskın komut.', thermal: 'Termal pay', thermalCopy: 'Yumuşak limite göre kalan batarya sıcaklık alanı.', score: 'Kontrol skoru', scoreCopy: 'Clipping ve termal limit sürelerinden türetilen karar kalitesi.', lookahead: 'Lookahead', lookaheadCopy: 'Yaklaşan uzun düzlükler için enerji rezerv ufku.', finalSoc: 'Final SoC', finishCopy: 'Hedef finish rezervi {{target}} MJ.' }},
                en: {{ gain: 'Orchestration gain', gainCopy: 'Lap time improvement versus the fixed map.', control: 'Clipping control', controlled: 'Under control', monitor: 'Risk monitored', reduced: 'of clipping time reduced.', intensity: 'Deploy intensity', energyCopy: 'deploy, {{regen}} regen.', mode: 'Decision mode', dominant: 'Dominant command across {{share}}% of lap samples.', thermal: 'Thermal headroom', thermalCopy: 'Battery temperature margin to the soft limit.', score: 'Control score', scoreCopy: 'Decision quality derived from clipping and thermal-limit time.', lookahead: 'Lookahead', lookaheadCopy: 'Energy reserve horizon for upcoming long straights.', finalSoc: 'Final SoC', finishCopy: 'Target finish reserve: {{target}} MJ.' }}
              }};
              const renderInsights = (rows, trace) => {{
                lastInsightRows = rows || [];
                lastInsightTrace = trace || [];
                const target = document.getElementById('reo-insights');
                if (!target || !rows?.length || !trace?.length) return;
                const fixed = rows.find(row => row.strategy === 'fixed_map');
                const predictive = rows.find(row => row.strategy === 'predictive_mpc');
                if (!fixed || !predictive) return;
                const lapDelta = Number(fixed.lap_time_proxy_s) - Number(predictive.lap_time_proxy_s);
                const clippingDelta = Number(fixed.clipping_duration_s) - Number(predictive.clipping_duration_s);
                const counts = trace.reduce((map, row) => {{ map[row.driver_command] = (map[row.driver_command] || 0) + 1; return map; }}, {{}});
                const top = Object.entries(counts).sort((a, b) => b[1] - a[1])[0] || ['ENERGY HOLD', 0];
                const copy = insightCopy[document.documentElement.lang === 'en' ? 'en' : 'tr'];
                const riskState = Number(predictive.clipping_duration_s) <= 0.05 ? copy.controlled : copy.monitor;
                const runtime = window.reoConfig || {{ battery_soft_limit_c: 58, horizon_s: 30, target_finish_soc_mj: 0.45 }};
                const share = number(Number(top[1]) / trace.length * 100, 1);
                target.innerHTML = `<div class="insight"><span>${{copy.gain}}</span><b>${{number(lapDelta)}}s</b><p>${{copy.gainCopy}}</p></div><div class="insight"><span>${{copy.control}}</span><b>${{riskState}}</b><p>${{number(clippingDelta, 2)}}s ${{copy.reduced}}</p></div><div class="insight"><span>${{copy.intensity}}</span><b>${{number(predictive.deploy_intensity_pct, 1)}}%</b><p>${{number(predictive.total_deploy_mj, 2)}} MJ ${{copy.energyCopy.replace('{{regen}}', number(predictive.total_regen_mj, 2))}}</p></div><div class="insight"><span>${{copy.mode}}</span><b>${{html(top[0])}}</b><p>${{copy.dominant.replace('{{share}}', share)}}</p></div><div class="insight"><span>${{copy.thermal}}</span><b>${{number(Number(runtime.battery_soft_limit_c) - Number(predictive.max_battery_temp_c), 1)}}C</b><p>${{copy.thermalCopy}}</p></div><div class="insight"><span>${{copy.score}}</span><b>${{number(predictive.clipping_control_score, 1)}}</b><p>${{copy.scoreCopy}}</p></div><div class="insight"><span>${{copy.lookahead}}</span><b>${{number(runtime.horizon_s, 0)}}s</b><p>${{copy.lookaheadCopy}}</p></div><div class="insight"><span>${{copy.finalSoc}}</span><b>${{number(predictive.end_soc_mj, 2)}} MJ</b><p>${{copy.finishCopy.replace('{{target}}', number(runtime.target_finish_soc_mj, 2))}}</p></div>`;
              }};
              const renderScenarios = rows => {{
                const body = document.getElementById('reo-scenario-body');
                if (!body || !rows?.length) return;
                const effective = document.documentElement.lang === 'en' ? ['Effective', 'Review'] : ['Etkili', 'İncelenmeli'];
                body.innerHTML = rows.map(row => `<tr><td><b>${{html(String(row.scenario).replace('_', ' '))}}</b></td><td>${{number(row.ambient_temp_c, 1)}}C</td><td>${{number(row.lap_gain_s)}}s</td><td>${{number(row.clipping_reduction_s)}}s</td><td>${{number(row.orchestrator_thermal_limit_s)}}s</td><td>${{number(row.orchestrator_end_soc_mj)}} MJ</td><td><span class="pill${{row.effective ? '' : ' warning'}}">${{row.effective ? effective[0] : effective[1]}}</span></td></tr>`).join('');
              }};
              const updatePlotForSelection = async () => {{
                const plot = document.getElementById('reo-telemetry-plot');
                if (!plot || !window.Plotly) return;
                try {{
                  const [traceResponse, metricsResponse, scenarioResponse] = await Promise.all([
                    fetch(`${{window.reoApiBase}}/api/trace${{selectedQuery}}`, {{ cache: 'no-store' }}),
                    fetch(`${{window.reoApiBase}}/api/metrics${{selectedQuery}}`, {{ cache: 'no-store' }}),
                    fetch(`${{window.reoApiBase}}/api/scenarios${{selectedQuery}}`, {{ cache: 'no-store' }})
                  ]);
                  if (!traceResponse.ok || !metricsResponse.ok) throw new Error('Track analysis unavailable');
                  const payload = await traceResponse.json();
                  const metricPayload = await metricsResponse.json();
                  const scenarioPayload = scenarioResponse.ok ? await scenarioResponse.json() : [];
                  const fixed = payload.fixed_map;
                  const predictive = payload.predictive_mpc;
                  renderMetrics(metricPayload.rows || []);
                  renderSegments(predictive);
                  renderTimeline(predictive);
                  renderInsights(metricPayload.rows || [], predictive);
                  renderScenarios(scenarioPayload);
                  const x = predictive.map(row => row.distance_m);
                  const updates = [
                    {{ x: [x], y: [predictive.map(row => row.speed_kmh)] }},
                    {{ x: [x], y: [predictive.map(row => row.aero_mode === 'X_MODE' ? 100 : 0)] }},
                    {{ x: [x], y: [fixed.map(row => row.deploy_kw)] }},
                    {{ x: [x], y: [predictive.map(row => row.deploy_kw)] }},
                    {{ x: [x], y: [fixed.map(row => -row.regen_kw)] }},
                    {{ x: [x], y: [predictive.map(row => -row.regen_kw)] }},
                    {{ x: [x], y: [fixed.map(row => row.soc_mj)] }},
                    {{ x: [x], y: [predictive.map(row => row.soc_mj)] }},
                    {{ x: [x], y: [fixed.map(row => row.clipping_risk)] }},
                    {{ x: [x], y: [predictive.map(row => row.clipping_risk)] }},
                    {{ x: [x], y: [fixed.map(row => row.battery_temp_c)] }},
                    {{ x: [x], y: [predictive.map(row => row.battery_temp_c)] }}
                  ];
                  for (let index = 0; index < updates.length; index += 1) window.Plotly.restyle(plot, updates[index], [index]);
                  window.reoLapDistanceM = x.length ? Number(x[x.length - 1]) : 1;
                  updateTelemetry(predictive[0]);
                  updateTrackRibbon(predictive);
                }} catch (error) {{
                  console.warn('Trace API unavailable; keeping embedded chart.', error);
                }}
              window.addEventListener('reo-language-change', () => {{ renderInsights(lastInsightRows, lastInsightTrace); }});
              }};
              updatePlotForSelection();
            }})();
          </script>
        </div>
        <div class="panel data-dependent">
          <h2 data-i18n="commandsTitle">Sistemin verdiği kararlar</h2>
          {_command_timeline(predictive_trace)}
        </div>
      </div>

      <div class="grid">
        <div class="panel data-dependent">
          <h2 data-i18n="comparisonTitle">Sabit harita / Orchestrator</h2>
          {_format_metrics(metrics)}
        </div>
        <div class="panel data-dependent">
          <h2 data-i18n="segmentTitle">Pist segmentleri</h2>
          {_segment_summary(base_frame)}
        </div>
      </div>

      <div class="panel data-dependent">
        <h2 data-i18n="insightTitle">Ana sonuç</h2>
        {_orchestrator_insights(metrics, predictive_trace, config)}
      </div>

      {_scenario_comparison_panel(scenario_comparison)}

      {_support_links(selection_query)}

    </section>
  </div>
</main>
<script>
  (() => {{
    const dictionary = {{
      tr: {{ navDashboard: "Dashboard", navTelemetry: "Telemetry", navGuide: "Guide", sourceLabel: "Veri kaynağı", yearLabel: "Yıl / Year", eventSelectLabel: "Yarış / Track", loadData: "Veriyi yükle", panelPurpose: "Race Energy Orchestrator / Enerji karar paneli", productName: "Race Energy Orchestrator", heroTitle: "Enerji kararlarını daha hızlı tur için yönet.", heroCopy: "Sistem, sabit enerji haritasını öngörülü orkestrasyonla karşılaştırır ve aracın enerjiyi nerede kullanacağına karar verir.", apiChecking: "Kontrol ediliyor", mainQuestion: "Bu panel neyi cevaplıyor?", mainAnswer: "Sınırlı hibrit enerjiyi tur boyunca ne zaman deploy, ne zaman regen ve ne zaman koruma modunda kullanmak gerekir?", stepObserve: "1. Veriyi oku", stepObserveCopy: "Pist segmenti, hız, SoC ve batarya sıcaklığını izler.", stepPredict: "2. İleriyi tahmin et", stepPredictCopy: "Uzun düzlük ve fren bölgelerini lookahead ile değerlendirir.", stepDecide: "3. Karar ver", stepDecideCopy: "Deploy, regen veya enerji koruma komutunu üretir.", readingGuide: "Nasıl okunmalı?", readingGuideCopy: "Önce üstteki sonuçlara bak. Orchestrator satırı sabit haritadan daha iyi ise strateji avantaj sağlıyor. Sonra karar akışı ve telemetriyi açarak nedenini incele.", insightTitle: "Ana sonuç", trackTitle: "Pistte enerji planı", telemetryTitle: "Strateji grafiği / Oturum özeti", telemetryNote: "Grafik, API oturumundan üretilen karşılaştırma özetidir. Canlı karar ve KPI değerleri API'den güncellenir.", trackLabel: "Pist", eventLabel: "Yarış", sessionLabel: "Oturum", driverLabel: "Sürücü", apiLabel: "API durumu", commandsTitle: "Sistemin verdiği kararlar", comparisonTitle: "Sabit harita / Orchestrator", segmentTitle: "Pist segmentleri", assumptionsTitle: "Model varsayımları ve veri sözleşmesi", scenarioTitle: "Senaryo doğrulaması", rawDataTitle: "Ham telemetriyi incele", rawDataHeading: "Telemetri veri gezgini", rawDataCopy: "Ham karar akışının tamamı bu panelde. Dosya açmadan strateji, risk ve komut bazında incele.", strategyFilter: "Strateji", allOption: "Tümü", fixedOption: "Sabit harita", searchFilter: "Arama", incidentFilter: "Clipping / termal limit", clearFilters: "Filtreleri temizle" }},
      en: {{ navDashboard: "Dashboard", navTelemetry: "Telemetry", navGuide: "Guide", sourceLabel: "Data source", yearLabel: "Year", eventSelectLabel: "Event / Track", loadData: "Load data", panelPurpose: "Race Energy Orchestrator / Energy decision cockpit", productName: "Race Energy Orchestrator", heroTitle: "Manage energy decisions for a faster lap.", heroCopy: "The system compares a fixed energy map with predictive orchestration and decides where the car should use its energy.", apiChecking: "Checking", mainQuestion: "What question does this panel answer?", mainAnswer: "Across the lap, when should limited hybrid energy be deployed, regenerated, or protected?", stepObserve: "1. Read the data", stepObserveCopy: "Track segment, speed, SoC, and battery temperature are monitored.", stepPredict: "2. Look ahead", stepPredictCopy: "Long straights and braking zones are evaluated ahead of the car.", stepDecide: "3. Make the decision", stepDecideCopy: "The system produces deploy, regen, or energy-save commands.", readingGuide: "How should I read it?", readingGuideCopy: "Start with the results above. If the Orchestrator row beats the fixed map, the strategy has an advantage. Open the decision flow and telemetry to understand why.", insightTitle: "Key result", trackTitle: "Energy plan on track", telemetryTitle: "Strategy telemetry / Session snapshot", telemetryNote: "This chart is a comparison snapshot generated from the API session. Live decisions and KPI values are API-backed.", trackLabel: "Track", eventLabel: "Event", sessionLabel: "Session", driverLabel: "Driver", apiLabel: "API status", commandsTitle: "System decisions", comparisonTitle: "Fixed map / Orchestrator", segmentTitle: "Track segments", assumptionsTitle: "Model assumptions and data contract", scenarioTitle: "Scenario validation", rawDataTitle: "Inspect raw telemetry", rawDataHeading: "Telemetry data explorer", rawDataCopy: "The full decision stream lives here. Explore strategy, risk, and commands without opening a file.", strategyFilter: "Strategy", allOption: "All", fixedOption: "Fixed map", searchFilter: "Search", incidentFilter: "Clipping / thermal limit", clearFilters: "Clear filters" }}
    }};
    Object.assign(dictionary.tr, {{ panelPurpose: "Race Energy Orchestrator / Enerji karar kokpiti", heroTitle: "Enerji karar kokpiti", heroCopy: "Sabit harita ve predictive orchestration karşılaştırması.", compactStatus: "Operasyon görünümü" }});
    Object.assign(dictionary.en, {{ panelPurpose: "Race Energy Orchestrator / Energy decision cockpit", heroTitle: "Energy decision cockpit", heroCopy: "Fixed-map and predictive orchestration comparison.", compactStatus: "Operational view" }});
    Object.assign(dictionary.tr, {{ lapImprovement: "Tur süresi iyileşmesi", vsFixed: "Sabit haritaya göre", clippingReduction: "Clipping azalması", orchestratorStrategy: "Orchestrator stratejisi", regenEvents: "Regen olayları", regenPoints: "Regen karar noktası", previous: "Önceki", next: "Sonraki", orchestrationGain: "Orkestrasyon kazancı", lapGainCopy: "Sabit haritaya karşı tur süresi iyileşmesi.", clippingControl: "Clipping kontrolü", energyUse: "Deploy yoğunluğu", decisionMode: "Karar modu", dominantCommand: "Tur örneklerinin baskın komutu.", sideLap: "Tur süresi kazancı", sideClipping: "Orchestrator clipping", sideRisk: "Potansiyel clipping riski", thermalHeadroom: "Termal pay", thermalHeadroomCopy: "Yumuşak limite göre kalan batarya sıcaklık alanı.", controlScore: "Kontrol skoru", controlScoreCopy: "Clipping ve termal limit sürelerinden türetilen karar kalitesi.", lookahead: "Lookahead", lookaheadCopy: "Yaklaşan uzun düzlükler için enerji rezerv ufku.", finalSoc: "Final SoC", scenarioDescription: "Orchestrator performansı, farklı başlangıç ve termal koşullar altında aynı pist modeliyle karşılaştırılıyor.", scenarioName: "Senaryo", scenarioAmbient: "Ortam", scenarioLapGain: "Tur kazancı", scenarioClipping: "Clipping azalması", scenarioThermal: "Termal limit", scenarioFinalSoc: "Final SoC", scenarioStatus: "Durum", tableStrategy: "Strateji", tableLapProxy: "Tur proxy (s)", tableClipping: "Clipping (s)", tableClippingLoss: "Clipping zaman etkisi (proxy s)", tableThermal: "Termal limit (s)", tableSpeedLoss: "Maksimum hız kaybı", tableEndSoc: "Final SoC", tableUnused: "Kalan enerji", tableMaxTemp: "Maks. batarya sıcaklığı", tableDeploy: "Deploy MJ", tableRegen: "Regen MJ", tableIntensity: "Deploy yoğunluğu %", tableScore: "Kontrol skoru", segmentHeader: "Segment", aeroHeader: "Aero", distanceHeader: "Mesafe", durationHeader: "Süre", avgSpeedHeader: "Ort. hız" }});
    Object.assign(dictionary.en, {{ lapImprovement: "Lap time improvement", vsFixed: "Compared with fixed map", clippingReduction: "Clipping reduction", orchestratorStrategy: "Orchestrator strategy", regenEvents: "Regen events", regenPoints: "Regen decision points", previous: "Previous", next: "Next", orchestrationGain: "Orchestration gain", lapGainCopy: "Lap time improvement versus the fixed map.", clippingControl: "Clipping control", energyUse: "Deploy intensity", decisionMode: "Decision mode", dominantCommand: "Dominant command across lap samples.", sideLap: "Lap time gain", sideClipping: "Orchestrator clipping", sideRisk: "Potential clipping risk", thermalHeadroom: "Thermal headroom", thermalHeadroomCopy: "Battery temperature margin to the soft limit.", controlScore: "Control score", controlScoreCopy: "Decision quality derived from clipping and thermal-limit time.", lookahead: "Lookahead", lookaheadCopy: "Energy reserve horizon for upcoming long straights.", finalSoc: "Final SoC", scenarioDescription: "Orchestrator performance compared across starting and thermal conditions on the same track model.", scenarioName: "Scenario", scenarioAmbient: "Ambient", scenarioLapGain: "Lap gain", scenarioClipping: "Clipping reduction", scenarioThermal: "Thermal limit", scenarioFinalSoc: "Final SoC", scenarioStatus: "Status", tableStrategy: "Strategy", tableLapProxy: "Lap proxy (s)", tableClipping: "Clipping (s)", tableClippingLoss: "Clipping time effect (proxy s)", tableThermal: "Thermal limit (s)", tableSpeedLoss: "Maximum speed loss", tableEndSoc: "Final SoC", tableUnused: "Unused energy", tableMaxTemp: "Max battery temperature", tableDeploy: "Deploy MJ", tableRegen: "Regen MJ", tableIntensity: "Deploy intensity %", tableScore: "Control score", segmentHeader: "Segment", aeroHeader: "Aero", distanceHeader: "Distance", durationHeader: "Duration", avgSpeedHeader: "Avg. speed" }});
    Object.assign(dictionary.tr, {{ sessionSelectLabel: "Oturum", driverSelectLabel: "Sürücü", telemetrySupportCopy: "Ham karar kayıtlarını filtrele, karşılaştır ve incele.", guideSupportCopy: "Paneli kullanma mantığı, model sınırları ve kolon sözleşmesi.", explorerRows: "kayıt", explorerPage: "Sayfa", explorerNoResults: "Filtreye uyan kayıt yok.", explorerStrategyHeader: "Strateji", explorerTimeHeader: "Zaman", explorerDistanceHeader: "Mesafe", explorerSegmentHeader: "Segment", explorerCommandHeader: "Komut", explorerBatteryHeader: "Batarya", explorerRiskHeader: "Risk", explorerStatusHeader: "Durum" }});
    Object.assign(dictionary.en, {{ sessionSelectLabel: "Session", driverSelectLabel: "Driver", telemetrySupportCopy: "Filter, compare, and inspect raw decision records.", guideSupportCopy: "How to use the panel, model limits, and the data contract.", explorerRows: "records", explorerPage: "Page", explorerNoResults: "No records match the filters.", explorerStrategyHeader: "Strategy", explorerTimeHeader: "Time", explorerDistanceHeader: "Distance", explorerSegmentHeader: "Segment", explorerCommandHeader: "Command", explorerBatteryHeader: "Battery", explorerRiskHeader: "Risk", explorerStatusHeader: "Status" }});
    const setLanguage = language => {{
      document.documentElement.lang = language === 'en' ? 'en' : 'tr';
      window.reoLanguage = language === 'en' ? 'en' : 'tr';
      localStorage.setItem('reo-language', language);
      document.querySelectorAll('[data-i18n]').forEach(node => {{ node.textContent = dictionary[language][node.dataset.i18n] || node.textContent; }});
      document.querySelectorAll('[data-i18n-tr]').forEach(node => {{ node.textContent = language === 'en' ? node.dataset.i18nEn : node.dataset.i18nTr; }});
      document.getElementById('lang-tr').classList.toggle('active', language === 'tr');
      document.getElementById('lang-en').classList.toggle('active', language === 'en');
      window.dispatchEvent(new CustomEvent('reo-language-change', {{ detail: language }}));
    }};
    document.getElementById('lang-tr').addEventListener('click', () => setLanguage('tr'));
    document.getElementById('lang-en').addEventListener('click', () => setLanguage('en'));
    const theme = localStorage.getItem('reo-theme') || 'dark';
    const applyTheme = value => {{
      document.documentElement.dataset.theme = value;
      localStorage.setItem('reo-theme', value);
      document.getElementById('reo-theme-toggle').textContent = value === 'dark' ? '☼' : '◐';
      document.getElementById('reo-theme-toggle').setAttribute('aria-label', value === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
      const plot = document.getElementById('reo-telemetry-plot');
      if (plot && window.Plotly) window.Plotly.relayout(plot, {{ paper_bgcolor: value === 'dark' ? '#151b22' : 'rgba(0,0,0,0)', plot_bgcolor: value === 'dark' ? '#151b22' : '#fbfcfb', 'font.color': value === 'dark' ? '#eef3f7' : '#14171c' }});
    }};
    document.getElementById('reo-theme-toggle').addEventListener('click', () => applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));
    applyTheme(theme);
    setLanguage(localStorage.getItem('reo-language') || 'tr');
  }})();
</script>
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
        rows=5,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        subplot_titles=(
            "Hız ve aktif aero",
            "Deploy / recharge",
            "Energy Store SoC",
            "Potansiyel clipping riski",
            "Batarya sıcaklığı",
        ),
    )

    x = predictive_trace["distance_m"]
    aero_numeric = predictive_trace["aero_mode"].map({"Z_MODE": 0, "X_MODE": 1})
    fig.add_trace(go.Scatter(x=x, y=predictive_trace["speed_kmh"], name="Hız km/h", line=dict(color="#245f9f", width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=aero_numeric * 100, name="X_MODE x100", line=dict(color="#14171c", dash="dot")), row=1, col=1)

    fig.add_trace(go.Scatter(x=x, y=fixed_trace["deploy_kw"], name="Sabit deploy", line=dict(color="#bf7a00")), row=2, col=1)
    fig.add_trace(go.Scatter(x=x, y=predictive_trace["deploy_kw"], name="Orchestrator deploy", line=dict(color="#b5121b", width=2)), row=2, col=1)
    fig.add_trace(go.Scatter(x=x, y=-fixed_trace["regen_kw"], name="Sabit recharge", line=dict(color="#d7a84c", dash="dot")), row=2, col=1)
    fig.add_trace(go.Scatter(x=x, y=-predictive_trace["regen_kw"], name="Orchestrator recharge", line=dict(color="#007a7a", dash="dot")), row=2, col=1)

    fig.add_trace(go.Scatter(x=x, y=fixed_trace["soc_mj"], name="Sabit SoC", line=dict(color="#8a5a00")), row=3, col=1)
    fig.add_trace(go.Scatter(x=x, y=predictive_trace["soc_mj"], name="Orchestrator SoC", line=dict(color="#b5121b", width=2)), row=3, col=1)
    fig.add_hline(y=config.minimum_soc_mj, row=3, col=1, line=dict(color="#7f0c14", dash="dash"))

    fig.add_trace(go.Scatter(x=x, y=fixed_trace["clipping_risk"], name="Sabit risk", line=dict(color="#e05260")), row=4, col=1)
    fig.add_trace(go.Scatter(x=x, y=predictive_trace["clipping_risk"], name="Orchestrator risk", line=dict(color="#007a7a", width=2)), row=4, col=1)

    fig.add_trace(go.Scatter(x=x, y=fixed_trace["battery_temp_c"], name="Sabit batarya C", line=dict(color="#bf7a00")), row=5, col=1)
    fig.add_trace(go.Scatter(x=x, y=predictive_trace["battery_temp_c"], name="Orchestrator batarya C", line=dict(color="#2f7d4f", width=2)), row=5, col=1)
    fig.add_hline(y=config.battery_soft_limit_c, row=5, col=1, line=dict(color="#b5121b", dash="dash"))
    fig.add_shape(
        type="line",
        x0=float(x.iloc[0]),
        x1=float(x.iloc[0]),
        y0=0,
        y1=1,
        xref="x",
        yref="paper",
        line=dict(color="#b5121b", width=2, dash="dot"),
    )

    fig.update_yaxes(title_text="km/h", row=1, col=1)
    fig.update_yaxes(title_text="kW", row=2, col=1)
    fig.update_yaxes(title_text="MJ", row=3, col=1)
    fig.update_yaxes(title_text="risk", row=4, col=1, range=[-0.05, 1.05])
    fig.update_yaxes(title_text="C", row=5, col=1)
    fig.update_xaxes(title_text="Mesafe (m)", row=5, col=1)
    fig.update_layout(
        height=920,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=52, r=24, t=76, b=44),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#fbfcfb",
        template="plotly_white",
        font=dict(family="Avenir Next, Segoe UI, sans-serif", size=12, color="#14171c"),
    )
    return fig


def _event_options(selected_event: str) -> str:
    return "".join(
        f'<option value="{escape(event)}"{" selected" if event == selected_event else ""}{" disabled" if not event_data_available(event) else ""}>{escape(label if event_data_available(event) else f"{label} · Veri bekleniyor")}</option>'
        for event, label in F1_2026_EVENTS
    )


def _side_summary(lap_data: LapData, metrics: pd.DataFrame, predictive_trace: pd.DataFrame) -> str:
    fixed = _metric(metrics, "fixed_map")
    predictive = _metric(metrics, "predictive_mpc")
    lap_delta = fixed["lap_time_proxy_s"] - predictive["lap_time_proxy_s"]
    risk_peak = predictive_trace["clipping_risk"].max()
    return f"""
      <div class="side-block">
        <span class="side-label" data-i18n="sideLap">Tur süresi kazancı</span>
        <span class="side-value" id="reo-side-lap">{lap_delta:.3f} s</span>
      </div>
      <div class="side-block">
        <span class="side-label" data-i18n="sideClipping">Orchestrator clipping</span>
        <span class="side-value" id="reo-side-clipping">{predictive["clipping_duration_s"]:.3f} s</span>
      </div>
      <div class="side-block">
        <span class="side-label" data-i18n="sideRisk">Potansiyel clipping riski</span>
        <span class="side-value" id="reo-side-risk">{risk_peak:.2f}</span>
      </div>
"""


def _scenario_comparison_panel(comparison: pd.DataFrame | None) -> str:
    if comparison is None or comparison.empty:
        return ""
    rows = []
    for _, row in comparison.iterrows():
        status = "Etkili" if bool(row["effective"]) else "Incelenmeli"
        status_class = "pill" if bool(row["effective"]) else "pill warning"
        rows.append(
            "<tr>"
            f"<td><b>{escape(str(row['scenario']).replace('_', ' ').title())}</b></td>"
            f"<td>{row['ambient_temp_c']:.1f}C</td>"
            f"<td>{row['lap_gain_s']:.3f}s</td>"
            f"<td>{row['clipping_reduction_s']:.3f}s</td>"
            f"<td>{row['orchestrator_thermal_limit_s']:.3f}s</td>"
            f"<td>{row['orchestrator_end_soc_mj']:.3f} MJ</td>"
            f"<td><span class=\"{status_class}\">{status}</span></td>"
            "</tr>"
        )
    return f"""
      <div class="panel data-dependent">
        <h2 data-i18n="scenarioTitle">Senaryo doğrulaması</h2>
        <p data-i18n="scenarioDescription">Orchestrator performansı, farklı başlangıç ve termal koşullar altında aynı pist modeliyle karşılaştırılıyor.</p>
        <div style="overflow-x:auto">
          <table>
            <thead><tr><th data-i18n="scenarioName">Senaryo</th><th data-i18n="scenarioAmbient">Ortam</th><th data-i18n="scenarioLapGain">Tur kazancı</th><th data-i18n="scenarioClipping">Clipping azalması</th><th data-i18n="scenarioThermal">Termal limit</th><th data-i18n="scenarioFinalSoc">Final SoC</th><th data-i18n="scenarioStatus">Durum</th></tr></thead>
            <tbody id="reo-scenario-body">{''.join(rows)}</tbody>
          </table>
        </div>
      </div>
"""


def _support_links(selection_query: str) -> str:
    return """
      <section class="resource-links" aria-label="Supporting pages">
        <a href="explorer.html{selection_query}" aria-label="Telemetry Explorer"><b data-i18n="navTelemetry">Telemetry</b><span data-i18n="telemetrySupportCopy">Ham karar kayıtlarını filtrele, karşılaştır ve incele.</span></a>
        <a href="guide.html{selection_query}" aria-label="Guide &amp; Contract"><b data-i18n="navGuide">Guide</b><span data-i18n="guideSupportCopy">Paneli kullanma mantığı, model sınırları ve kolon sözleşmesi.</span></a>
      </section>
"""


def _live_decision_console(feed: pd.DataFrame, source: str) -> str:
    payload = json.dumps(feed.to_dict(orient="records"), ensure_ascii=True, allow_nan=False)
    source_label = "SYNTHETIC REPLAY" if source.lower() == "synthetic" else escape(source.upper())
    return f"""
      <section class="live-console data-dependent" aria-live="polite">
        <div class="live-console-head">
          <div><h2 id="reo-live-title">Canlı karar konsolu</h2><p id="reo-live-subtitle">Yarış mühendisi için anlık enerji önerisi</p></div>
          <span class="live-badge" id="reo-live-source">{source_label}</span>
        </div>
        <div class="live-decision">
          <div class="live-command" id="reo-live-command">
            <small id="reo-live-status">NORMAL</small>
            <b id="reo-live-action">ENERGY HOLD</b>
            <p id="reo-live-reason"></p>
          </div>
          <div class="live-kpis">
            <div class="live-kpi"><span id="reo-live-soc-label">Enerji deposu</span><b id="reo-live-soc">-</b></div>
            <div class="live-kpi"><span id="reo-live-temp-label">Batarya</span><b id="reo-live-temp">-</b></div>
            <div class="live-kpi"><span id="reo-live-risk-label">Potansiyel clipping riski</span><b id="reo-live-risk">-</b></div>
            <div class="live-kpi"><span id="reo-live-next-label">Sonraki düzlük</span><b id="reo-live-next">-</b></div>
          </div>
        </div>
        <div class="live-stream" aria-label="Live telemetry">
          <div class="live-stream-item"><span id="reo-live-speed-label">Hız</span><b id="reo-live-speed">-</b></div>
          <div class="live-stream-item"><span id="reo-live-deploy-label">Deploy</span><b id="reo-live-deploy">-</b></div>
          <div class="live-stream-item"><span id="reo-live-regen-label">Regen</span><b id="reo-live-regen">-</b></div>
          <div class="live-stream-item"><span id="reo-live-aero-label">Aero</span><b id="reo-live-aero">-</b></div>
          <div class="live-stream-item"><span id="reo-live-segment-label">Segment</span><b id="reo-live-segment">-</b></div>
        </div>
        <div class="live-console-meta"><span class="live-time" id="reo-live-context"></span><span class="live-time" id="reo-live-confidence"></span></div>
        <div class="live-controls">
          <button id="reo-live-play" type="button" aria-label="Play">&#9654;</button>
          <button id="reo-live-pause" type="button" aria-label="Pause">&#10074;&#10074;</button>
          <input id="reo-live-seek" type="range" min="0" value="0" aria-label="Replay position">
          <span class="live-time" id="reo-live-clock"></span>
        </div>
      </section>
      <script>
        (() => {{
          const feed = {payload};
          window.reoLapDistanceM = feed.length ? Number(feed[feed.length - 1].distance_m) : 1;
          const selectedQuery = window.reoSelectionQuery ? `&${{window.reoSelectionQuery}}` : '';
          const labels = {{
            tr: {{ title: 'Canlı karar konsolu', subtitle: 'Yarış mühendisi için anlık enerji önerisi', soc: 'Enerji deposu', temp: 'Batarya', risk: 'Potansiyel clipping riski', next: 'Sonraki düzlük', speed: 'Hız', deploy: 'Deploy', regen: 'Regen', aero: 'Aero', segment: 'Segment', confidence: 'Güven', context: 'Tur içi konum' }},
            en: {{ title: 'Live decision console', subtitle: 'Real-time energy recommendation for the race engineer', soc: 'Energy store', temp: 'Battery', risk: 'Potential clipping risk', next: 'Next straight', speed: 'Speed', deploy: 'Deploy', regen: 'Regen', aero: 'Aero', segment: 'Segment', confidence: 'Confidence', context: 'Lap position' }}
          }};
          let index = 0;
          let timer = null;
          let language = document.documentElement.lang === 'en' ? 'en' : 'tr';
          const seek = document.getElementById('reo-live-seek');
          seek.max = String(Math.max(feed.length - 1, 0));
          const localize = () => {{
            const copy = labels[language];
            document.getElementById('reo-live-title').textContent = copy.title;
            document.getElementById('reo-live-subtitle').textContent = copy.subtitle;
            document.getElementById('reo-live-soc-label').textContent = copy.soc;
            document.getElementById('reo-live-temp-label').textContent = copy.temp;
            document.getElementById('reo-live-risk-label').textContent = copy.risk;
            document.getElementById('reo-live-next-label').textContent = copy.next;
            document.getElementById('reo-live-speed-label').textContent = copy.speed;
            document.getElementById('reo-live-deploy-label').textContent = copy.deploy;
            document.getElementById('reo-live-regen-label').textContent = copy.regen;
            document.getElementById('reo-live-aero-label').textContent = copy.aero;
            document.getElementById('reo-live-segment-label').textContent = copy.segment;
          }};
          const renderRow = row => {{
            if (!row) return;
            window.reoLiveRow = row;
            if (window.reoUpdateTelemetry) window.reoUpdateTelemetry(row);
            const copy = labels[language];
            const command = document.getElementById('reo-live-command');
            command.className = `live-command ${{row.severity}}`;
            document.getElementById('reo-live-status').textContent = row.severity.toUpperCase();
            document.getElementById('reo-live-action').textContent = row.command;
            document.getElementById('reo-live-reason').textContent = language === 'en' ? row.reason_en : row.reason_tr;
            document.getElementById('reo-live-soc').textContent = `${{row.soc_mj.toFixed(2)}} MJ`;
            document.getElementById('reo-live-temp').textContent = `${{row.battery_temp_c.toFixed(1)}} C`;
            document.getElementById('reo-live-risk').textContent = `${{Math.round(row.clipping_risk * 100)}}%`;
            document.getElementById('reo-live-next').textContent = row.next_straight_eta_s > 0 ? `${{row.next_straight_eta_s.toFixed(1)}} s` : '—';
            document.getElementById('reo-live-speed').textContent = `${{row.speed_kmh.toFixed(0)}} km/h`;
            document.getElementById('reo-live-deploy').textContent = `${{row.deploy_kw.toFixed(1)}} kW`;
            document.getElementById('reo-live-regen').textContent = `${{row.regen_kw.toFixed(1)}} kW`;
            document.getElementById('reo-live-aero').textContent = row.aero_mode;
            document.getElementById('reo-live-segment').textContent = row.segment_type;
            document.getElementById('reo-live-context').textContent = `${{copy.context}}: ${{row.time_s.toFixed(1)}} s · ${{row.distance_m.toFixed(0)}} m · ${{row.segment_type}}`;
            document.getElementById('reo-live-confidence').textContent = `${{copy.confidence}}: ${{row.confidence_pct.toFixed(0)}}%`;
            document.getElementById('reo-live-clock').textContent = `${{row.time_s.toFixed(1)}} s`;
            seek.value = String(index);
          }};
          const render = () => renderRow(feed[index]);
          const syncApi = async () => {{
            try {{
              const response = await fetch(`${{window.reoApiBase}}/api/decision?index=${{index}}${{selectedQuery}}`, {{ cache: 'no-store' }});
              if (!response.ok) throw new Error('API unavailable');
              const payload = await response.json();
              seek.max = String(Math.max(Number(payload.total) - 1, 0));
              index = Math.min(index, Number(payload.total) - 1);
              renderRow(payload.decision);
              document.getElementById('reo-live-source').textContent = 'API LIVE';
            }} catch (error) {{
              document.getElementById('reo-live-source').textContent = 'SYNTHETIC REPLAY';
              render();
            }}
          }};
          const play = () => {{
            if (timer || feed.length < 2) return;
            timer = window.setInterval(() => {{ index = (index + 1) % feed.length; syncApi(); }}, 120);
          }};
          const pause = () => {{ if (timer) {{ window.clearInterval(timer); timer = null; }} }};
          document.getElementById('reo-live-play').addEventListener('click', play);
          document.getElementById('reo-live-pause').addEventListener('click', pause);
          seek.addEventListener('input', () => {{ index = Number(seek.value); syncApi(); }});
          window.addEventListener('reo-language-change', event => {{ language = event.detail; localize(); render(); }});
          localize();
          render();
          syncApi();
        }})();
      </script>
"""


def _data_explorer_panel(fixed_trace: pd.DataFrame, predictive_trace: pd.DataFrame) -> str:
    columns = [
        "time_s",
        "distance_m",
        "segment_type",
        "driver_command",
        "deploy_kw",
        "regen_kw",
        "soc_mj",
        "battery_temp_c",
        "clipping_risk",
        "clipping",
        "thermal_limited",
    ]
    records = []
    for strategy, trace in (("fixed_map", fixed_trace), ("predictive_mpc", predictive_trace)):
        frame = trace[columns].copy()
        frame["strategy"] = strategy
        records.extend(frame.to_dict(orient="records"))
    payload = json.dumps(records, ensure_ascii=True, allow_nan=False)
    return f"""
      <details class="advanced-section">
        <summary data-i18n="rawDataTitle">Ham telemetriyi incele</summary>
        <div class="panel data-explorer">
        <div class="explorer-heading">
          <div>
        <h2 data-i18n="rawDataHeading">Telemetry Data Explorer</h2>
            <p data-i18n="rawDataCopy">Ham karar akışının tamamı bu panelde. Dosya açmadan strateji, risk ve komut bazında incele.</p>
          </div>
          <span class="pill" id="reo-row-count">0 kayıt</span>
        </div>
        <div class="explorer-controls">
          <label><span data-i18n="strategyFilter">Strateji</span>
            <select id="reo-strategy-filter">
              <option value="all" data-i18n="allOption">Tümü</option>
              <option value="predictive_mpc">Orchestrator</option>
              <option value="fixed_map" data-i18n="fixedOption">Sabit harita</option>
            </select>
          </label>
          <label><span data-i18n="searchFilter">Arama</span>
            <input id="reo-text-filter" type="search" placeholder="komut, segment veya değer ara">
          </label>
          <label class="check-label"><input id="reo-clipping-filter" type="checkbox"> <span data-i18n="incidentFilter">Clipping / termal limit</span></label>
          <button id="reo-reset-filter" type="button" data-i18n="clearFilters">Filtreleri temizle</button>
        </div>
        <div class="explorer-table-wrap">
          <table>
            <thead><tr><th data-i18n="explorerStrategyHeader">Strateji</th><th data-i18n="explorerTimeHeader">Zaman</th><th data-i18n="explorerDistanceHeader">Mesafe</th><th data-i18n="explorerSegmentHeader">Segment</th><th data-i18n="explorerCommandHeader">Komut</th><th>Deploy</th><th>Regen</th><th>SoC</th><th data-i18n="explorerBatteryHeader">Batarya</th><th data-i18n="explorerRiskHeader">Risk</th><th data-i18n="explorerStatusHeader">Durum</th></tr></thead>
            <tbody id="reo-data-body"></tbody>
          </table>
        </div>
        <div class="explorer-footer">
          <span id="reo-page-label">Sayfa 1</span>
          <div class="explorer-pages"><button id="reo-prev-page" type="button" data-i18n="previous">Önceki</button><button id="reo-next-page" type="button" data-i18n="next">Sonraki</button></div>
        </div>
        </div>
      </details>
      <script>
        (() => {{
          let allRows = {payload};
          window.reoApiBase = document.documentElement.dataset.apiBase || new URLSearchParams(window.location.search).get('api_base') || '';
          const pageSize = 18;
          const explorerCopy = {{
            tr: {{ fixed: 'Sabit', statusNormal: 'NORMAL', statusClipping: 'CLIPPING', statusThermal: 'TERMAL LİMİT', noResults: 'Filtreye uyan kayıt yok.', rows: 'kayıt', page: 'Sayfa' }},
            en: {{ fixed: 'Fixed', statusNormal: 'NORMAL', statusClipping: 'CLIPPING', statusThermal: 'THERMAL LIMIT', noResults: 'No records match the filters.', rows: 'records', page: 'Page' }}
          }};
          let page = 0;
          const strategy = document.getElementById('reo-strategy-filter');
          const text = document.getElementById('reo-text-filter');
          const incidents = document.getElementById('reo-clipping-filter');
          const body = document.getElementById('reo-data-body');
          const count = document.getElementById('reo-row-count');
          const pageLabel = document.getElementById('reo-page-label');
          const esc = value => String(value).replace(/[&<>\"']/g, char => ({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}}[char]));
          const filteredRows = () => {{
            const query = text.value.trim().toLowerCase();
            return allRows.filter(row => {{
              const matchStrategy = strategy.value === 'all' || row.strategy === strategy.value;
              const matchQuery = !query || Object.values(row).some(value => String(value).toLowerCase().includes(query));
              const matchIncident = !incidents.checked || row.clipping || row.thermal_limited;
              return matchStrategy && matchQuery && matchIncident;
            }});
          }};
          const render = () => {{
            const rows = filteredRows();
            const copy = explorerCopy[document.documentElement.lang === 'en' ? 'en' : 'tr'];
            const pageCount = Math.max(1, Math.ceil(rows.length / pageSize));
            page = Math.min(page, pageCount - 1);
            const visible = rows.slice(page * pageSize, (page + 1) * pageSize);
            body.innerHTML = visible.map(row => {{
              const incident = row.clipping || row.thermal_limited;
              const status = row.clipping ? copy.statusClipping : row.thermal_limited ? copy.statusThermal : copy.statusNormal;
              return `<tr class="${{incident ? 'incident-row' : ''}}"><td>${{row.strategy === 'predictive_mpc' ? 'Orchestrator' : copy.fixed}}</td><td>${{Number(row.time_s).toFixed(1)}}s</td><td>${{Number(row.distance_m).toFixed(0)}}m</td><td>${{esc(row.segment_type)}}</td><td>${{esc(row.driver_command)}}</td><td>${{Number(row.deploy_kw).toFixed(1)}} kW</td><td>${{Number(row.regen_kw).toFixed(1)}} kW</td><td>${{Number(row.soc_mj).toFixed(2)}} MJ</td><td>${{Number(row.battery_temp_c).toFixed(1)}} C</td><td>${{Number(row.clipping_risk).toFixed(2)}}</td><td>${{status}}</td></tr>`;
            }}).join('') || `<tr><td colspan="11">${{copy.noResults}}</td></tr>`;
            count.textContent = `${{rows.length}} ${{copy.rows}}`;
            pageLabel.textContent = `${{copy.page}} ${{page + 1}} / ${{pageCount}}`;
            document.getElementById('reo-prev-page').disabled = page === 0;
            document.getElementById('reo-next-page').disabled = page >= pageCount - 1;
          }};
          [strategy, text, incidents].forEach(control => control.addEventListener('input', () => {{ page = 0; render(); }}));
          document.getElementById('reo-reset-filter').addEventListener('click', () => {{ strategy.value = 'all'; text.value = ''; incidents.checked = false; page = 0; render(); }});
          document.getElementById('reo-prev-page').addEventListener('click', () => {{ page -= 1; render(); }});
          document.getElementById('reo-next-page').addEventListener('click', () => {{ page += 1; render(); }});
          window.addEventListener('reo-language-change', render);
          render();
          window.reoExplorerReload = async selectedQuery => {{
            try {{
              const response = await fetch(`${{window.reoApiBase}}/api/explorer?${{selectedQuery}}`, {{ cache: 'no-store' }});
              if (!response.ok) throw new Error('Explorer API unavailable');
              const data = await response.json();
              allRows = data.rows || [];
              page = 0;
              render();
            }} catch (error) {{
              console.warn('Explorer API unavailable; keeping embedded snapshot.', error);
            }}
          }};
        }})();
      </script>
"""


def _kpi_cards(metrics: pd.DataFrame, predictive_trace: pd.DataFrame, config: EnergyConfig) -> str:
    fixed = _metric(metrics, "fixed_map")
    predictive = _metric(metrics, "predictive_mpc")
    lap_delta = fixed["lap_time_proxy_s"] - predictive["lap_time_proxy_s"]
    clipping_delta = fixed["clipping_duration_s"] - predictive["clipping_duration_s"]
    soc_pct = (
        (predictive["end_soc_mj"] - config.minimum_soc_mj)
        / max(config.usable_energy_mj - config.minimum_soc_mj, 1e-6)
        * 100.0
    )
    regen_count = int((predictive_trace["driver_command"] == "REGEN PRIORITY").sum())
    return f"""
          <div class="metric"><span data-i18n="lapImprovement">Tur süresi iyileşmesi</span><b id="reo-kpi-lap">{lap_delta:.3f}s</b><small data-i18n="vsFixed">Sabit haritaya göre</small></div>
          <div class="metric"><span data-i18n="clippingReduction">Clipping azalması</span><b id="reo-kpi-clipping">{clipping_delta:.1f}s</b><small data-i18n="orchestratorStrategy">Orchestrator stratejisi</small></div>
          <div class="metric"><span data-i18n="finalSoc">Final SoC</span><b id="reo-kpi-soc">{soc_pct:.1f}%</b><small id="reo-kpi-soc-detail">{predictive["end_soc_mj"]:.3f} MJ</small></div>
          <div class="metric"><span data-i18n="regenEvents">Regen olayları</span><b id="reo-kpi-regen">{regen_count}</b><small data-i18n="regenPoints">Regen karar noktası</small></div>
"""


def _orchestrator_insights(metrics: pd.DataFrame, predictive_trace: pd.DataFrame, config: EnergyConfig) -> str:
    fixed = _metric(metrics, "fixed_map")
    predictive = _metric(metrics, "predictive_mpc")
    lap_delta = fixed["lap_time_proxy_s"] - predictive["lap_time_proxy_s"]
    clipping_delta = fixed["clipping_duration_s"] - predictive["clipping_duration_s"]
    thermal_headroom = config.battery_soft_limit_c - predictive["max_battery_temp_c"]
    command_counts = predictive_trace["driver_command"].value_counts()
    top_command = str(command_counts.index[0]) if not command_counts.empty else "ENERGY HOLD"
    top_command_share = float(command_counts.iloc[0] / max(len(predictive_trace), 1) * 100.0) if not command_counts.empty else 0.0
    risk_state = "Kontrol altında" if predictive["clipping_duration_s"] <= 0.05 else "Risk izlenmeli"
    return f"""
      <div class="insight-grid" id="reo-insights">
        <div class="insight">
          <span data-i18n="orchestrationGain">Orkestrasyon kazancı</span>
          <b>{lap_delta:.3f}s</b>
          <p data-i18n="lapGainCopy">Sabit haritaya karşı tur süresi iyileşmesi.</p>
        </div>
        <div class="insight">
          <span data-i18n="clippingControl">Clipping kontrolü</span>
          <b>{risk_state}</b>
          <p data-i18n-tr="{clipping_delta:.2f}s clipping süresi azaltıldı." data-i18n-en="{clipping_delta:.2f}s of clipping time reduced.">{clipping_delta:.2f}s clipping süresi azaltıldı.</p>
        </div>
        <div class="insight">
          <span data-i18n="energyUse">Deploy yoğunluğu</span>
          <b>{predictive["deploy_intensity_pct"]:.1f}%</b>
          <p>{predictive["total_deploy_mj"]:.2f} MJ deploy, {predictive["total_regen_mj"]:.2f} MJ regen.</p>
        </div>
        <div class="insight">
          <span data-i18n="decisionMode">Karar modu</span>
          <b>{escape(top_command)}</b>
          <p data-i18n="dominantCommand">Tur örneklerinin {top_command_share:.1f}% bölümünde baskın komut.</p>
        </div>
        <div class="insight">
          <span data-i18n="thermalHeadroom">Termal pay</span>
          <b>{thermal_headroom:.1f}C</b>
          <p data-i18n="thermalHeadroomCopy">Yumuşak limite göre kalan batarya sıcaklık alanı.</p>
        </div>
        <div class="insight">
          <span data-i18n="controlScore">Kontrol skoru</span>
          <b>{predictive["clipping_control_score"]:.1f}</b>
          <p data-i18n="controlScoreCopy">Clipping ve termal limit sürelerinden türetilen karar kalitesi.</p>
        </div>
        <div class="insight">
          <span data-i18n="lookahead">Lookahead</span>
          <b>{config.horizon_s:.0f}s</b>
          <p data-i18n="lookaheadCopy">Yaklaşan uzun düzlükler için enerji rezerv ufku.</p>
        </div>
        <div class="insight">
          <span data-i18n="finalSoc">Final SoC</span>
          <b>{predictive["end_soc_mj"]:.2f} MJ</b>
          <p data-i18n-tr="Hedef finish rezervi {config.target_finish_soc_mj:.2f} MJ." data-i18n-en="Target finish reserve: {config.target_finish_soc_mj:.2f} MJ.">Hedef finish rezervi {config.target_finish_soc_mj:.2f} MJ.</p>
        </div>
      </div>
"""


def _track_ribbon(frame: pd.DataFrame) -> str:
    colors = {
        "straight": "#245f9f",
        "acceleration": "#2f7d4f",
        "braking": "#b5121b",
        "slow_corner": "#bf7a00",
        "fast_corner": "#007a7a",
    }
    labels = {
        "straight": "Düzlük",
        "acceleration": "Hızlanma",
        "braking": "Fren",
        "slow_corner": "Yavaş viraj",
        "fast_corner": "Hızlı viraj",
    }
    total = max(float(frame["ds_m"].sum()), 1.0)
    chunks = []
    token = frame["segment_type"].ne(frame["segment_type"].shift()).cumsum()
    for _, group in frame.groupby(token):
        segment = str(group["segment_type"].iloc[0])
        width = float(group["ds_m"].sum()) / total * 100.0
        chunks.append(
            f'<span title="{escape(labels.get(segment, segment))}: {group["ds_m"].sum():.0f} m" '
            f'style="width:{width:.3f}%; background:{colors.get(segment, "#66717d")};"></span>'
        )
    legend = "".join(
        f'<span><i style="background:{color}"></i>{escape(labels[key])}</span>' for key, color in colors.items()
    )
    return f'<div class="track-shell"><div class="track" id="reo-track-ribbon">{"".join(chunks)}</div><i class="track-marker" id="reo-track-marker" style="left:0%"></i></div><div class="legend">{legend}</div>'


def _command_timeline(trace: pd.DataFrame) -> str:
    changes = trace[trace["driver_command"].ne(trace["driver_command"].shift())].copy()
    changes = changes[["time_s", "distance_m", "driver_command", "clipping_risk", "soc_mj"]].head(22)
    cards = []
    for _, row in changes.iterrows():
        cards.append(
            f"""
            <div class="command">
              <time>{row["time_s"]:.1f}s<br>{row["distance_m"]:.0f}m</time>
              <div>
                <span class="pill">{escape(str(row["driver_command"]))}</span>
                <b>Risk {row["clipping_risk"]:.2f} | SoC {row["soc_mj"]:.2f} MJ</b>
              </div>
            </div>
"""
        )
    return f'<div class="command-list" id="reo-command-timeline">{"".join(cards)}</div>'


def _format_metrics(metrics: pd.DataFrame) -> str:
    columns = [
        "strategy",
        "lap_time_proxy_s",
        "clipping_duration_s",
        "clipping_loss_proxy_s",
        "thermal_limited_duration_s",
        "max_speed_loss_kmh",
        "end_soc_mj",
        "unused_energy_mj",
        "max_battery_temp_c",
        "total_deploy_mj",
        "total_regen_mj",
        "deploy_intensity_pct",
        "clipping_control_score",
    ]
    labels = {
        "strategy": "Strateji",
        "lap_time_proxy_s": "Lap proxy (s)",
        "clipping_duration_s": "Clipping (s)",
        "clipping_loss_proxy_s": "Clipping zaman etkisi (proxy s)",
        "thermal_limited_duration_s": "Termal limit (s)",
        "max_speed_loss_kmh": "Maksimum hız kaybı",
        "end_soc_mj": "Final SoC",
        "unused_energy_mj": "Kalan enerji",
        "max_battery_temp_c": "Max batarya C",
        "total_deploy_mj": "Deploy MJ",
        "total_regen_mj": "Regen MJ",
        "deploy_intensity_pct": "Deploy yoğunluğu %",
        "clipping_control_score": "Kontrol skoru",
    }
    i18n_keys = {
        "strategy": "tableStrategy", "lap_time_proxy_s": "tableLapProxy", "clipping_duration_s": "tableClipping",
        "clipping_loss_proxy_s": "tableClippingLoss", "thermal_limited_duration_s": "tableThermal", "max_speed_loss_kmh": "tableSpeedLoss",
        "end_soc_mj": "tableEndSoc", "unused_energy_mj": "tableUnused", "max_battery_temp_c": "tableMaxTemp", "total_deploy_mj": "tableDeploy",
        "total_regen_mj": "tableRegen", "deploy_intensity_pct": "tableIntensity", "clipping_control_score": "tableScore",
    }
    table = metrics[columns].copy()
    table["strategy"] = table["strategy"].replace(
        {"fixed_map": "Sabit harita", "predictive_mpc": "Orchestrator"}
    )
    numeric_cols = table.select_dtypes("number").columns
    table[numeric_cols] = table[numeric_cols].round(3)
    table = table.rename(columns=labels)
    headers = "".join(f"<th data-i18n=\"{i18n_keys.get(column, '')}\">{escape(str(labels[column]))}</th>" for column in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(str(value))}</td>" for value in row) + "</tr>"
        for row in table.itertuples(index=False, name=None)
    )
    return f'<div class="table-scroll"><table id="reo-metrics-table"><thead><tr>{headers}</tr></thead><tbody id="reo-metrics-body">{body}</tbody></table></div>'


def _segment_summary(frame: pd.DataFrame) -> str:
    grouped = (
        frame.groupby(["segment_type", "aero_mode"], as_index=False)
        .agg(distance_m=("ds_m", "sum"), duration_s=("dt_s", "sum"), mean_speed_kmh=("speed_kmh", "mean"))
        .sort_values(["segment_type", "aero_mode"])
    )
    grouped[["distance_m", "duration_s", "mean_speed_kmh"]] = grouped[
        ["distance_m", "duration_s", "mean_speed_kmh"]
    ].round(2)
    grouped = grouped.rename(
        columns={
            "segment_type": "Segment",
            "aero_mode": "Aero",
            "distance_m": "Mesafe",
            "duration_s": "Süre",
            "mean_speed_kmh": "Ort. hız",
        }
    )
    header_keys = {"Segment": "segmentHeader", "Aero": "aeroHeader", "Mesafe": "distanceHeader", "Süre": "durationHeader", "Ort. hız": "avgSpeedHeader"}
    headers = "".join(f"<th data-i18n=\"{header_keys.get(column, '')}\">{escape(str(column))}</th>" for column in grouped.columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(str(value))}</td>" for value in row) + "</tr>"
        for row in grouped.itertuples(index=False, name=None)
    )
    return f'<div class="table-scroll"><table id="reo-segment-table"><thead><tr>{headers}</tr></thead><tbody id="reo-segment-body">{body}</tbody></table></div>'


def _metric(metrics: pd.DataFrame, strategy: str) -> pd.Series:
    return metrics[metrics["strategy"] == strategy].iloc[0]
