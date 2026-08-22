from __future__ import annotations

from html import escape
from pathlib import Path

import pandas as pd

from .config import EnergyConfig, MODEL_COLUMNS, REQUIRED_INPUT_COLUMNS
from .data import LapData
from .report import _data_explorer_panel


def render_support_pages(
    output_dir: str | Path,
    lap_data: LapData,
    fixed_trace: pd.DataFrame,
    predictive_trace: pd.DataFrame,
    config: EnergyConfig,
) -> tuple[Path, Path]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    explorer = directory / "explorer.html"
    guide = directory / "guide.html"
    explorer.write_text(_explorer_html(fixed_trace, predictive_trace), encoding="utf-8")
    guide.write_text(_guide_html(lap_data, config), encoding="utf-8")
    return explorer, guide


def _shell(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)} | Race Energy Orchestrator</title>
  <style>
    :root {{ --bg:#f3f5f2; --surface:#fff; --ink:#14171c; --muted:#66717d; --line:#d9ded8; --red:#b5121b; --red-deep:#7f0c14; --shadow:0 14px 34px rgba(24,29,35,.08); }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--ink); background:var(--bg); font-family:"Avenir Next","Segoe UI",sans-serif; }}
    main {{ width:min(1380px,calc(100vw - 32px)); margin:auto; padding:24px 0 48px; }}
    header {{ display:flex; justify-content:space-between; align-items:center; gap:16px; margin-bottom:20px; }}
    header strong {{ font-size:15px; }}
    nav {{ display:flex; flex-wrap:wrap; gap:6px; }}
    nav a {{ padding:7px 10px; border:1px solid var(--line); border-radius:5px; background:#fff; color:var(--ink); font-size:12px; font-weight:800; text-decoration:none; }}
    nav a.active {{ border-color:var(--red); color:var(--red-deep); }}
    .hero, .panel, details {{ border:1px solid var(--line); border-radius:8px; background:var(--surface); box-shadow:var(--shadow); }}
    .hero {{ padding:22px; margin-bottom:16px; }}
    h1 {{ margin:0 0 7px; font-size:clamp(28px,4vw,48px); }}
    h2 {{ margin:0 0 10px; font-size:20px; }}
    h3 {{ margin:0 0 7px; font-size:15px; }}
    p, li {{ color:var(--muted); line-height:1.55; }}
    .panel {{ padding:18px; margin-bottom:16px; }}
    .grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }}
    .contract {{ width:100%; border-collapse:collapse; font-size:13px; }}
    .contract th, .contract td {{ padding:9px 8px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }}
    .contract th {{ background:#f4f6f5; }}
    code {{ padding:1px 4px; border-radius:4px; background:#eef2f1; }}
    .explorer-heading {{ display:flex; justify-content:space-between; gap:12px; align-items:center; }}
    .data-explorer {{ border:0; box-shadow:none; padding:0; }}
    .advanced-section {{ padding:18px; }}
    .advanced-section > summary {{ cursor:pointer; font-size:20px; font-weight:800; list-style:none; }}
    .explorer-controls {{ display:flex; flex-wrap:wrap; gap:10px; align-items:end; margin:15px 0; }}
    .explorer-controls label {{ display:grid; gap:5px; color:var(--muted); font-size:11px; font-weight:800; text-transform:uppercase; }}
    .explorer-controls select, .explorer-controls input, .explorer-controls button {{ min-height:34px; padding:6px 8px; border:1px solid var(--line); border-radius:5px; background:#fff; font:inherit; }}
    .explorer-controls button {{ cursor:pointer; font-weight:800; }}
    .explorer-table-wrap {{ overflow:auto; }}
    table {{ width:100%; border-collapse:collapse; font-size:12px; min-width:900px; }}
    th, td {{ padding:8px 7px; border-bottom:1px solid var(--line); text-align:right; white-space:nowrap; }}
    th:first-child, td:first-child {{ text-align:left; }}
    .explorer-footer {{ display:flex; justify-content:space-between; gap:12px; margin-top:12px; color:var(--muted); font-size:12px; }}
    @media (max-width:760px) {{ main {{ width:min(100vw - 20px,1380px); }} header, .grid {{ display:block; }} nav {{ margin-top:12px; }} .panel {{ overflow:hidden; }} }}
  </style>
</head>
<body><main>
  <header><strong>REO / Race Energy Orchestrator</strong><nav><a href="index.html">Dashboard</a><a class="{'active' if title.startswith('Telemetry') else ''}" href="explorer.html">Telemetry</a><a class="{'active' if title.startswith('Guide') else ''}" href="guide.html">Guide &amp; Contract</a></nav></header>
  {body}
</main></body></html>"""


def _explorer_html(fixed_trace: pd.DataFrame, predictive_trace: pd.DataFrame) -> str:
    explorer = _data_explorer_panel(fixed_trace, predictive_trace).replace(
        '<details class="advanced-section">', '<details class="advanced-section" open>', 1
    )
    body = f"""
      <section class="hero"><h1>Telemetry Explorer</h1><p>Telemetri Explorer / Ham karar kayıtlarını strateji, risk, segment ve komut bazında incele.</p></section>
      {explorer}
    """
    return _shell("Telemetry Explorer", body)


def _guide_html(lap_data: LapData, config: EnergyConfig) -> str:
    input_rows = "".join(f"<tr><td><code>{escape(column)}</code></td><td>FastF1 veya synthetic telemetry girdisi</td></tr>" for column in REQUIRED_INPUT_COLUMNS)
    model_rows = "".join(f"<tr><td><code>{escape(column)}</code></td><td>Enerji modeli tarafından üretilen karar/telemetri alanı</td></tr>" for column in MODEL_COLUMNS)
    notes = "".join(f"<li>{escape(note)}</li>" for note in lap_data.notes) or "<li>Fallback notu yok.</li>"
    body = f"""
      <section class="hero"><h1>Guide &amp; Data Contract</h1><p>Nasıl kullanılır / Model varsayımları / Veri sözleşmesi</p></section>
      <div class="grid">
        <section class="panel"><h2>1. Nasıl kullanılır?</h2><ol><li>Önce Dashboard sayfasından yıl, pist, session ve sürücüyü seç.</li><li>Canlı karar konsolunda komut, gerekçe, SoC, sıcaklık ve clipping riskini izle.</li><li>Grafikteki kırmızı imleç aracın tur içindeki mevcut konumunu gösterir.</li><li>Ham kayıtları karşılaştırmak için Telemetry Explorer sayfasına geç.</li></ol></section>
        <section class="panel"><h2>2. Karar mantığı</h2><p>Sistem her örnekte deploy, regen veya energy hold kararı üretir.</p><ul><li><b>Deploy:</b> enerji değeri yüksek hızlanma bölgesinde güç kullan.</li><li><b>Regen:</b> frenleme enerjisini sonraki deploy fırsatı için geri kazan.</li><li><b>Thermal protect:</b> batarya sıcaklık payını koru.</li><li><b>Energy hold:</b> clipping riski veya finish rezervi nedeniyle mevcut haritayı koru.</li></ul></section>
      </div>
      <section class="panel"><h2>3. Veri kaynağı ve sınırlar</h2><p><b>Mevcut kaynak:</b> {escape(lap_data.source)}. {escape(lap_data.source_detail)}</p><p>Bu prototip takım içi gerçek araç parametrelerini kullanmaz. Enerji limitleri ve termal varsayımlar genel hibrit yarış aracı modeli içindir.</p><p>Senaryo: ortam {config.ambient_temp_c:.1f}C, başlangıç SoC {config.initial_soc_mj:.2f} MJ, başlangıç batarya {config.initial_battery_temp_c:.1f}C, lookahead {config.horizon_s:.1f}s.</p><ul>{notes}</ul></section>
      <section class="panel"><h2>4. Girdi veri sözleşmesi</h2><table class="contract"><thead><tr><th>Kolon</th><th>Anlam</th></tr></thead><tbody>{input_rows}</tbody></table></section>
      <section class="panel"><h2>5. Model çıktı sözleşmesi</h2><table class="contract"><thead><tr><th>Kolon</th><th>Anlam</th></tr></thead><tbody>{model_rows}</tbody></table></section>
      <section class="panel"><h2>6. API sözleşmesi</h2><p><code>GET /api/session</code> oturum bağlamını, <code>GET /api/metrics</code> özet KPI’ları, <code>GET /api/decision?index=n</code> canlı kararı, <code>GET /api/trace</code> seçilen grafik serilerini döndürür.</p><p><a href="http://127.0.0.1:8001/docs">FastAPI OpenAPI dokümantasyonunu aç</a></p></section>
    """
    return _shell("Guide & Data Contract", body)
