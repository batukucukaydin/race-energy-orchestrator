# Race Energy Orchestrator

Predictive hybrid race-vehicle energy management and clipping-prevention prototype. It uses public FastF1 lap telemetry when available and overlays configurable synthetic ERS, battery, thermal, active aero, and strategy signals. If FastF1 data is unavailable, it falls back to a deterministic track/session/driver-specific synthetic lap.

The project is intentionally team-neutral and vehicle-neutral. Its default configuration uses a 2026-style formula-car regulation profile as an example, not a real team, driver, or car dataset.

## Run the live application

The live product is a FastAPI application with a separate static client in `web/`. Start one server:

```bash
python3 -m uvicorn race_energy_orchestrator.api:app --host 127.0.0.1 --port 8001 --reload
```

Open `http://localhost:8001/`. Dashboard, Telemetry, and Guide use the same stable application shell. Session changes fetch JSON from `/api/*` without a page reload.

Frontend responsibilities:

- `web/*.html`: semantic page structure only
- `web/assets/styles.css`: shared design and responsive layout
- `web/assets/app.js`: API state, localization, filters, replay, and charts

Backend responsibilities:

- `src/race_energy_orchestrator/api.py`: HTTP contracts and static-file serving
- Python model modules: FastF1 loading, segmentation, strategy, simulation, metrics, and stint planning

## Offline report export

The CLI still supports a portable, self-contained report when an explicit offline artifact is required:

```bash
python -m race_energy_orchestrator --synthetic-only --output outputs/report.html
```

The exported report embeds its data and Plotly runtime by design. It is not the primary live web application. CSV files are not written unless an explicit output path is provided.

The dashboard begins with a synthetic live-decision replay for the race engineer. It uses one operator command vocabulary (`THERMAL PROTECT`, `REGEN PRIORITY`, `ENERGY HOLD`, `DEPLOY NOW`) and separates realized clipping duration from potential future clipping risk. Deploy intensity is normalized against the MGU-K power-time envelope; it is not cumulative deploy energy divided by a single-lap battery capacity.

The five-lap stint planner derives a multi-lap energy budget from the selected representative lap. It schedules `BUILD`, `NORMAL`, `ATTACK`, `RECOVER`, or `COOL` modes while enforcing Energy Store capacity, minimum reserve, regeneration acceptance, and battery-temperature limits. Its SoC and ERS outputs remain model estimates; the dashboard labels whether they are synthetic or derived from FastF1 telemetry.

Scenario run with hotter ambient conditions and a lower starting battery state:

```bash
python -m race_energy_orchestrator --synthetic-only --ambient-temp-c 34 --initial-soc-mj 2.6 --initial-battery-temp-c 52 --horizon-s 38 --output outputs/hot_scenario.html
```

Compare orchestrator behavior across baseline, hot, low-SoC, and thermal-stress scenarios:

```bash
python -m race_energy_orchestrator --synthetic-only --compare-scenarios --output outputs/scenario_dashboard.html
```

This adds the comparison table to the dashboard. To additionally export CSV data, pass `--metrics-output`, `--trace-output`, or `--comparison-output` explicitly.

Build the static client copy:

```bash
./scripts/build-dashboard.sh
npm run build
```

`docs/` is generated from `web/` and marked as generated for GitHub Linguist. A static deployment still needs the API under the same `/api` origin or an equivalent reverse proxy.

API endpoints:

- `GET /api/health`: service and data-source status
- `GET /api/session`: current session metadata
- `GET /api/metrics`: fixed-map and predictive-orchestrator KPI rows
- `GET /api/options`: supported years, tracks, and session types
- `GET /api/trace`: selected fixed/predictive telemetry traces for the live chart
- `GET /api/decision?index=0`: one operator decision
- `GET /api/decisions?start=0&limit=100`: paginated decision stream
- `GET /api/scenarios`: selected-track scenario comparison
- `GET /api/stint-plan?current_lap=1&horizon_laps=5`: bounded multi-lap energy plan

The live web panel only renders data returned by the FastAPI backend. If the API is offline or FastF1 has no telemetry, it shows a clear error state and does not substitute embedded telemetry. A future race returns `409` instead of fabricating telemetry.

Outputs:

- `outputs/report.html`: self-contained Plotly HTML report
- `web/`: primary live frontend source
- `docs/`: generated static deployment copy
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
