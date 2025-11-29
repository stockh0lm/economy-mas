import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = PROJECT_ROOT / "agents"

for path in (PROJECT_ROOT, AGENTS_DIR):
    if path.exists():
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
