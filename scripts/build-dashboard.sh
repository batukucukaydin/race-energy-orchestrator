#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

rm -rf docs
mkdir -p docs
cp -R web/. docs/
PLOTLY_JS="$(python3 -c 'from pathlib import Path; import plotly; print(Path(plotly.__file__).parent / "package_data" / "plotly.min.js")')"
cp "$PLOTLY_JS" docs/assets/plotly.min.js
