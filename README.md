# SF26 EnergyOS Prototype

Predictive hybrid energy-management and clipping-prevention prototype for a 2026-style Formula 1 car. It uses public FastF1 lap telemetry when available and overlays synthetic 2026 ERS, battery, thermal, active aero, and strategy signals. If FastF1 data is unavailable, the same CLI falls back to a deterministic synthetic Monza-like lap.

This is not Ferrari telemetry and does not claim real SF-26 parameters. Ferrari/SF-26 is treated as the concept context from the brief.

## Run

From this folder:

```bash
python -m sf26_energyos --year 2024 --event Monza --session Q --driver LEC --output outputs/report.html
```

Offline deterministic demo:

```bash
python -m sf26_energyos --synthetic-only --output outputs/report.html
```

Outputs:

- `outputs/report.html`: self-contained Plotly HTML report
- `outputs/metrics.csv`: fixed-map vs predictive strategy metrics
- `outputs/strategy_trace.csv`: combined strategy trace

## Model Basis

- FIA 2026 Formula One regulations category: https://www.fia.com/regulation/category/110
- FIA 2026 Technical Regulations Section C, Issue 18: https://www.fia.com/system/files/documents/fia_2026_f1_regulations_-_section_c_technical_-_iss_18_-_2026-05-07.pdf
- The prototype uses a configurable MGU-K deploy cap of 350 kW and explicitly synthetic battery/thermal/ERS assumptions.

## Test

```bash
python -m pytest
```

## Git Sync

Initialize and use the local repository:

```bash
git init -b main
git add .
git commit -m "Initial commit"
```

Create a private GitHub repo first, then connect it:

```bash
git remote add origin https://github.com/<USERNAME>/<PRIVATE_REPO>.git
git push -u origin main
```

Manual sync:

```bash
./scripts/git-sync-once.sh
```

Continuous auto-sync loop:

```bash
./scripts/git-auto-sync.sh
```

The auto-sync loop polls every 8 seconds by default and commits with an `autosync:` timestamp message whenever tracked files change.
