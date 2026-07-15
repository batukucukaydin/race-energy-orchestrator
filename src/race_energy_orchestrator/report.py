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
    plot_html = fig.to_html(full_html=False, include_plotlyjs="inline", config={"responsive": True})
    notes_html = "".join(f"<li>{escape(note)}</li>" for note in lap_data.notes) or "<li>Fallback notu yok.</li>"

    html = f"""<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Race Energy Orchestrator Dashboard</title>
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
      .shell, .hero, .grid {{ grid-template-columns: 1fr; }}
      aside {{ position: relative; min-height: auto; top: 0; }}
      .hero-main {{ min-height: 300px; }}
      .shell, .content, .hero, .grid, .panel {{ width: 100%; max-width: 100%; }}
    }}
    @media (max-width: 680px) {{
      main {{ width: min(100vw - 20px, 1440px); padding-top: 10px; }}
      .hero-metrics {{ grid-template-columns: 1fr; }}
      .insight-grid {{ grid-template-columns: 1fr; }}
      .metric {{ min-height: 104px; }}
      .command {{ grid-template-columns: 1fr; }}
      .hero-main {{ min-height: 260px; padding: 26px 18px; }}
      h1 {{ max-width: min(320px, calc(100vw - 76px)); font-size: 34px; line-height: 1.02; }}
      .hero-main p, aside p {{ max-width: min(280px, calc(100vw - 96px)); font-size: 14px; }}
      .panel {{ overflow-x: auto; }}
    }}
  </style>
</head>
<body>
<main>
  <div class="shell">
    <aside>
      <div class="brand">
        <div class="mark">REO</div>
        <b>Race Energy Orchestrator</b>
        <span>Predictive race energy control</span>
      </div>
      {_side_summary(lap_data, metrics, predictive_trace)}
      <div class="side-block">
        <span class="side-label">Veri kaynagi</span>
        <span class="side-value">{escape(lap_data.source)}</span>
        <p>{escape(lap_data.source_detail)}</p>
      </div>
    </aside>
    <section class="content">
      <div class="hero">
        <div class="hero-main">
          <span class="eyebrow">Race Energy Orchestrator</span>
          <h1>Enerji kararlarini clipping olusmadan orkestre et.</h1>
          <p>Dashboard, sabit enerji haritasi ile ongorulu orkestrasyon stratejisini ayni tur uzerinde karsilastirir. FastF1 verisi yoksa deterministik sentetik tur kullanilir; batarya, termal, aktif aero ve ERS sinyalleri genel model varsayimidir.</p>
        </div>
        <div class="hero-metrics">
          {_kpi_cards(metrics, predictive_trace)}
        </div>
      </div>

      <div class="panel">
        <h2>Orchestrator Insight</h2>
        {_orchestrator_insights(metrics, predictive_trace, config)}
      </div>

      <div class="panel">
        <h2>Pist Enerji Seridi</h2>
        {_track_ribbon(base_frame)}
      </div>

      <div class="grid">
        <div class="panel plot-panel">
          <h2>Strateji Telemetrisi</h2>
          {plot_html}
        </div>
        <div class="panel">
          <h2>Surucu Komut Akisi</h2>
          {_command_timeline(predictive_trace)}
        </div>
      </div>

      <div class="grid">
        <div class="panel">
          <h2>Strateji Karsilastirmasi</h2>
          {_format_metrics(metrics)}
        </div>
        <div class="panel">
          <h2>Segment Ozeti</h2>
          {_segment_summary(base_frame)}
        </div>
      </div>

      <div class="panel">
        <h2>Varsayimlar ve Veri Sozlesmesi</h2>
        <p>Bu prototip takim ozel telemetri veya gercek arac parametresi kullanmaz. Varsayimlar genel hibrit yaris araci enerji yonetimi modelini gostermek icindir.</p>
        <p>Senaryo: ortam {config.ambient_temp_c:.1f}C, baslangic SoC {config.initial_soc_mj:.2f} MJ, baslangic batarya {config.initial_battery_temp_c:.1f}C, lookahead {config.horizon_s:.1f}s.</p>
        <p>Girdi kolonlari: {", ".join(f"<code>{col}</code>" for col in REQUIRED_INPUT_COLUMNS)}</p>
        <p>Model kolonlari: {", ".join(f"<code>{col}</code>" for col in MODEL_COLUMNS)}</p>
        <ul>{notes_html}</ul>
        <p><a href="{config.reference_links[0]}">FIA Formula One regulations category</a> | <a href="{config.reference_links[1]}">FIA 2026 Technical Regulations Section C, Issue 18 PDF</a></p>
      </div>
    </section>
  </div>
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
        rows=5,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        subplot_titles=(
            "Hiz ve aktif aero",
            "Deploy / recharge",
            "Energy Store SoC",
            "Clipping riski",
            "Batarya sicakligi",
        ),
    )

    x = predictive_trace["distance_m"]
    aero_numeric = predictive_trace["aero_mode"].map({"Z_MODE": 0, "X_MODE": 1})
    fig.add_trace(go.Scatter(x=x, y=predictive_trace["speed_kmh"], name="Hiz km/h", line=dict(color="#245f9f", width=2)), row=1, col=1)
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


def _side_summary(lap_data: LapData, metrics: pd.DataFrame, predictive_trace: pd.DataFrame) -> str:
    fixed = _metric(metrics, "fixed_map")
    predictive = _metric(metrics, "predictive_mpc")
    lap_delta = fixed["lap_time_proxy_s"] - predictive["lap_time_proxy_s"]
    risk_peak = predictive_trace["clipping_risk"].max()
    return f"""
      <div class="side-block">
        <span class="side-label">Lap proxy kazanci</span>
        <span class="side-value">{lap_delta:.3f} s</span>
      </div>
      <div class="side-block">
        <span class="side-label">Orchestrator clipping</span>
        <span class="side-value">{predictive["clipping_duration_s"]:.3f} s</span>
      </div>
      <div class="side-block">
        <span class="side-label">Peak risk</span>
        <span class="side-value">{risk_peak:.2f}</span>
      </div>
