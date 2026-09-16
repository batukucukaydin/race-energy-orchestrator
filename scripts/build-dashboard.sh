#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p docs docs/assets
cp -X web/*.html docs/
cp -X web/assets/*.css web/assets/*.js docs/assets/
PLOTLY_JS="$(python3 -c 'from pathlib import Path; import plotly; print(Path(plotly.__file__).parent / "package_data" / "plotly.min.js")')"
cp "$PLOTLY_JS" docs/assets/plotly.min.js
