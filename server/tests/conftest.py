"""Pytest config + path shim. The server module is laid out flat (no
package), so we put its directory on sys.path here once per session."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