"""


def _kpi_cards(metrics: pd.DataFrame, predictive_trace: pd.DataFrame) -> str:
    fixed = _metric(metrics, "fixed_map")
    predictive = _metric(metrics, "predictive_mpc")
    lap_delta = fixed["lap_time_proxy_s"] - predictive["lap_time_proxy_s"]
    clipping_delta = fixed["clipping_duration_s"] - predictive["clipping_duration_s"]
    soc_pct = predictive["end_soc_mj"] / 4.0 * 100.0
    attack_count = int(predictive_trace["driver_command"].isin(["DEPLOY ATTACK", "OVERTAKE READY"]).sum())
    return f"""
          <div class="metric"><span>Lap proxy iyilesme</span><b>{lap_delta:.3f}s</b><small>Sabit haritaya gore</small></div>
          <div class="metric"><span>Clipping azalimi</span><b>{clipping_delta:.1f}s</b><small>Orchestrator stratejisi</small></div>
          <div class="metric"><span>Final SoC</span><b>{soc_pct:.1f}%</b><small>{predictive["end_soc_mj"]:.3f} MJ</small></div>
          <div class="metric"><span>Atak hazirligi</span><b>{attack_count}</b><small>Deploy komut noktasi</small></div>
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
    risk_state = "Kontrol altinda" if predictive["clipping_duration_s"] <= 0.05 else "Risk izlenmeli"
    return f"""
      <div class="insight-grid">
        <div class="insight">
          <span>Orkestrasyon kazanci</span>
          <b>{lap_delta:.3f}s</b>
          <p>Sabit haritaya karsi lap proxy iyilesmesi.</p>
        </div>
        <div class="insight">
          <span>Clipping kontrolu</span>
          <b>{risk_state}</b>
          <p>{clipping_delta:.2f}s clipping suresi temizlendi.</p>
        </div>
        <div class="insight">
          <span>Enerji kullanimi</span>
          <b>{predictive["energy_utilization_pct"]:.1f}%</b>
          <p>{predictive["total_deploy_mj"]:.2f} MJ deploy, {predictive["total_regen_mj"]:.2f} MJ regen.</p>
        </div>
        <div class="insight">
          <span>Karar modu</span>
          <b>{escape(top_command)}</b>
          <p>Tur orneklerinin {top_command_share:.1f}% bolumunde baskin komut.</p>
        </div>
        <div class="insight">
          <span>Termal pay</span>
          <b>{thermal_headroom:.1f}C</b>
          <p>Soft limite gore kalan batarya sicaklik alani.</p>
        </div>
        <div class="insight">
          <span>Kontrol skoru</span>
          <b>{predictive["clipping_control_score"]:.1f}</b>
          <p>Clipping ve termal limit surelerinden turetilen karar kalitesi.</p>
        </div>
        <div class="insight">
          <span>Lookahead</span>
          <b>{config.horizon_s:.0f}s</b>
          <p>Yaklasan uzun duzlukler icin enerji rezerv ufku.</p>
        </div>
        <div class="insight">
          <span>Final SoC</span>
          <b>{predictive["end_soc_mj"]:.2f} MJ</b>
          <p>Hedef finish rezervi {config.target_finish_soc_mj:.2f} MJ.</p>
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
        "straight": "Duzluk",
        "acceleration": "Hizlanma",
        "braking": "Fren",
        "slow_corner": "Yavas viraj",
        "fast_corner": "Hizli viraj",
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
    return f'<div class="track">{"".join(chunks)}</div><div class="legend">{legend}</div>'


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
    return f'<div class="command-list">{"".join(cards)}</div>'


def _format_metrics(metrics: pd.DataFrame) -> str:
    columns = [
        "strategy",
        "lap_time_proxy_s",
        "clipping_duration_s",
        "thermal_limited_duration_s",
        "max_speed_loss_kmh",
        "end_soc_mj",
        "unused_energy_mj",
        "max_battery_temp_c",
        "total_deploy_mj",
        "total_regen_mj",
        "energy_utilization_pct",
        "clipping_control_score",
    ]
    labels = {
        "strategy": "Strateji",
        "lap_time_proxy_s": "Lap proxy (s)",
        "clipping_duration_s": "Clipping (s)",
        "thermal_limited_duration_s": "Termal limit (s)",
        "max_speed_loss_kmh": "Max hiz kaybi",
        "end_soc_mj": "Final SoC",
        "unused_energy_mj": "Kalan enerji",
        "max_battery_temp_c": "Max batarya C",
        "total_deploy_mj": "Deploy MJ",
        "total_regen_mj": "Regen MJ",
        "energy_utilization_pct": "Enerji kull. %",
        "clipping_control_score": "Kontrol skoru",
    }
    table = metrics[columns].copy()
    table["strategy"] = table["strategy"].replace(
        {"fixed_map": "Sabit harita", "predictive_mpc": "Orchestrator"}
    )
    numeric_cols = table.select_dtypes("number").columns
    table[numeric_cols] = table[numeric_cols].round(3)
    table = table.rename(columns=labels)
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
    grouped = grouped.rename(
        columns={
            "segment_type": "Segment",
            "aero_mode": "Aero",
            "distance_m": "Mesafe",
            "duration_s": "Sure",
            "mean_speed_kmh": "Ort hiz",
        }
    )
    return grouped.to_html(index=False, escape=True)


def _metric(metrics: pd.DataFrame, strategy: str) -> pd.Series:
    return metrics[metrics["strategy"] == strategy].iloc[0]
