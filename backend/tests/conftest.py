import sys
from pathlib import Path

# Ensure /backend is importable as the `app` package regardless of the
# directory pytest is invoked from, matching the approach in init_db.py
# and seed.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
