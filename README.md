# Race Energy Orchestrator

Predictive hybrid race-vehicle energy management and clipping-prevention prototype. It uses public FastF1 lap telemetry when available and overlays configurable synthetic ERS, battery, thermal, active aero, and strategy signals. If FastF1 data is unavailable, the same CLI falls back to a deterministic Monza-like demo lap.

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

Scenario run with hotter ambient conditions and a lower starting battery state:

```bash
python -m race_energy_orchestrator --synthetic-only --ambient-temp-c 34 --initial-soc-mj 2.6 --initial-battery-temp-c 52 --horizon-s 38 --output outputs/hot_scenario.html
```

Deploy-ready static output:

```bash
python -m race_energy_orchestrator --synthetic-only --output docs/index.html
python -m http.server 8000 --directory docs
```

Then open `http://localhost:8000`.

Outputs:

- `outputs/report.html`: self-contained Plotly HTML report
- `outputs/metrics.csv`: fixed-map vs predictive strategy metrics
- `outputs/strategy_trace.csv`: combined strategy trace
- `docs/index.html`: static dashboard entrypoint for deployment

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

