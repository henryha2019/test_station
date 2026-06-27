"""Put the repo root on sys.path so `import host` / `import vision` work in tests."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
