"""Root shim so `python -m sf26_energyos` works without editable install."""

from pathlib import Path

_SRC_PACKAGE = Path(__file__).resolve().parent.parent / "src" / "sf26_energyos"
if _SRC_PACKAGE.exists():
    __path__.append(str(_SRC_PACKAGE))

__version__ = "0.1.0"
