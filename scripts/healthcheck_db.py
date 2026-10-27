"""Shortcut script to run CoverScope MongoDB Atlas health check."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.database.healthcheck import main

if __name__ == "__main__":
    sys.exit(main())
