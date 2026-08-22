# Race Energy Orchestrator

Predictive hybrid race-vehicle energy management and clipping-prevention prototype. It uses public FastF1 lap telemetry when available and overlays configurable synthetic ERS, battery, thermal, active aero, and strategy signals. If FastF1 data is unavailable, it falls back to a deterministic track/session/driver-specific synthetic lap.

The project is intentionally team-neutral and vehicle-neutral. Its default configuration uses a 2026-style formula-car regulation profile as an example, not a real team, driver, or car dataset.

## Run

From this folder:

```bash
python -m race_energy_orchestrator --year 2024 --event Monza --session Q --driver LEC --output outputs/report.html
```

Offline deterministic demo:

```bash
python -m race_energy_orchestrator --synthetic-only --output outputs/report.html
```

Dashboard UI output:

```bash
python -m race_energy_orchestrator --synthetic-only --output outputs/dashboard.html
```

All telemetry, strategy decisions, filters, charts, and scenario analysis are embedded in the self-contained HTML dashboard. CSV files are not written unless an explicit output path is provided.

The dashboard begins with a synthetic live-decision replay for the race engineer. It shows the current energy recommendation, severity, reason, confidence, SoC, battery temperature, clipping risk, and time to the next high-value straight. Use the replay controls to inspect the decision stream across the lap.

Scenario run with hotter ambient conditions and a lower starting battery state:

```bash
python -m race_energy_orchestrator --synthetic-only --ambient-temp-c 34 --initial-soc-mj 2.6 --initial-battery-temp-c 52 --horizon-s 38 --output outputs/hot_scenario.html
```

Compare orchestrator behavior across baseline, hot, low-SoC, and thermal-stress scenarios:

```bash
python -m race_energy_orchestrator --synthetic-only --compare-scenarios --output outputs/scenario_dashboard.html
```

This adds the comparison table to the dashboard. To additionally export CSV data, pass `--metrics-output`, `--trace-output`, or `--comparison-output` explicitly.

Deploy-ready static output:

```bash
python -m race_energy_orchestrator --synthetic-only --output docs/index.html
python -m http.server 8000 --directory docs
```

Then open `http://localhost:8000`.

FastAPI decision backend:

```bash
python3 -m uvicorn race_energy_orchestrator.api:app --host 127.0.0.1 --port 8001
```

API endpoints:

- `GET /api/health`: service and data-source status
- `GET /api/session`: current session metadata
- `GET /api/metrics`: fixed-map and predictive-orchestrator KPI rows
- `GET /api/options`: supported years, tracks, and session types
- `GET /api/trace`: selected fixed/predictive telemetry traces for the live chart
- `GET /api/decision?index=0`: one operator decision
- `GET /api/decisions?start=0&limit=100`: paginated decision stream

The web panel uses the API for session context, KPI values, and the live decision console. The Plotly chart is a generated session snapshot; if the API is offline, the dashboard marks the embedded replay fallback instead of presenting it as live data.

Outputs:

- `outputs/report.html`: self-contained Plotly HTML report
- `docs/index.html`: static dashboard entrypoint for deployment
- Optional CSV exports are created only when `--metrics-output`, `--trace-output`, or `--comparison-output` is explicitly passed.

## Model Basis

- FIA 2026 Formula One regulations category: https://www.fia.com/regulation/category/110
- FIA 2026 Technical Regulations Section C, Issue 18: https://www.fia.com/system/files/documents/fia_2026_f1_regulations_-_section_c_technical_-_iss_18_-_2026-05-07.pdf
- The default profile uses a configurable MGU-K deploy cap of 350 kW and explicitly synthetic battery/thermal/ERS assumptions.

## Test

```bash
python -m pytest
```

## Build

```bash
./scripts/build-dashboard.sh
npm run build
```
